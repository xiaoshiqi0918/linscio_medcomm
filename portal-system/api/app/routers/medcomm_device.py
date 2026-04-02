"""
MedComm v3 换机码：服务端生成 6 位数字，门户验证后下发新 Token
"""
import random
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.medcomm_models import (
    MedcommUser,
    MedcommUserLicense,
    MedcommDeviceChangeCode,
    MedcommDeviceRebindLog,
)
from app.schemas.medcomm import (
    MedcommChangeCodeRequestRequest,
    MedcommChangeCodeRequestResponse,
    MedcommChangeCodeVerifyRequest,
    MedcommChangeCodeVerifyResponse,
)
from app.services.medcomm_auth_service import (
    verify_password,
    get_user_by_credential,
    decode_session_token,
    get_user_by_id,
    get_user_license,
    generate_access_token,
)
from app.services.medcomm_rate_limit import check_locked, record_failure, reset_failures

router = APIRouter(prefix="/medcomm/device", tags=["medcomm-device"])
security = HTTPBearer(auto_error=False)

CHANGE_CODE_TTL_SEC = 300
MAX_REBIND_PER_CYCLE = 2


@router.post("/change-code/request", response_model=MedcommChangeCodeRequestResponse)
async def change_code_request(
    body: MedcommChangeCodeRequestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    新设备凭账号密码请求换机码（无需 Bearer）；按 credential 限流 5 次/30 分钟
    """
    cred = (body.credential or "").strip()
    if "@" in cred:
        cred_key = cred.lower()
    elif len("".join(c for c in cred if c.isdigit())) == 11:
        cred_key = "".join(c for c in cred if c.isdigit())
    else:
        cred_key = cred.lower()
    cred_id = f"changecode_request:{cred_key}"
    locked = await check_locked(db, "changecode_request", cred_id)
    if locked:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    user = await get_user_by_credential(db, body.credential)
    if not user or not verify_password(body.password, user.password_hash):
        await record_failure(db, "changecode_request", cred_id, max_failures=5, lockout_minutes=30)
        await db.commit()
        return MedcommChangeCodeRequestResponse(
            success=False,
            error="invalid_credential",
            message="账号或密码错误",
        )
    if user.is_active != 1:
        await db.commit()
        return MedcommChangeCodeRequestResponse(
            success=False,
            error="account_disabled",
            message="账号已被封禁",
        )

    ul = await get_user_license(db, user.id)
    if not ul:
        await db.commit()
        return MedcommChangeCodeRequestResponse(
            success=False,
            error="no_license",
            message="未找到有效授权，请先激活授权码",
        )

    remaining = MAX_REBIND_PER_CYCLE - (ul.rebind_count or 0)
    if remaining <= 0:
        await db.commit()
        return MedcommChangeCodeRequestResponse(
            success=False,
            error="rebind_limit_exceeded",
            message="本授权周期换机次数已用完，请联系客服处理",
        )

    user_lock = await check_locked(db, "changecode_verify", str(user.id))
    if user_lock:
        await db.commit()
        return MedcommChangeCodeRequestResponse(
            success=False,
            error="rate_limited",
            message="请稍后再试",
        )

    code = f"{random.randint(0, 999999):06d}"
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=CHANGE_CODE_TTL_SEC)
    row = MedcommDeviceChangeCode(
        user_id=user.id,
        code=code,
        new_fingerprint=body.new_fingerprint.strip()[:128],
        new_device_name=(body.new_device_name or "")[:255],
        expires_at=expires,
        is_used=0,
    )
    db.add(row)
    await reset_failures(db, "changecode_request", cred_id)
    await db.commit()
    return MedcommChangeCodeRequestResponse(
        success=True,
        code=code,
        expires_in=CHANGE_CODE_TTL_SEC,
    )


@router.post("/change-code/verify", response_model=MedcommChangeCodeVerifyResponse)
async def change_code_verify(
    body: MedcommChangeCodeVerifyRequest,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """门户已登录用户输入换机码完成换绑"""
    if not cred or not cred.credentials:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = decode_session_token(cred.credentials.strip())
    if not user_id:
        raise HTTPException(status_code=401, detail="请使用门户登录凭证")
    user = await get_user_by_id(db, user_id)
    if not user or user.is_active != 1:
        raise HTTPException(status_code=401, detail="用户无效")

    locked = await check_locked(db, "changecode_verify", str(user.id))
    if locked:
        return MedcommChangeCodeVerifyResponse(
            success=False,
            error="rate_limited",
            locked_until=locked.isoformat(),
        )

    code = (body.code or "").strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        await record_failure(db, "changecode_verify", str(user.id), 5, 30)
        await db.commit()
        return MedcommChangeCodeVerifyResponse(success=False, error="code_invalid")

    now = datetime.now(timezone.utc)
    r = await db.execute(
        select(MedcommDeviceChangeCode).where(
            MedcommDeviceChangeCode.user_id == user.id,
            MedcommDeviceChangeCode.code == code,
            MedcommDeviceChangeCode.is_used == 0,
        )
    )
    row = r.scalar_one_or_none()
    if not row:
        await record_failure(db, "changecode_verify", str(user.id), 5, 30)
        await db.commit()
        return MedcommChangeCodeVerifyResponse(success=False, error="code_invalid")

    exp = row.expires_at
    if getattr(exp, "tzinfo", None) is None and exp:
        exp = exp.replace(tzinfo=timezone.utc)
    if not exp or exp < now:
        await record_failure(db, "changecode_verify", str(user.id), 5, 30)
        await db.commit()
        return MedcommChangeCodeVerifyResponse(success=False, error="code_expired")

    ul = await get_user_license(db, user.id)
    if not ul:
        await db.commit()
        return MedcommChangeCodeVerifyResponse(success=False, error="no_license")

    old_fp = ul.device_fingerprint
    old_name = ul.device_name
    new_fp = row.new_fingerprint
    new_name = row.new_device_name
    new_token = generate_access_token()
    ul.device_fingerprint = new_fp
    ul.device_name = new_name
    ul.access_token = new_token
    ul.token_created_at = now
    ul.rebind_count = (ul.rebind_count or 0) + 1
    ul.updated_at = now
    # 用后即删（设计 2.1）
    await db.delete(row)

    db.add(
        MedcommDeviceRebindLog(
            user_id=user.id,
            old_fingerprint=old_fp,
            new_fingerprint=new_fp,
            old_device_name=old_name,
            new_device_name=new_name,
            rebind_type="self_service",
        )
    )
    await reset_failures(db, "changecode_verify", str(user.id))
    await db.commit()

    rebind_remaining = max(0, MAX_REBIND_PER_CYCLE - ul.rebind_count)
    return MedcommChangeCodeVerifyResponse(
        success=True,
        new_device_name=new_name,
        rebind_remaining=rebind_remaining,
        deep_link=f"linscio://auth?token={new_token}",
    )

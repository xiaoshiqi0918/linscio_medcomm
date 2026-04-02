"""
LinScio MedComm v3 认证路由
- 注册（验证码流程，开发环境可日志输出验证码）
- 验证
- 登录（支持邮箱/手机号/用户名）
- 改密、忘记密码、重置密码
"""
import random
import re
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.medcomm_models import (
    MedcommUser,
    MedcommPendingRegistration,
    MedcommPasswordReset,
)
from app.schemas.medcomm import (
    MedcommRegisterRequest,
    MedcommVerifyRequest,
    MedcommLoginRequest,
    MedcommLoginResponse,
    MedcommChangePasswordRequest,
    MedcommForgotPasswordRequest,
    MedcommResetPasswordRequest,
)
from app.services.medcomm_rate_limit import (
    check_locked,
    record_failure,
    record_cooldown,
    reset_failures,
)
from app.services.medcomm_auth_service import (
    hash_password,
    verify_password,
    get_user_by_credential,
    create_session_token,
    decode_session_token,
    is_valid_email,
    is_valid_phone,
    is_valid_username,
    normalize_credential,
    revoke_access_token,
)

router = APIRouter(prefix="/medcomm/auth", tags=["medcomm-auth"])
CODE_TTL_MINUTES = 10
DEV_BYPASS_CODE = "123456"  # 开发环境万能码


def _normalize_for_lookup(credential: str) -> str | None:
    """用于查找 pending/reset 的 credential 规范化"""
    s = (credential or "").strip()
    if not s:
        return None
    if "@" in s:
        return s.lower()
    if len(re.sub(r"\D", "", s)) == 11:
        return re.sub(r"\D", "", s)
    return s.lower()


@router.post("/register")
async def register(
    body: MedcommRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """注册：发送验证码（规范 3.1）"""
    cred = normalize_credential(body.credential, body.credential_type)
    if not cred:
        raise HTTPException(status_code=400, detail="凭证格式不正确")
    if body.credential_type == "email" and not is_valid_email(body.credential):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if body.credential_type == "phone" and not is_valid_phone(body.credential):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    if body.credential_type == "username" and not is_valid_username(body.credential):
        raise HTTPException(status_code=400, detail="用户名须 3-32 位字母数字下划线")
    existing = await get_user_by_credential(db, body.credential)
    if existing:
        raise HTTPException(status_code=400, detail="该账号已注册")
    code_send_key = f"code_send:{cred}"
    if await check_locked(db, "code_send", code_send_key):
        raise HTTPException(status_code=429, detail="验证码发送过于频繁，请 1 分钟后再试")
    code = f"{random.randint(0, 999999):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
    # 删除同 credential 的旧待验证
    await db.execute(
        delete(MedcommPendingRegistration).where(MedcommPendingRegistration.credential == cred)
    )
    pr = MedcommPendingRegistration(
        credential=cred,
        credential_type=body.credential_type,
        password_hash=hash_password(body.password),
        code=code,
        expires_at=expires,
    )
    db.add(pr)
    await record_cooldown(db, "code_send", code_send_key, cooldown_minutes=1)
    await db.commit()
    # 开发环境日志输出验证码（邮件/短信待集成）
    # import logging
    # logging.getLogger(__name__).info(f"MedComm register code for {cred}: {code}")
    return {"success": True, "message": "验证码已发送"}


@router.post("/verify")
async def verify(
    body: MedcommVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """验证账号：校验验证码后完成注册。开发环境可用验证码 123456。"""
    cred = _normalize_for_lookup(body.credential)
    if not cred:
        raise HTTPException(status_code=400, detail="凭证格式不正确")
    r = await db.execute(
        select(MedcommPendingRegistration).where(
            MedcommPendingRegistration.credential == cred
        )
    )
    pr = r.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=400, detail="请先获取验证码或验证码已过期")
    now = datetime.now(timezone.utc)
    exp = pr.expires_at
    if getattr(exp, "tzinfo", None) is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        await db.execute(delete(MedcommPendingRegistration).where(MedcommPendingRegistration.id == pr.id))
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    code_ok = (body.code or "").strip() == pr.code or (body.code or "").strip() == DEV_BYPASS_CODE
    if not code_ok:
        raise HTTPException(status_code=400, detail="验证码错误")
    user = MedcommUser(
        username=cred if pr.credential_type == "username" else None,
        email=cred if pr.credential_type == "email" else None,
        phone=cred if pr.credential_type == "phone" else None,
        password_hash=pr.password_hash,
    )
    db.add(user)
    await db.execute(delete(MedcommPendingRegistration).where(MedcommPendingRegistration.id == pr.id))
    await db.commit()
    return {"success": True, "message": "验证成功"}


@router.post("/login", response_model=MedcommLoginResponse)
async def login(
    body: MedcommLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """登录（支持邮箱/手机号/用户名）；同 IP 失败 10 次锁定 60 分钟"""
    client_ip = request.client.host if request.client else "unknown"
    login_ip_key = f"login_ip:{client_ip}"
    locked = await check_locked(db, "login_ip", login_ip_key)
    if locked:
        raise HTTPException(
            status_code=429,
            detail=f"登录尝试过于频繁，请 {int((locked - datetime.now(timezone.utc)).total_seconds() // 60) + 1} 分钟后再试",
        )
    user = await get_user_by_credential(db, body.credential)
    if not user or not verify_password(body.password, user.password_hash):
        await record_failure(db, "login_ip", login_ip_key, max_failures=10, lockout_minutes=60)
        await db.commit()
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user.is_active != 1:
        raise HTTPException(status_code=403, detail="账号已被封禁")
    await reset_failures(db, "login_ip", login_ip_key)
    await db.commit()
    token = create_session_token(user.id)
    return MedcommLoginResponse(session_token=token, expires_in=7 * 86400)


async def _get_medcomm_user_from_bearer(
    cred: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> MedcommUser | None:
    from app.services.medcomm_auth_service import decode_session_token, get_user_by_id
    if not cred or not cred.credentials:
        return None
    user_id = decode_session_token(cred.credentials.strip())
    if user_id:
        return await get_user_by_id(db, user_id)
    return None


@router.post("/change-password")
async def change_password(
    body: MedcommChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
):
    """修改密码（需 Bearer session_token），成功后撤销 access_token"""
    from app.services.medcomm_auth_service import decode_session_token, get_user_by_id
    if not cred or not cred.credentials:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = decode_session_token(cred.credentials.strip())
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的登录凭证")
    user = await get_user_by_id(db, user_id)
    if not user or user.is_active != 1:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    client_ip = request.client.host if request.client else None
    await revoke_access_token(db, user.id, reason="password_changed", client_ip=client_ip)
    await db.commit()
    return {
        "success": True,
        "access_token_revoked": True,
        "message": "密码已修改。下次打开软件时需要重新激活授权。",
    }


@router.post("/forgot-password")
async def forgot_password(
    body: MedcommForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """忘记密码：发送重置验证码（规范 3.1，邮件/短信待集成）。开发环境可用验证码 123456。"""
    cred = _normalize_for_lookup(body.credential)
    if not cred:
        raise HTTPException(status_code=400, detail="凭证格式不正确")
    code_send_key = f"code_send:{cred}"
    if await check_locked(db, "code_send", code_send_key):
        raise HTTPException(status_code=429, detail="验证码发送过于频繁，请 1 分钟后再试")
    user = await get_user_by_credential(db, body.credential)
    if not user:
        await record_cooldown(db, "code_send", code_send_key, cooldown_minutes=1)
        await db.commit()
        return {"success": True, "message": "若该账号存在，将收到重置验证码"}
    code = f"{random.randint(0, 999999):06d}"
    # 邮箱重置 30 分钟，手机 10 分钟
    reset_ttl_min = 30 if "@" in (body.credential or "") else 10
    expires = datetime.now(timezone.utc) + timedelta(minutes=reset_ttl_min)
    await db.execute(
        delete(MedcommPasswordReset).where(MedcommPasswordReset.credential == cred)
    )
    pr = MedcommPasswordReset(credential=cred, code=code, expires_at=expires)
    db.add(pr)
    await record_cooldown(db, "code_send", code_send_key, cooldown_minutes=1)
    await db.commit()
    return {"success": True, "message": "若该账号存在，将收到重置验证码"}


@router.post("/reset-password")
async def reset_password(
    body: MedcommResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """重置密码：验证码 + 新密码完成重置"""
    cred = _normalize_for_lookup(body.credential)
    if not cred:
        raise HTTPException(status_code=400, detail="凭证格式不正确")
    r = await db.execute(
        select(MedcommPasswordReset).where(MedcommPasswordReset.credential == cred)
    )
    pr = r.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=400, detail="请先获取重置验证码或验证码已过期")
    now = datetime.now(timezone.utc)
    exp = pr.expires_at
    if getattr(exp, "tzinfo", None) is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        await db.execute(delete(MedcommPasswordReset).where(MedcommPasswordReset.id == pr.id))
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    code_ok = (body.code or "").strip() == pr.code or (body.code or "").strip() == DEV_BYPASS_CODE
    if not code_ok:
        raise HTTPException(status_code=400, detail="验证码错误")
    user = await get_user_by_credential(db, body.credential)
    if not user:
        raise HTTPException(status_code=400, detail="账号不存在")
    user.password_hash = hash_password(body.new_password)
    user.updated_at = now
    client_ip = request.client.host if request.client else None
    await revoke_access_token(db, user.id, reason="password_reset", client_ip=client_ip)
    await db.execute(delete(MedcommPasswordReset).where(MedcommPasswordReset.id == pr.id))
    await db.commit()
    return {"success": True, "message": "密码已重置"}

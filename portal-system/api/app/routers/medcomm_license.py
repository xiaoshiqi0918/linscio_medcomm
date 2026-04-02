"""
LinScio MedComm v3 授权码激活与状态查询
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.medcomm_models import (
    MedcommUser,
    MedcommUserLicense,
    MedcommUserSpecialty,
    MedcommLicenseCode,
    MedcommSpecialtyVersionPolicy,
)
from app.schemas.medcomm import (
    MedcommActivateRequest,
    MedcommActivateResponse,
    MedcommValidateRequest,
    MedcommValidateResponse,
    MedcommLicenseStatusResponse,
    MedcommLicenseStatusBase,
    MedcommSpecialtyStatus,
    MedcommVersionPolicy,
)
from app.services.medcomm_auth_service import (
    get_user_by_credential,
    get_user_by_access_token,
    decode_session_token,
    get_user_license,
)
from app.services.medcomm_license_service import (
    validate_license_format,
    lookup_license_code,
    compute_new_expires_at,
    normalize_license_code,
    SPECIALTY_NAMES,
)
from app.services.medcomm_manifest_service import load_specialty_manifest, specialty_remote_info
from app.services.medcomm_rate_limit import check_locked, record_failure, reset_failures

router = APIRouter(prefix="/medcomm/license", tags=["medcomm-license"])
security = HTTPBearer(auto_error=False)


async def get_medcomm_user(
    cred: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> MedcommUser | None:
    """从 Bearer 解析：session_token (JWT) 或 access_token (64-char hex)"""
    if not cred or not cred.credentials:
        return None
    token = cred.credentials.strip()
    # 尝试 JWT（门户）
    user_id = decode_session_token(token)
    if user_id:
        from app.services.medcomm_auth_service import get_user_by_id
        user = await get_user_by_id(db, user_id)
        if user and user.is_active != 1:
            return None  # 封禁用户 JWT 路径同样拒绝
        return user
    # 尝试 access_token（软件）
    return await get_user_by_access_token(db, token)


@router.post("/validate", response_model=MedcommValidateResponse)
async def validate_code(
    body: MedcommValidateRequest,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """
    验证授权码（预览激活结果，不实际激活）
    用于两步流程：先验证展示预览，用户确认后再调用 activate
    """
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    ok, _ = validate_license_format(body.code)
    if not ok:
        return MedcommValidateResponse(valid=False, error="授权码格式不正确")

    lc = await lookup_license_code(db, body.code)
    if not lc:
        return MedcommValidateResponse(valid=False, error="授权码无效或已使用")
    if lc.is_activated and lc.activated_by != user.id:
        return MedcommValidateResponse(valid=False, error="授权码已被他人使用")

    ul = await get_user_license(db, user.id)
    now = datetime.now(timezone.utc)

    if lc.license_type == "specialty":
        specialty_ids = lc.specialty_ids or []
        names = [SPECIALTY_NAMES.get(s, s) for s in specialty_ids]
        return MedcommValidateResponse(
            valid=True,
            license_type="specialty",
            is_trial=bool(lc.is_trial),
            specialty_ids=specialty_ids,
            specialty_names=names,
        )

    duration = lc.duration_months or 12
    current_expires = ul.expires_at if ul else None
    new_expires = compute_new_expires_at(current_expires, duration, now)
    current_days = None
    if current_expires and current_expires > now:
        current_days = (current_expires - now).days

    return MedcommValidateResponse(
        valid=True,
        license_type="basic",
        is_trial=bool(lc.is_trial),
        duration_months=duration,
        current_expires_at=current_expires.isoformat() if current_expires else None,
        current_days_remaining=current_days,
        new_expires_at=new_expires.isoformat() if new_expires else None,
    )


@router.post("/activate", response_model=MedcommActivateResponse)
async def activate(
    body: MedcommActivateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """
    激活授权码（需已登录，Bearer session_token）
    首次激活返回 deep_link，续费时 token_unchanged=true
    """
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    client_ip = request.client.host if request.client else "unknown"
    ip_id = f"activate:{client_ip}"
    user_id_str = f"activate_user:{user.id}"
    locked = await check_locked(db, "activate_ip", ip_id)
    user_locked = await check_locked(db, "activate_user", user_id_str)
    if locked:
        await db.commit()
        return MedcommActivateResponse(success=False, error="rate_limit_exceeded")
    if user_locked:
        await db.commit()
        return MedcommActivateResponse(
            success=False,
            error="account_locked",
            message="激活失败次数过多，账号已永久锁定，请联系管理员解锁",
        )

    ok, err = validate_license_format(body.code)
    if not ok:
        await record_failure(db, "activate_ip", ip_id, max_failures=5, lockout_minutes=60)
        await record_failure(db, "activate_user", user_id_str, max_failures=10, lockout_minutes=-1)
        await db.commit()
        return MedcommActivateResponse(success=False, error="code_invalid_or_used")

    lc = await lookup_license_code(db, body.code)
    if not lc:
        await record_failure(db, "activate_ip", ip_id, max_failures=5, lockout_minutes=60)
        await record_failure(db, "activate_user", user_id_str, max_failures=10, lockout_minutes=-1)
        await db.commit()
        return MedcommActivateResponse(success=False, error="code_invalid_or_used")
    if lc.is_activated and lc.activated_by != user.id:
        await record_failure(db, "activate_ip", ip_id, max_failures=5, lockout_minutes=60)
        await record_failure(db, "activate_user", user_id_str, max_failures=10, lockout_minutes=-1)
        await db.commit()
        return MedcommActivateResponse(success=False, error="code_invalid_or_used")

    ul = await get_user_license(db, user.id)
    now = datetime.now(timezone.utc)

    if lc.license_type == "specialty":
        # 试用基础版用户不可再激活学科包（需正式授权）
        if ul and ul.is_trial:
            await db.commit()
            return MedcommActivateResponse(success=False, error="trial_no_specialty")
        # 学科包激活
        specialty_ids = lc.specialty_ids or []
        for sid in specialty_ids:
            r = await db.execute(
                select(MedcommUserSpecialty).where(
                    MedcommUserSpecialty.user_id == user.id,
                    MedcommUserSpecialty.specialty_id == sid,
                )
            )
            if not r.scalar_one_or_none():
                us = MedcommUserSpecialty(
                    user_id=user.id,
                    specialty_id=sid,
                    license_code_id=lc.id,
                )
                db.add(us)
        lc.is_activated = 1
        lc.activated_by = user.id
        lc.activated_at = now
        await reset_failures(db, "activate_ip", ip_id)
        await reset_failures(db, "activate_user", user_id_str)
        await db.commit()
        names = [SPECIALTY_NAMES.get(s, s) for s in specialty_ids]
        return MedcommActivateResponse(
            success=True,
            license_type="specialty",
            specialty_ids=specialty_ids,
            specialty_names=names,
            deep_link=f"linscio://specialty/new?ids={','.join(specialty_ids)}",
        )

    # basic 基础版
    duration = lc.duration_months or 12
    current_expires = ul.expires_at if ul else None
    new_expires = compute_new_expires_at(current_expires, duration, now)
    token_unchanged = False
    deep_link = None
    rebind_count_reset = False

    if ul:
        # 续费
        ul.expires_at = new_expires
        ul.is_trial = lc.is_trial
        ul.updated_at = now
        token_unchanged = True
        rebind_count_reset = True
        ul.rebind_count = 0
    else:
        # 首次激活
        from app.services.medcomm_auth_service import generate_access_token

        access_token = generate_access_token()
        ul = MedcommUserLicense(
            user_id=user.id,
            is_trial=lc.is_trial,
            started_at=now,
            expires_at=new_expires,
            device_fingerprint=body.device_fingerprint,
            device_name=body.device_name,
            access_token=access_token,
            token_created_at=now,
        )
        db.add(ul)
        deep_link = f"linscio://auth?token={access_token}"
        rebind_count_reset = True

    lc.is_activated = 1
    lc.activated_by = user.id
    lc.activated_at = now
    await reset_failures(db, "activate_ip", ip_id)
    await reset_failures(db, "activate_user", user_id_str)
    await db.commit()

    days = (new_expires - now).days if new_expires else 0
    return MedcommActivateResponse(
        success=True,
        license_type="basic",
        is_trial=bool(lc.is_trial),
        new_expires_at=new_expires.isoformat() if new_expires else None,
        days_added=duration * 30,
        token_unchanged=token_unchanged,
        rebind_count_reset=rebind_count_reset,
        deep_link=deep_link,
    )


@router.get("/status", response_model=MedcommLicenseStatusResponse)
async def status(
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
    reported_specialties: str | None = None,
):
    """
    查询授权状态（Bearer access_token 或 session_token）
    reported_specialties: 软件上报的本地学科包版本，如 endocrine:2.0.0,cardiology:1.4.0
    """
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    ul = await get_user_license(db, user.id)
    if not ul:
        return MedcommLicenseStatusResponse(
            base=MedcommLicenseStatusBase(
                valid=False,
                is_trial=False,
                expires_at=None,
                days_remaining=None,
                device_name=None,
                token_created_at=None,
                rebind_remaining=0,
            ),
        )

    now = datetime.now(timezone.utc)
    valid = ul.access_token is not None and ul.expires_at and ul.expires_at > now
    days = (ul.expires_at - now).days if ul.expires_at and ul.expires_at > now else 0
    rebind_remaining = max(0, 2 - ul.rebind_count)

    if reported_specialties and isinstance(reported_specialties, str):
        ul.reported_specialties = {}
        for part in reported_specialties.split(","):
            if ":" in part:
                k, v = part.strip().split(":", 1)
                ul.reported_specialties[k.strip()] = v.strip()
        ul.reported_at = now

    base = MedcommLicenseStatusBase(
        valid=valid,
        is_trial=bool(ul.is_trial),
        expires_at=ul.expires_at.isoformat() if ul.expires_at else None,
        days_remaining=days if valid else None,
        device_name=ul.device_name,
        token_created_at=ul.token_created_at.isoformat() if ul.token_created_at else None,
        rebind_remaining=rebind_remaining,
    )

    manifest = load_specialty_manifest()
    r = await db.execute(
        select(MedcommUserSpecialty).where(MedcommUserSpecialty.user_id == user.id)
    )
    specs = r.scalars().all()
    reported = ul.reported_specialties or {}
    specialties = [
        MedcommSpecialtyStatus(
            id=s.specialty_id,
            name=SPECIALTY_NAMES.get(s.specialty_id, s.specialty_id),
            remote_version=specialty_remote_info(manifest, s.specialty_id).get("version"),
            local_version=reported.get(s.specialty_id),
            purchased_at=s.purchased_at.isoformat() if s.purchased_at else None,
        )
        for s in specs
    ]

    r2 = await db.execute(select(MedcommSpecialtyVersionPolicy))
    policies = [
        MedcommVersionPolicy(
            specialty_id=p.specialty_id,
            force_min_version=p.force_min_version,
            force_max_version=p.force_max_version,
            policy_message=p.policy_message,
        )
        for p in r2.scalars().all()
    ]

    await db.commit()
    return MedcommLicenseStatusResponse(
        base=base,
        specialties=specialties,
        version_policies=policies,
    )

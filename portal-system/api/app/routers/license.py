"""
运行时心跳验证（8.3）：镜像启动时上报，校验授权、机器绑定、并发后允许运行。
超过 15 分钟无心跳的实例标记离线，释放并发名额。
支持公钥签名方案：配置 LINSCIO_LICENSE_PRIVATE_KEY 时在响应中返回 signed_token 供客户端离线验签。
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import LicenseKey, Plan, MachineBinding, InstanceHeartbeat, GenerationQuota, PortalUser
from app.services.quota_service import get_cycle_bounds, get_quota_limit, CONTENT_TYPES as QUOTA_CONTENT_TYPES
from app.services.license_service import mask_to_module_codes

router = APIRouter(prefix="/license", tags=["license"])

HEARTBEAT_OFFLINE_MINUTES = 15


async def _allowed_login_usernames_for_license(db: AsyncSession, license_key: LicenseKey) -> list[str]:
    """返回该授权码允许登录主产品实例的用户名列表：授权绑定用户 + admin。"""
    out = ["admin"]
    if license_key.assigned_to:
        u = await db.get(PortalUser, license_key.assigned_to)
        if u and getattr(u, "username", None):
            if u.username not in out:
                out.append(u.username)
    return out


def _make_signed_token(license_key: LicenseKey, machine_id: str) -> str | None:
    """若配置了签发私钥则返回 signed_token，否则返回 None"""
    try:
        from app.config import settings
        from app.services.license_signing import get_signing_key, sign_license_payload
        key = get_signing_key(getattr(settings, "LINSCIO_LICENSE_PRIVATE_KEY", "") or "")
        if not key or not license_key.expires_at:
            return None
        expires_ts = int(license_key.expires_at.timestamp())
        return sign_license_payload(str(license_key.id), expires_ts, machine_id, key)
    except Exception:
        return None


class HeartbeatQuotaItem(BaseModel):
    used: int = 0
    limit: int = 0  # 0 表示不限
    reset_date: str = ""  # 周期重置日 YYYY-MM-DD


def _days_remaining(expires_at: datetime | None, now: datetime) -> int | None:
    if not expires_at:
        return None
    try:
        exp = expires_at.replace(tzinfo=None) if getattr(expires_at, "tzinfo", None) else expires_at
        delta = exp - now
        return max(0, delta.days)
    except Exception:
        return None


async def _heartbeat_quota(
    db: AsyncSession,
    license_key: LicenseKey,
    plan_code: str,
    machine_id: str,
) -> dict[str, HeartbeatQuotaItem]:
    bounds = get_cycle_bounds(license_key.activated_at)
    if not bounds:
        return {ct: HeartbeatQuotaItem(used=0, limit=get_quota_limit(plan_code or "basic", ct), reset_date="") for ct in QUOTA_CONTENT_TYPES}
    cycle_start, cycle_end = bounds
    next_reset = (cycle_end + timedelta(days=1)).isoformat()
    out = {}
    for ct in QUOTA_CONTENT_TYPES:
        lim = get_quota_limit(plan_code or "basic", ct)
        r = await db.execute(
            select(GenerationQuota).where(
                GenerationQuota.license_id == license_key.id,
                GenerationQuota.machine_id == machine_id,
                GenerationQuota.content_type == ct,
                GenerationQuota.cycle_start == cycle_start,
            )
        )
        row = r.scalar_one_or_none()
        used = row.used_count if row else 0
        out[ct] = HeartbeatQuotaItem(used=used, limit=lim, reset_date=next_reset)
    return out


class HeartbeatRequest(BaseModel):
    license_key: str
    machine_id: str
    instance_id: str


class HeartbeatOkResponse(BaseModel):
    ok: bool = True
    expires_at: str | None = None
    machine_limit: int = 1
    concurrent_limit: int = 1
    license_expired: bool = False
    message: str | None = None
    module_mask: int | None = None  # 套餐模块位图，应用据此解锁模块入口（5.3）
    modules: list[str] = []  # 模块 code 列表，主产品据此做 require_module 校验
    concurrent_count: int = 0  # 当前活跃实例数（含本实例）（6.4）
    days_remaining: int | None = None  # 授权剩余天数（7.3）
    quota: dict[str, HeartbeatQuotaItem] = {}  # schola / medcomm / qcc 各类剩余次数（7.3）
    revoked: bool = False
    # 公钥签名方案：客户端可缓存用于离线验签，格式 base64url(payload).base64url(signature)
    signed_token: str | None = None
    allowed_login_usernames: list[str] = []  # 允许登录主产品实例的用户名（主产品用本地密码校验）


class ValidateRequest(BaseModel):
    license_key: str
    machine_id: str


class ValidateResponse(BaseModel):
    valid: bool = True
    revoked: bool = False
    expired: bool = False
    message: str | None = None
    signed_token: str | None = None
    expires_at: str | None = None
    days_remaining: int | None = None
    modules: list[str] = []  # 模块 code 列表，主产品据此做 require_module 校验
    allowed_login_usernames: list[str] = []  # 允许登录主产品实例的用户名（主产品用本地密码校验）


@router.post("/validate", response_model=ValidateResponse)
async def license_validate(
    data: ValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    启动时校验授权码（不创建实例心跳）。返回 valid/signed_token/revoked/expired，便于客户端落盘与离线验签。
    """
    code = data.license_key.strip().upper()
    now = datetime.now(timezone.utc)
    r = await db.execute(
        select(LicenseKey).where(
            LicenseKey.code == code,
            LicenseKey.is_used == True,
        )
    )
    license_key = r.scalar_one_or_none()
    if not license_key:
        raise HTTPException(status_code=404, detail="授权码无效或未激活")
    if license_key.is_revoked:
        return ValidateResponse(valid=False, revoked=True, message="授权已作废")
    expired = license_key.expires_at and license_key.expires_at <= now
    days_rem = _days_remaining(license_key.expires_at, now)
    signed_token = _make_signed_token(license_key, data.machine_id)
    modules = await mask_to_module_codes(db, license_key.module_mask)
    allowed = await _allowed_login_usernames_for_license(db, license_key)
    return ValidateResponse(
        valid=True,
        revoked=False,
        expired=expired,
        message="授权已过期，请续费" if expired else None,
        signed_token=signed_token,
        expires_at=license_key.expires_at.isoformat() if license_key.expires_at else None,
        days_remaining=days_rem,
        modules=modules,
        allowed_login_usernames=allowed,
    )


@router.post("/heartbeat", response_model=HeartbeatOkResponse)
async def license_heartbeat(
    data: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    运行时心跳。校验通过返回 200（授权已过期时也返回 200 并带 license_expired，由应用展示橙色提示条）；
    并发超限或机器绑定数满且本机未绑定时返回 403 拒绝启动。
    """
    code = data.license_key.strip().upper()
    now = datetime.now(timezone.utc)
    offline_threshold = now - timedelta(minutes=HEARTBEAT_OFFLINE_MINUTES)

    r = await db.execute(
        select(LicenseKey).where(
            LicenseKey.code == code,
            LicenseKey.is_used == True,
        )
    )
    license_key = r.scalar_one_or_none()
    if not license_key:
        raise HTTPException(status_code=404, detail="授权码无效或未激活")
    if license_key.is_revoked:
        raise HTTPException(status_code=403, detail="授权已作废")

    plan_code = license_key.plan_type
    if license_key.plan_id:
        p = await db.get(Plan, license_key.plan_id)
        if p:
            plan_code = p.code
    machine_limit = license_key.machine_limit or 0
    concurrent_limit = license_key.concurrent_limit or 0

    expired = license_key.expires_at and license_key.expires_at <= now
    days_rem = _days_remaining(license_key.expires_at, now)
    quota_map = await _heartbeat_quota(db, license_key, plan_code or "basic", data.machine_id)
    signed_token = _make_signed_token(license_key, data.machine_id)
    modules = await mask_to_module_codes(db, license_key.module_mask)
    allowed = await _allowed_login_usernames_for_license(db, license_key)
    if expired:
        return HeartbeatOkResponse(
            ok=True,
            expires_at=license_key.expires_at.isoformat() if license_key.expires_at else None,
            machine_limit=machine_limit,
            concurrent_limit=concurrent_limit,
            license_expired=True,
            message="授权已过期，请续费",
            module_mask=license_key.module_mask,
            modules=modules,
            concurrent_count=0,
            days_remaining=days_rem,
            quota=quota_map,
            signed_token=signed_token,
            allowed_login_usernames=allowed,
        )

    await db.execute(
        update(InstanceHeartbeat)
        .where(
            InstanceHeartbeat.license_id == license_key.id,
            InstanceHeartbeat.last_beat < offline_threshold,
        )
        .values(is_active=False)
    )
    await db.flush()

    bindings = await db.execute(
        select(MachineBinding).where(
            MachineBinding.license_id == license_key.id,
            MachineBinding.is_active == True,
        )
    )
    bindings_list = bindings.scalars().all()
    machine_ids = {b.machine_id for b in bindings_list}
    if machine_limit > 0 and len(bindings_list) >= machine_limit and data.machine_id not in machine_ids:
        raise HTTPException(
            status_code=403,
            detail=f"已达机器绑定上限（{len(bindings_list)}/{machine_limit}），请在用户中心解绑旧机器",
        )

    active_instances = await db.execute(
        select(func.count(InstanceHeartbeat.id)).where(
            InstanceHeartbeat.license_id == license_key.id,
            InstanceHeartbeat.is_active == True,
        )
    )
    active_count = active_instances.scalar() or 0
    existing = await db.execute(
        select(InstanceHeartbeat).where(
            InstanceHeartbeat.license_id == license_key.id,
            InstanceHeartbeat.instance_id == data.instance_id,
        )
    )
    instance_row = existing.scalar_one_or_none()
    if instance_row and instance_row.is_active:
        active_count_after = active_count
    else:
        active_count_after = active_count + 1
    if concurrent_limit > 0 and active_count_after > concurrent_limit:
        raise HTTPException(
            status_code=403,
            detail=f"并发实例数已达上限（{active_count_after}/{concurrent_limit}）",
        )
    if instance_row:
        instance_row.last_beat = now
        instance_row.is_active = True
        instance_row.machine_id = data.machine_id
    else:
        db.add(InstanceHeartbeat(
            license_id=license_key.id,
            machine_id=data.machine_id,
            instance_id=data.instance_id,
            last_beat=now,
            is_active=True,
        ))
    await db.flush()

    mb = await db.execute(
        select(MachineBinding).where(
            MachineBinding.license_id == license_key.id,
            MachineBinding.machine_id == data.machine_id,
        )
    )
    binding_row = mb.scalar_one_or_none()
    if binding_row:
        binding_row.last_heartbeat = now
        if not binding_row.is_active:
            binding_row.is_active = True
    else:
        user_id = license_key.assigned_to
        if user_id:
            db.add(MachineBinding(
                license_id=license_key.id,
                user_id=user_id,
                machine_id=data.machine_id,
                last_heartbeat=now,
                is_active=True,
            ))
    await db.flush()

    return HeartbeatOkResponse(
        ok=True,
        expires_at=license_key.expires_at.isoformat() if license_key.expires_at else None,
        machine_limit=machine_limit,
        concurrent_limit=concurrent_limit,
        license_expired=False,
        module_mask=license_key.module_mask,
        modules=modules,
        concurrent_count=active_count_after,
        days_remaining=days_rem,
        quota=quota_map,
        signed_token=signed_token,
        allowed_login_usernames=allowed,
    )

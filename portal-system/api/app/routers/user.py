from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.database import get_db
from app.models import PortalUser, LicenseKey, RegistryCredential, Plan, BillingPeriod, MachineBinding, ContainerToken, ContainerMachineBinding, GenerationQuota
from app.schemas.user import (
    UserProfile,
    ActivateLicenseRequest,
    LicenseInfo,
    RegistryCredentialResponse,
    MachineBindingItem,
    MachineListResponse,
    QuotaSummaryResponse,
    QuotaMachineItem,
    QuotaTypeItem,
    PullQuotaResponse,
)
from app.services.auth_service import decode_access_token
from app.services.quota_service import get_cycle_bounds, get_quota_limit, CONTENT_TYPES
from app.services.license_service import (
    validate_license_format,
    lookup_license_activate_status,
    validate_license_plan_period,
)
from app.services.registry_service import (
    generate_registry_username,
    generate_registry_password,
    encrypt_password,
    decrypt_password,
    write_htpasswd,
    get_plan_prefix,
    get_allowed_image_tags,
)
from app.config import settings

router = APIRouter(prefix="/user", tags=["user"])
security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if not credentials or credentials.credentials is None:
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    return user_id


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(PortalUser).where(PortalUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")
    return user


@router.get("/profile", response_model=UserProfile)
async def get_profile(user: PortalUser = Depends(get_current_user)):
    return user


@router.post("/activate")
async def activate_user_license(
    data: ActivateLicenseRequest,
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    code = data.code.strip().upper()
    ok, err_msg = validate_license_format(code)
    if not ok:
        raise HTTPException(status_code=400, detail=err_msg or "授权码格式错误，请检查输入")

    err_plan_period = await validate_license_plan_period(db, code)
    if err_plan_period:
        raise HTTPException(status_code=400, detail=err_plan_period)
    license_key, err_msg = await lookup_license_activate_status(db, code)
    if err_msg:
        raise HTTPException(status_code=400, detail=err_msg)

    try:
        license_key.is_used = True
        license_key.assigned_to = user.id
        license_key.activated_at = datetime.now(timezone.utc)
        await db.flush()
        await _bind_license_to_user_and_credential(db, user, license_key)
        return {"message": "激活成功"}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        err = str(e) if getattr(settings, "ENVIRONMENT", "production") == "development" else "激活过程出错"
        raise HTTPException(status_code=500, detail=err)


async def _bind_license_to_user_and_credential(
    db: AsyncSession,
    user: PortalUser,
    license_key: LicenseKey,
) -> None:
    """将授权码绑定到用户并生成/更新 Registry 凭证。调用前需已 flush license_key 的 is_used/assigned_to/activated_at。"""
    plan_code = license_key.plan_type
    if license_key.plan_id:
        res = await db.execute(select(Plan).where(Plan.id == license_key.plan_id))
        plan = res.scalar_one_or_none()
        if plan:
            plan_code = plan.code
    plan_prefix = get_plan_prefix(plan_code) if plan_code else None
    reg_username = generate_registry_username(plan_prefix)
    reg_password = generate_registry_password()
    if not write_htpasswd(reg_username, reg_password):
        raise HTTPException(status_code=500, detail="Registry 凭证写入失败，请检查 API 容器内 /registry/auth 可写且已安装 htpasswd")
    allowed_tags = get_allowed_image_tags(plan_code) if plan_code else None
    existing = await db.execute(select(RegistryCredential).where(RegistryCredential.user_id == user.id))
    cred_row = existing.scalar_one_or_none()
    if cred_row:
        cred_row.license_id = license_key.id
        cred_row.registry_username = reg_username
        cred_row.registry_password_enc = encrypt_password(reg_password)
        cred_row.expires_at = license_key.expires_at
        cred_row.allowed_image_tags = allowed_tags
        await db.flush()
    else:
        cred = RegistryCredential(
            user_id=user.id,
            license_id=license_key.id,
            registry_username=reg_username,
            registry_password_enc=encrypt_password(reg_password),
            expires_at=license_key.expires_at,
            allowed_image_tags=allowed_tags,
        )
        db.add(cred)
        await db.flush()


@router.post("/update-license")
async def update_user_license(
    data: ActivateLicenseRequest,
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    """
    使用新的授权码重新激活当前账户。新授权码须未使用、未过期、未作废；原授权码将解除与当前用户的绑定并可被他人使用。
    """
    code = data.code.strip().upper()
    ok, err_msg = validate_license_format(code)
    if not ok:
        raise HTTPException(status_code=400, detail=err_msg or "授权码格式错误，请检查输入")
    err_plan_period = await validate_license_plan_period(db, code)
    if err_plan_period:
        raise HTTPException(status_code=400, detail=err_plan_period)
    new_license_key, err_msg = await lookup_license_activate_status(db, code)
    if err_msg:
        raise HTTPException(status_code=400, detail=err_msg)

    try:
        # 解除当前用户已绑定的授权码（若有），使其可被他人再次激活
        old_lic = await db.execute(
            select(LicenseKey).where(
                LicenseKey.assigned_to == user.id,
                LicenseKey.is_used == True,
            )
        )
        old_license_key = old_lic.scalar_one_or_none()
        if old_license_key:
            old_license_key.is_used = False
            old_license_key.assigned_to = None
            old_license_key.activated_at = None
            await db.flush()

        # 绑定新授权码到当前用户
        new_license_key.is_used = True
        new_license_key.assigned_to = user.id
        new_license_key.activated_at = datetime.now(timezone.utc)
        await db.flush()

        await _bind_license_to_user_and_credential(db, user, new_license_key)
        return {"message": "授权码已更新，账户已使用新授权码激活"}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        err = str(e) if getattr(settings, "ENVIRONMENT", "production") == "development" else "更新授权码失败"
        raise HTTPException(status_code=500, detail=err)


@router.get("/license", response_model=LicenseInfo)
async def get_license(
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    result = await db.execute(
        select(LicenseKey).where(
            LicenseKey.assigned_to == user.id,
            LicenseKey.is_used == True,
            LicenseKey.is_revoked == False,
        ).order_by(LicenseKey.activated_at.desc()).limit(1)
    )
    license_key = result.scalar_one_or_none()
    if not license_key:
        return LicenseInfo(is_activated=False)
    now = datetime.now(timezone.utc)
    days = (license_key.expires_at - now).days if license_key.expires_at > now else 0
    plan_name = period_name = None
    machine_limit = license_key.machine_limit
    concurrent_limit = license_key.concurrent_limit
    pull_limit_monthly = license_key.pull_limit_monthly
    allowed_image_tags = None
    if license_key.plan_id:
        plan_res = await db.execute(select(Plan).where(Plan.id == license_key.plan_id))
        plan = plan_res.scalar_one_or_none()
        if plan:
            plan_name = plan.name
            machine_limit = plan.machine_limit
            concurrent_limit = plan.concurrent_limit
            pull_limit_monthly = plan.pull_limit_monthly
            allowed_image_tags = get_allowed_image_tags(plan.code)
        if license_key.period_id:
            period_res = await db.execute(select(BillingPeriod).where(BillingPeriod.id == license_key.period_id))
            period = period_res.scalar_one_or_none()
            if period:
                period_name = {"monthly": "月付", "quarterly": "季付", "yearly": "年付", "internal": "内测"}.get(period.code, period.code)
    return LicenseInfo(
        is_activated=True,
        plan_type=license_key.plan_type,
        plan_name=plan_name,
        period_name=period_name,
        machine_limit=machine_limit,
        concurrent_limit=concurrent_limit,
        pull_limit_monthly=pull_limit_monthly,
        allowed_image_tags=allowed_image_tags,
        activated_at=license_key.activated_at,
        expires_at=license_key.expires_at,
        days_remaining=max(0, days),
    )


@router.get("/registry-credential", response_model=RegistryCredentialResponse)
async def get_registry_credential(
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    result = await db.execute(
        select(RegistryCredential).where(RegistryCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="尚未激活授权，无法获取凭证")
    lic = (await db.execute(select(LicenseKey).where(LicenseKey.id == cred.license_id))).scalar_one_or_none()
    if lic and lic.is_revoked:
        raise HTTPException(status_code=403, detail="授权已作废")
    if cred.expires_at and cred.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="授权已过期")
    password = decrypt_password(cred.registry_password_enc)
    return RegistryCredentialResponse(
        registry_url=settings.REGISTRY_URL,
        username=cred.registry_username,
        password=password,
        allowed_image_tags=cred.allowed_image_tags,
    )


def _user_can_self_unbind(plan_code: str | None) -> bool:
    return plan_code in ("team", "enterprise", "beta")


@router.get("/machines", response_model=MachineListResponse)
async def list_machines(
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    lic = await db.execute(
        select(LicenseKey).where(
            LicenseKey.assigned_to == user.id,
            LicenseKey.is_used == True,
        ).order_by(LicenseKey.activated_at.desc()).limit(1)
    )
    license_key = lic.scalar_one_or_none()
    if not license_key:
        return MachineListResponse(bindings=[], machine_limit=0, binding_count=0, can_self_unbind=False)
    plan_code = license_key.plan_type
    if license_key.plan_id:
        p = await db.execute(select(Plan).where(Plan.id == license_key.plan_id))
        plan = p.scalar_one_or_none()
        if plan:
            plan_code = plan.code
    machine_limit = license_key.machine_limit or 0
    bindings_q = await db.execute(
        select(MachineBinding).where(
            MachineBinding.license_id == license_key.id,
            MachineBinding.is_active == True,
        ).order_by(MachineBinding.last_heartbeat.desc())
    )
    bindings = bindings_q.scalars().all()
    now = datetime.now(timezone.utc)
    offline_threshold = now - timedelta(hours=24)
    plan_name_for_list = plan_code
    if license_key.plan_id:
        plr = await db.execute(select(Plan).where(Plan.id == license_key.plan_id))
        pl = plr.scalar_one_or_none()
        if pl:
            plan_name_for_list = pl.name
    slots_remaining = max(0, machine_limit - len(bindings)) if machine_limit > 0 else None
    unbind_hint = "需联系管理员" if not _user_can_self_unbind(plan_code) else None
    return MachineListResponse(
        bindings=[
            MachineBindingItem(
                id=b.id,
                machine_id=b.machine_id,
                machine_name=b.machine_name,
                first_seen=b.first_seen,
                last_heartbeat=b.last_heartbeat,
                is_active=b.is_active,
                is_online=b.last_heartbeat >= offline_threshold if b.last_heartbeat else False,
                machine_id_display=(b.machine_id or "")[:8],
            )
            for b in bindings
        ],
        machine_limit=machine_limit,
        binding_count=len(bindings),
        slots_remaining=slots_remaining,
        plan_name=plan_name_for_list,
        can_self_unbind=_user_can_self_unbind(plan_code),
        unbind_hint=unbind_hint,
    )


@router.get("/quota-summary", response_model=QuotaSummaryResponse)
async def get_quota_summary(
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    """
    当前用户本周期各已绑定机器的生成次数概览（用于门户「生成次数」页）。
    """
    lic = await db.execute(
        select(LicenseKey).where(
            LicenseKey.assigned_to == user.id,
            LicenseKey.is_used == True,
            LicenseKey.is_revoked == False,
        ).order_by(LicenseKey.activated_at.desc()).limit(1)
    )
    license_key = lic.scalar_one_or_none()
    if not license_key:
        return QuotaSummaryResponse(machines=[])
    plan_code = license_key.plan_type
    if license_key.plan_id:
        p = await db.execute(select(Plan).where(Plan.id == license_key.plan_id))
        plan = p.scalar_one_or_none()
        if plan:
            plan_code = plan.code
    bounds = get_cycle_bounds(license_key.activated_at)
    if not bounds:
        return QuotaSummaryResponse(machines=[])
    cycle_start, cycle_end = bounds
    next_reset = cycle_end + timedelta(days=1)
    bindings_q = await db.execute(
        select(MachineBinding).where(
            MachineBinding.license_id == license_key.id,
            MachineBinding.is_active == True,
        ).order_by(MachineBinding.last_heartbeat.desc())
    )
    bindings = bindings_q.scalars().all()
    machines_out = []
    for b in bindings:
        types_out = []
        for ct in CONTENT_TYPES:
            lim = get_quota_limit(plan_code or "basic", ct)
            q = await db.execute(
                select(GenerationQuota).where(
                    GenerationQuota.license_id == license_key.id,
                    GenerationQuota.machine_id == b.machine_id,
                    GenerationQuota.content_type == ct,
                    GenerationQuota.cycle_start == cycle_start,
                )
            )
            row = q.scalar_one_or_none()
            used = row.used_count if row else 0
            types_out.append(QuotaTypeItem(
                content_type=ct,
                used=used,
                limit=lim,
                exhausted=lim > 0 and used >= lim,
            ))
        machines_out.append(QuotaMachineItem(
            machine_id=b.machine_id or "",
            machine_id_display=(b.machine_id or "")[:8],
            machine_name=b.machine_name,
            types=types_out,
        ))
    return QuotaSummaryResponse(
        cycle_start=cycle_start.isoformat(),
        cycle_end=cycle_end.isoformat(),
        next_reset_date=next_reset.isoformat(),
        machines=machines_out,
    )


def _start_of_current_month_utc() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/pull-quota", response_model=PullQuotaResponse)
async def get_pull_quota(
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    """
    门户「本月拉取次数」：已用、上限、重置日（自然月）。未激活或无凭证返回 used=0, limit=None。
    """
    r = await db.execute(
        select(RegistryCredential, LicenseKey.pull_limit_monthly)
        .outerjoin(LicenseKey, RegistryCredential.license_id == LicenseKey.id)
        .where(RegistryCredential.user_id == user.id)
    )
    row = r.one_or_none()
    if not row:
        return PullQuotaResponse(used=0, limit=None, reset_at=None)
    cred, pull_limit = row[0], row[1]
    start_of_month = _start_of_current_month_utc()
    reset_at = cred.pull_count_reset_at
    if reset_at is not None and getattr(reset_at, "tzinfo", None) is None:
        try:
            from datetime import timezone
            reset_at = reset_at.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if reset_at is None or start_of_month > reset_at:
        cred.pull_count_this_month = 0
        cred.pull_count_reset_at = start_of_month
        await db.flush()
    used = cred.pull_count_this_month or 0
    limit = pull_limit if pull_limit is not None else None
    next_month = (start_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    return PullQuotaResponse(
        used=used,
        limit=limit,
        reset_at=next_month.strftime("%Y-%m-%d"),
    )


@router.delete("/machines/{binding_id}")
async def unbind_machine(
    binding_id: str,
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    lic = await db.execute(
        select(LicenseKey).where(
            LicenseKey.assigned_to == user.id,
            LicenseKey.is_used == True,
            LicenseKey.is_revoked == False,
        ).order_by(LicenseKey.activated_at.desc()).limit(1)
    )
    license_key = lic.scalar_one_or_none()
    if not license_key:
        raise HTTPException(status_code=404, detail="未激活授权")
    plan_code = license_key.plan_type
    if license_key.plan_id:
        p = await db.execute(select(Plan).where(Plan.id == license_key.plan_id))
        plan = p.scalar_one_or_none()
        if plan:
            plan_code = plan.code
    if not _user_can_self_unbind(plan_code):
        raise HTTPException(status_code=403, detail="当前套餐不支持自助解绑，请联系管理员")
    b = await db.execute(
        select(MachineBinding).where(
            MachineBinding.id == binding_id,
            MachineBinding.license_id == license_key.id,
            MachineBinding.is_active == True,
        )
    )
    binding = b.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定记录不存在或已解绑")
    binding.is_active = False
    await db.flush()
    return {"message": "已解绑"}


# 全栈方案 §5.8：解绑 container-token 体系下的机器（按 machine_id）
@router.delete("/container-machines/{machine_id}")
async def unbind_container_machine(
    machine_id: str,
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    """
    解绑当前用户下指定 machine_id 的机器。
    同时将该 user_id + machine_id 的 container_tokens 置 is_revoked=TRUE。
    注意：被解绑机器的令牌需等待自然过期（最长 24 小时）才完全失效（F6）。
    """
    mid = machine_id.strip()
    await db.execute(
        delete(ContainerMachineBinding).where(
            ContainerMachineBinding.user_id == user.id,
            ContainerMachineBinding.machine_id == mid,
        )
    )
    await db.execute(
        update(ContainerToken)
        .where(
            ContainerToken.user_id == user.id,
            ContainerToken.machine_id == mid,
        )
        .values(is_revoked=True)
    )
    await db.flush()
    return {"ok": True}

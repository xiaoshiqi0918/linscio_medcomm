from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import ProgrammingError, OperationalError
import io
import csv

from app.database import get_db
from app.models import PortalUser, AdminUser, LicenseKey, ModuleDefinition, RegistryCredential, Plan, BillingPeriod, MachineBinding, InstanceHeartbeat, GenerationQuota, OperationLog, Order
from app.schemas.admin import (
    AdminLoginRequest,
    UserListItem,
    UserUpdateRequest,
    LicenseListItem,
    LicenseDetailItem,
    LicenseBatchCreate,
    ModuleListItem,
    ModuleUpdateRequest,
    ModuleCreateRequest,
    LicenseExtendRequest,
    PlanOption,
    PlanOptionDetail,
    PlanManageItem,
    PlanCreate,
    PlanUpdate,
    PeriodOption,
    PeriodManageItem,
    BillingPeriodCreate,
    BillingPeriodUpdate,
    StatsOverview,
    RegistrationTrendItem,
    LicenseStatusCounts,
    PlanCountItem,
    PullTopItem,
    QuotaResetRequest,
)
from app.schemas.auth import TokenResponse
from app.services.auth_service import hash_password, verify_password
from app.services.license_service import create_license_batch, create_license_batch_v2, get_module_mask, generate_license_code_v2, ensure_controlled_modules
from app.services.registry_service import get_allowed_image_tags, remove_from_htpasswd, write_htpasswd, encrypt_password, generate_registry_password, trigger_registry_reload
from app.services.quota_service import get_cycle_bounds, get_quota_limit, reset_quota_for_license, CONTENT_TYPES as QUOTA_CONTENT_TYPES
from app.services.machine_binding_service import get_replace_period_start, can_replace_machine
from app.services.account_service import compute_account_status
from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])
admin_bearer = HTTPBearer(auto_error=False)

ADMIN_JWT_SECRET = settings.JWT_SECRET_KEY + "_admin"  # 与门户 JWT 区分
PLAN_DEFAULT_MACHINE_LIMIT = {"personal": 1, "team": 5, "enterprise": 0}


def create_admin_token(subject: str) -> str:
    from jose import jwt
    from datetime import timedelta
    expire = datetime.now(timezone.utc) + timedelta(minutes=getattr(settings, "JWT_EXPIRE_MINUTES_ADMIN", 480))
    return jwt.encode(
        {"sub": subject, "exp": expire},
        ADMIN_JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_admin_token(token: str) -> str | None:
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer),
    db: AsyncSession = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录")
    admin_id = decode_admin_token(credentials.credentials)
    if not admin_id:
        raise HTTPException(status_code=401, detail="token 无效")
    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    admin = result.scalar_one_or_none()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=403, detail="无权限")
    return admin


def require_super(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    """仅 super 可执行作废、强制解绑等敏感操作（8.2）。"""
    if admin.scope != "super":
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")
    return admin


@router.post("/auth/login", response_model=TokenResponse)
async def admin_login(data: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminUser).where(AdminUser.username == data.username))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")
    token = create_admin_token(str(admin.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.get("/users", response_model=list[UserListItem])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=500),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    q = select(PortalUser)
    if search:
        q = q.where(PortalUser.username.ilike(f"%{search}%"))
    q = q.offset(skip).limit(limit).order_by(PortalUser.created_at.desc())
    result = await db.execute(q)
    users = result.scalars().all()
    return [
        UserListItem(
            id=u.id,
            username=u.username,
            email=u.email,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login=u.last_login,
            plan=getattr(u, "plan", None),
            maintenance_until=getattr(u, "maintenance_until", None),
            machine_limit=getattr(u, "machine_limit", None),
            account_status=compute_account_status(u),
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserListItem)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(select(PortalUser).where(PortalUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserListItem(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
        plan=getattr(user, "plan", None),
        maintenance_until=getattr(user, "maintenance_until", None),
        machine_limit=getattr(user, "machine_limit", None),
        account_status=compute_account_status(user),
    )


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(select(PortalUser).where(PortalUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.plan is not None:
        if data.plan not in ("personal", "team", "enterprise"):
            raise HTTPException(status_code=400, detail="plan 须为 personal / team / enterprise 之一")
        user.plan = data.plan
        if data.machine_limit is None:
            user.machine_limit = PLAN_DEFAULT_MACHINE_LIMIT.get(data.plan, 1)
    if data.maintenance_until is not None:
        user.maintenance_until = data.maintenance_until
    if data.machine_limit is not None:
        user.machine_limit = data.machine_limit
    await db.flush()
    return {"message": "ok"}


@router.post("/users/{user_id}/refresh-credential")
async def refresh_user_credential(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """刷新该用户的镜像仓库凭证：按当前套餐重算 module_mask、allowed_image_tags，并重新生成密码写入 htpasswd。仅当用户已激活且有关联授权码时有效。"""
    result = await db.execute(select(PortalUser).where(PortalUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    cred_result = await db.execute(select(RegistryCredential).where(RegistryCredential.user_id == user_id))
    cred = cred_result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=400, detail="该用户暂无镜像仓库凭证")
    if not cred.license_id:
        raise HTTPException(status_code=400, detail="该用户凭证未关联授权码，无法刷新")
    lk_result = await db.execute(select(LicenseKey).where(LicenseKey.id == cred.license_id))
    lk = lk_result.scalar_one_or_none()
    if not lk:
        raise HTTPException(status_code=400, detail="关联的授权码不存在")
    plan_code = "basic"
    if lk.plan_id:
        plan_result = await db.execute(select(Plan).where(Plan.id == lk.plan_id))
        plan = plan_result.scalar_one_or_none()
        if plan:
            plan_code = plan.code
    else:
        plan_code = lk.plan_type or "basic"
    cred.allowed_image_tags = get_allowed_image_tags(plan_code)
    lk.module_mask = await get_module_mask(db, plan_code)
    new_password = generate_registry_password()
    if write_htpasswd(cred.registry_username, new_password):
        cred.registry_password_enc = encrypt_password(new_password)
    await db.flush()
    trigger_registry_reload()
    return {"message": "已更新该用户凭证", "updated": 1}


@router.patch("/orders/{order_id}/mark-paid")
async def mark_order_paid(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """全栈方案 §5.6：标记线下支付为已付款；若为首次购买/续费则同步更新用户 plan、maintenance_until。"""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="仅可标记 pending 订单为已付款")
    now = datetime.now(timezone.utc)
    order.status = "paid"
    order.paid_at = now
    user_result = await db.execute(select(PortalUser).where(PortalUser.id == order.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        if order.order_type == "initial_license":
            user.plan = order.plan
            user.license_paid_at = now
            user.maintenance_until = now + timedelta(days=365)
        elif order.order_type == "maintenance_renewal":
            base = user.maintenance_until if user.maintenance_until and user.maintenance_until > now else now
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            user.maintenance_until = base + timedelta(days=365)
    await db.flush()
    return {"message": "ok", "order_id": order_id}


@router.get("/plans", response_model=list[PlanOptionDetail])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """套餐列表，用于批量生成授权码下拉；含机器数/并发数/月拉取上限（分级授权与镜像管控）。"""
    result = await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.price_monthly.asc()))
    plans = result.scalars().all()
    return [
        PlanOptionDetail(
            code=p.code,
            name=p.name,
            machine_limit=p.machine_limit,
            concurrent_limit=p.concurrent_limit,
            pull_limit_monthly=p.pull_limit_monthly,
        )
        for p in plans
    ]


@router.get("/billing-periods", response_model=list[PeriodOption])
async def list_billing_periods(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """付费周期列表，用于批量生成授权码。"""
    result = await db.execute(select(BillingPeriod).order_by(BillingPeriod.months.asc()))
    periods = result.scalars().all()
    name_fallback = {"monthly": "月付", "quarterly": "季付", "yearly": "年付", "internal": "内测"}
    return [
        PeriodOption(code=p.code, name=(p.name or name_fallback.get(p.code, p.code)))
        for p in periods
    ]


# ---------- 套餐与周期管理（第一优先级：在后台配置） ----------
def _is_migration_needed_error(exc: BaseException) -> bool:
    """是否为「缺少表/列」类数据库错误，需执行迁移。"""
    base = getattr(exc, "orig", exc)
    msg = (getattr(base, "message", None) or (base.args[0] if base.args else None) or str(exc))
    if not isinstance(msg, str):
        msg = str(msg)
    msg = msg.lower()
    if "billing_periods" in msg and ("name" in msg or "column" in msg):
        return True
    if "does not exist" in msg or "undefined_column" in msg:
        return True
    return False


@router.get("/plans/manage", response_model=list[PlanManageItem])
async def list_plans_manage(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """管理用：返回全部套餐（含停用），用于套餐与周期页。"""
    try:
        result = await db.execute(select(Plan).order_by(Plan.price_monthly.asc()))
        plans = result.scalars().all()
        return [
            PlanManageItem(
                id=p.id,
                code=p.code,
                name=p.name,
                plan_char=p.plan_char,
                machine_limit=p.machine_limit,
                concurrent_limit=p.concurrent_limit,
                pull_limit_monthly=p.pull_limit_monthly,
                price_monthly=float(p.price_monthly) if p.price_monthly is not None else 0,
                is_active=p.is_active,
            )
            for p in plans
        ]
    except (ProgrammingError, OperationalError, Exception) as e:
        if _is_migration_needed_error(e):
            raise HTTPException(
                status_code=503,
                detail="数据库需先执行迁移。请执行：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_billing_period_name.sql 或 python api/scripts/add_billing_period_name_column.py",
            )
        raise


@router.post("/plans", response_model=PlanManageItem)
async def create_plan(
    data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """新增套餐。"""
    from decimal import Decimal
    r = await db.execute(select(Plan).where(Plan.code == data.code))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="套餐 code 已存在")
    r = await db.execute(select(Plan).where(Plan.plan_char == data.plan_char))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="授权码字符 plan_char 已被其他套餐使用")
    p = Plan(
        code=data.code,
        name=data.name,
        plan_char=data.plan_char,
        machine_limit=data.machine_limit,
        concurrent_limit=data.concurrent_limit,
        pull_limit_monthly=data.pull_limit_monthly,
        price_monthly=Decimal(str(data.price_monthly)),
        is_active=data.is_active,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return PlanManageItem(
        id=p.id, code=p.code, name=p.name, plan_char=p.plan_char,
        machine_limit=p.machine_limit, concurrent_limit=p.concurrent_limit,
        pull_limit_monthly=p.pull_limit_monthly,
        price_monthly=float(p.price_monthly) if p.price_monthly is not None else 0,
        is_active=p.is_active,
    )


@router.patch("/plans/{plan_id}", response_model=PlanManageItem)
async def update_plan(
    plan_id: str,
    data: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """更新套餐。"""
    r = await db.execute(select(Plan).where(Plan.id == plan_id))
    p = r.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="套餐不存在")
    from decimal import Decimal
    if data.name is not None:
        p.name = data.name
    if data.plan_char is not None:
        r2 = await db.execute(select(Plan).where(Plan.plan_char == data.plan_char, Plan.id != plan_id))
        if r2.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="授权码字符 plan_char 已被其他套餐使用")
        p.plan_char = data.plan_char
    if data.machine_limit is not None:
        p.machine_limit = data.machine_limit
    if data.concurrent_limit is not None:
        p.concurrent_limit = data.concurrent_limit
    if data.pull_limit_monthly is not None:
        p.pull_limit_monthly = data.pull_limit_monthly
    if data.price_monthly is not None:
        p.price_monthly = Decimal(str(data.price_monthly))
    if data.is_active is not None:
        p.is_active = data.is_active
    await db.commit()
    await db.refresh(p)
    return PlanManageItem(
        id=p.id, code=p.code, name=p.name, plan_char=p.plan_char,
        machine_limit=p.machine_limit, concurrent_limit=p.concurrent_limit,
        pull_limit_monthly=p.pull_limit_monthly,
        price_monthly=float(p.price_monthly) if p.price_monthly is not None else 0,
        is_active=p.is_active,
    )


@router.get("/billing-periods/manage", response_model=list[PeriodManageItem])
async def list_billing_periods_manage(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """管理用：返回全部付费周期，用于套餐与周期页。"""
    try:
        result = await db.execute(select(BillingPeriod).order_by(BillingPeriod.months.asc()))
        periods = result.scalars().all()
        return [
            PeriodManageItem(
                id=p.id,
                code=p.code,
                name=p.name,
                period_char=p.period_char,
                months=p.months,
                discount_rate=float(p.discount_rate) if p.discount_rate is not None else 1,
            )
            for p in periods
        ]
    except (ProgrammingError, OperationalError, Exception) as e:
        if _is_migration_needed_error(e):
            raise HTTPException(
                status_code=503,
                detail="数据库需先执行迁移：billing_periods 表缺少 name 列。请在 portal-system 目录执行：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_billing_period_name.sql 或 cd api && python scripts/add_billing_period_name_column.py",
            )
        raise


@router.post("/billing-periods", response_model=PeriodManageItem)
async def create_billing_period(
    data: BillingPeriodCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """新增付费周期。"""
    from decimal import Decimal
    r = await db.execute(select(BillingPeriod).where(BillingPeriod.code == data.code))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="周期 code 已存在")
    r = await db.execute(select(BillingPeriod).where(BillingPeriod.period_char == data.period_char))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="授权码字符 period_char 已被其他周期使用")
    p = BillingPeriod(
        code=data.code,
        name=data.name,
        period_char=data.period_char,
        months=data.months,
        discount_rate=Decimal(str(data.discount_rate)),
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return PeriodManageItem(
        id=p.id, code=p.code, name=p.name, period_char=p.period_char,
        months=p.months, discount_rate=float(p.discount_rate) if p.discount_rate is not None else 1,
    )


@router.patch("/billing-periods/{period_id}", response_model=PeriodManageItem)
async def update_billing_period(
    period_id: str,
    data: BillingPeriodUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """更新付费周期。"""
    r = await db.execute(select(BillingPeriod).where(BillingPeriod.id == period_id))
    p = r.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="周期不存在")
    from decimal import Decimal
    if data.name is not None:
        p.name = data.name
    if data.period_char is not None:
        r2 = await db.execute(select(BillingPeriod).where(BillingPeriod.period_char == data.period_char, BillingPeriod.id != period_id))
        if r2.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="授权码字符 period_char 已被其他周期使用")
        p.period_char = data.period_char
    if data.months is not None:
        p.months = data.months
    if data.discount_rate is not None:
        p.discount_rate = Decimal(str(data.discount_rate))
    await db.commit()
    await db.refresh(p)
    return PeriodManageItem(
        id=p.id, code=p.code, name=p.name, period_char=p.period_char,
        months=p.months, discount_rate=float(p.discount_rate) if p.discount_rate is not None else 1,
    )


# ---------- 默认套餐与周期（管理后台一键加载） ----------
DEFAULT_PLANS = [
    ("basic", "基础版", "B", 1, 1, 20, "49.9"),
    ("professional", "专业版", "P", 1, 1, 30, "149.9"),
    ("team", "团队版", "T", 10, 10, None, "999.9"),
    ("enterprise", "旗舰版", "E", 0, 0, None, "9999.9"),
    ("beta", "内测版", "D", 0, 0, None, "0"),
]
DEFAULT_BILLING_PERIODS = [
    ("monthly", "月付", "M", 1, "1.00"),
    ("quarterly", "季付", "Q", 3, "0.90"),
    ("yearly", "年付", "Y", 12, "0.80"),
    ("internal", "内测", "I", 1, "0.00"),
]


@router.post("/plans-periods/seed-defaults")
async def seed_default_plans_periods(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """加载默认套餐与周期（与 seed_plans_periods_modules 中预置一致）。已存在的 code 不会覆盖，仅补充缺失项。"""
    from decimal import Decimal
    added_plans = 0
    added_periods = 0
    for code, name, plan_char, ml, cl, plm, price in DEFAULT_PLANS:
        r = await db.execute(select(Plan).where(Plan.code == code))
        if r.scalar_one_or_none():
            continue
        db.add(Plan(
            code=code, name=name, plan_char=plan_char,
            machine_limit=ml, concurrent_limit=cl, pull_limit_monthly=plm,
            price_monthly=Decimal(price),
        ))
        added_plans += 1
    await db.flush()
    for code, period_name, period_char, months, rate in DEFAULT_BILLING_PERIODS:
        r = await db.execute(select(BillingPeriod).where(BillingPeriod.code == code))
        if r.scalar_one_or_none():
            continue
        db.add(BillingPeriod(
            code=code, name=period_name, period_char=period_char,
            months=months, discount_rate=Decimal(rate),
        ))
        added_periods += 1
    await db.commit()
    return {"message": "已加载默认套餐与周期", "added_plans": added_plans, "added_periods": added_periods}


@router.get("/licenses", response_model=list[LicenseListItem])
async def list_licenses(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(LicenseKey, Plan, BillingPeriod, PortalUser)
        .outerjoin(Plan, LicenseKey.plan_id == Plan.id)
        .outerjoin(BillingPeriod, LicenseKey.period_id == BillingPeriod.id)
        .outerjoin(PortalUser, LicenseKey.assigned_to == PortalUser.id)
        .order_by(LicenseKey.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()
    period_names = {"monthly": "月付", "quarterly": "季付", "yearly": "年付", "internal": "内测"}
    now = datetime.now(timezone.utc)
    license_ids = [lk.id for lk, _, _, _ in rows]

    machine_counts = {}
    instance_counts = {}
    pull_used = {}
    if license_ids:
        mb = await db.execute(
            select(MachineBinding.license_id, func.count(MachineBinding.id))
            .where(MachineBinding.license_id.in_(license_ids), MachineBinding.is_active == True)
            .group_by(MachineBinding.license_id)
        )
        machine_counts = {r[0]: r[1] for r in mb.all()}
        ih = await db.execute(
            select(InstanceHeartbeat.license_id, func.count(InstanceHeartbeat.id))
            .where(InstanceHeartbeat.license_id.in_(license_ids), InstanceHeartbeat.is_active == True)
            .group_by(InstanceHeartbeat.license_id)
        )
        instance_counts = {r[0]: r[1] for r in ih.all()}
        rc = await db.execute(
            select(RegistryCredential.license_id, RegistryCredential.pull_count_this_month).where(
                RegistryCredential.license_id.in_(license_ids)
            )
        )
        pull_used = {r[0]: (r[1] or 0) for r in rc.all()}

    def _period_display(period):
        if not period:
            return None
        return period.name or period_names.get(period.code, period.code)

    out = []
    for lk, plan, period, user in rows:
        status = "已作废" if lk.is_revoked else ("已激活" if lk.is_used else ("已过期" if lk.expires_at and lk.expires_at <= now else "未使用"))
        out.append(LicenseListItem(
            id=str(lk.id),
            code=str(lk.code) if lk.code else "",
            plan_type=lk.plan_type or "",
            expires_at=lk.expires_at,
            created_at=lk.created_at,
            created_by=lk.created_by or "",
            assigned_to=str(lk.assigned_to) if lk.assigned_to else None,
            is_used=lk.is_used,
            is_revoked=lk.is_revoked,
            activated_at=lk.activated_at,
            plan_name=plan.name if plan else None,
            period_name=_period_display(period),
            notes=lk.notes,
            machine_limit=lk.machine_limit,
            concurrent_limit=lk.concurrent_limit,
            pull_limit_monthly=lk.pull_limit_monthly,
            assigned_username=user.username if user else None,
            status=status,
            machine_bound_count=machine_counts.get(lk.id),
            instance_active_count=instance_counts.get(lk.id),
            pull_used_this_month=pull_used.get(lk.id),
        ))
    return out


@router.get("/licenses/export")
async def export_licenses_csv(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(LicenseKey, Plan, BillingPeriod)
        .outerjoin(Plan, LicenseKey.plan_id == Plan.id)
        .outerjoin(BillingPeriod, LicenseKey.period_id == BillingPeriod.id)
        .order_by(LicenseKey.created_at.desc())
    )
    rows = result.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["授权码", "套餐", "周期", "机器数", "并发数", "月拉取上限", "有效期至", "生成时间", "备注", "创建人", "绑定用户ID", "状态", "激活时间"])
    period_names = {"monthly": "月付", "quarterly": "季付", "yearly": "年付", "internal": "内测"}
    for lk, plan, period in rows:
        plan_name = plan.name if plan else (lk.plan_type or "—")
        period_name = period_names.get(period.code, period.code) if period else "—"
        status = "已作废" if lk.is_revoked else ("已激活" if lk.is_used else ("已过期" if lk.expires_at and lk.expires_at < datetime.now(timezone.utc) else "未使用"))
        writer.writerow([
            lk.code,
            plan_name,
            period_name,
            lk.machine_limit if lk.machine_limit else "∞",
            lk.concurrent_limit if lk.concurrent_limit else "∞",
            lk.pull_limit_monthly if lk.pull_limit_monthly is not None else "∞",
            lk.expires_at.isoformat() if lk.expires_at else "",
            lk.created_at.isoformat() if lk.created_at else "",
            (lk.notes or "").strip(),
            lk.created_by,
            lk.assigned_to or "",
            status,
            lk.activated_at.isoformat() if lk.activated_at else "",
        ])
    output.seek(0)
    filename = f"licenses_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/licenses/{license_id}", response_model=LicenseDetailItem)
async def get_license_detail(
    license_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(LicenseKey, Plan, BillingPeriod, PortalUser)
        .outerjoin(Plan, LicenseKey.plan_id == Plan.id)
        .outerjoin(BillingPeriod, LicenseKey.period_id == BillingPeriod.id)
        .outerjoin(PortalUser, LicenseKey.assigned_to == PortalUser.id)
        .where(LicenseKey.id == license_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="授权码不存在")
    lk, plan, period, user = row
    period_names = {"monthly": "月付", "quarterly": "季付", "yearly": "年付", "internal": "内测"}
    now = datetime.now(timezone.utc)
    status = "已作废" if lk.is_revoked else ("已激活" if lk.is_used else ("已过期" if lk.expires_at <= now else "未使用"))
    machine_bound = await db.scalar(select(func.count(MachineBinding.id)).where(MachineBinding.license_id == license_id, MachineBinding.is_active == True))
    instance_active = await db.scalar(select(func.count(InstanceHeartbeat.id)).where(InstanceHeartbeat.license_id == license_id, InstanceHeartbeat.is_active == True))
    cred = await db.scalar(select(RegistryCredential).where(RegistryCredential.license_id == license_id))
    pull_used = cred.pull_count_this_month if cred else None
    return LicenseDetailItem(
        id=lk.id,
        code=lk.code,
        plan_type=lk.plan_type or "",
        expires_at=lk.expires_at,
        created_at=lk.created_at,
        created_by=lk.created_by,
        assigned_to=lk.assigned_to,
        is_used=lk.is_used,
        is_revoked=lk.is_revoked,
        activated_at=lk.activated_at,
        plan_name=plan.name if plan else None,
        period_name=period_names.get(period.code, period.code) if period else None,
        notes=lk.notes,
        machine_limit=lk.machine_limit,
        concurrent_limit=lk.concurrent_limit,
        pull_limit_monthly=lk.pull_limit_monthly,
        assigned_username=user.username if user else None,
        status=status,
        machine_bound_count=machine_bound or 0,
        instance_active_count=instance_active or 0,
        pull_used_this_month=pull_used,
    )


@router.get("/licenses/{license_id}/quota-usage")
async def get_license_quota_usage(
    license_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """管理端：授权码详情页查看每台绑定机器的生成次数消耗（当前 90 天周期）。"""
    r = await db.execute(
        select(LicenseKey, Plan).outerjoin(Plan, LicenseKey.plan_id == Plan.id).where(LicenseKey.id == license_id)
    )
    row = r.first()
    if not row:
        raise HTTPException(status_code=404, detail="授权码不存在")
    lk, plan = row
    plan_code = plan.code if plan else (lk.plan_type or "basic")
    bounds = get_cycle_bounds(lk.activated_at)
    if not bounds:
        return {"cycle_start": None, "cycle_end": None, "machines": [], "totals": {}}
    cycle_start, cycle_end = bounds

    machines_result = await db.execute(
        select(MachineBinding).where(MachineBinding.license_id == license_id, MachineBinding.is_active == True)
    )
    machines = machines_result.scalars().all()
    out_machines = []
    totals_used = {ct: 0 for ct in QUOTA_CONTENT_TYPES}
    limits_per_type = {ct: get_quota_limit(plan_code, ct) for ct in QUOTA_CONTENT_TYPES}
    totals_limit = {ct: limits_per_type[ct] * len(machines) if limits_per_type[ct] else None for ct in QUOTA_CONTENT_TYPES}

    for mb in machines:
        per_type = {}
        for ct in QUOTA_CONTENT_TYPES:
            lim = limits_per_type[ct]
            q = await db.execute(
                select(GenerationQuota).where(
                    GenerationQuota.license_id == license_id,
                    GenerationQuota.machine_id == mb.machine_id,
                    GenerationQuota.content_type == ct,
                    GenerationQuota.cycle_start == cycle_start,
                )
            )
            quota_row = q.scalar_one_or_none()
            used = quota_row.used_count if quota_row else 0
            per_type[ct] = {"used": used, "limit": lim, "exhausted": lim > 0 and used >= lim}
            totals_used[ct] += used
        out_machines.append({
            "machine_id": mb.machine_id,
            "machine_name": mb.machine_name,
            "schola": per_type["schola"],
            "medcomm": per_type["medcomm"],
            "qcc": per_type["qcc"],
        })

    totals = {ct: {"used": totals_used[ct], "limit": totals_limit[ct]} for ct in QUOTA_CONTENT_TYPES}
    return {
        "cycle_start": cycle_start.isoformat(),
        "cycle_end": cycle_end.isoformat(),
        "machines": out_machines,
        "totals": totals,
    }


@router.post("/quota/reset")
async def admin_quota_reset(
    data: QuotaResetRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """手动重置指定授权码（及可选机器）当前 90 天周期的生成次数。"""
    r = await db.execute(select(LicenseKey).where(LicenseKey.id == data.license_id))
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="授权码不存在")
    count = await reset_quota_for_license(db, data.license_id, data.machine_id)
    return {"message": "已重置", "reset_count": count}


@router.get("/licenses/preview")
async def preview_license_code(
    plan_code: str = Query(..., description="套餐 code"),
    period_code: str = Query(..., description="周期 code"),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """批量生成前预览一条样例授权码（不写入数据库）。"""
    plan_res = await db.execute(select(Plan).where(Plan.code == plan_code))
    plan = plan_res.scalar_one_or_none()
    period_res = await db.execute(select(BillingPeriod).where(BillingPeriod.code == period_code))
    period = period_res.scalar_one_or_none()
    if not plan or not period:
        raise HTTPException(status_code=400, detail="套餐或周期不存在")
    sample_code = generate_license_code_v2(plan.plan_char, period.period_char)
    return {"sample_code": sample_code}


@router.post("/licenses/batch")
async def batch_create_licenses(
    data: LicenseBatchCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    if data.plan_code and data.period_code:
        try:
            keys = await create_license_batch_v2(
                db, data.count, data.plan_code, data.period_code, admin.username, data.notes
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        keys = await create_license_batch(
            db, data.count, data.months_valid, data.plan_type, admin.username, data.notes
        )
    return {"created": len(keys), "codes": [k.code for k in keys]}


@router.patch("/licenses/{license_id}")
async def revoke_license(
    license_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_super),
):
    result = await db.execute(select(LicenseKey).where(LicenseKey.id == license_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="授权码不存在")
    # 允许作废已激活授权码；作废后凭证与拉取立即失效（proxy/token/凭证接口会校验 is_revoked）
    key.is_revoked = True
    # 数据互通：凭证立即过期 + 从 htpasswd 删除，Registry 立即拒绝
    cred_result = await db.execute(
        select(RegistryCredential).where(RegistryCredential.license_id == license_id)
    )
    cred = cred_result.scalar_one_or_none()
    if cred:
        cred.expires_at = datetime.now(timezone.utc)
        remove_from_htpasswd(cred.registry_username)
    db.add(
        OperationLog(
            operator=admin.username,
            action="revoke_license",
            target=license_id,
            detail={"code": key.code, "was_used": key.is_used},
        )
    )
    await db.flush()
    return {"message": "已作废"}


@router.delete("/licenses/{license_id}/machines/{binding_id}")
async def admin_unbind_machine(
    license_id: str,
    binding_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_super),
):
    """管理员解绑机器。基础版/专业版受每周期更换次数限制（8.2）。"""
    r = await db.execute(
        select(LicenseKey, Plan).outerjoin(Plan, LicenseKey.plan_id == Plan.id).where(LicenseKey.id == license_id)
    )
    row = r.first()
    if not row:
        raise HTTPException(status_code=404, detail="授权码不存在")
    lk, plan = row
    plan_code = plan.code if plan else (lk.plan_type or "basic")
    current_period = get_replace_period_start(lk.activated_at)
    if lk.replace_period_start is None or (current_period and lk.replace_period_start < current_period):
        lk.replace_period_start = current_period
        lk.replace_count_used = 0
    allowed, err = can_replace_machine(
        plan_code, lk.replace_period_start, lk.replace_count_used, current_period
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=err or "本周期更换次数已用完")
    b = await db.execute(
        select(MachineBinding).where(
            MachineBinding.id == binding_id,
            MachineBinding.license_id == license_id,
            MachineBinding.is_active == True,
        )
    )
    binding = b.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定记录不存在或已解绑")
    binding.is_active = False
    lk.replace_count_used = (lk.replace_count_used or 0) + 1
    await db.flush()
    return {"message": "已解绑"}


@router.patch("/licenses/{license_id}/extend")
async def extend_license(
    license_id: str,
    data: LicenseExtendRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(select(LicenseKey).where(LicenseKey.id == license_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="授权码不存在")
    months = max(1, min(12, data.months))
    new_expires = key.expires_at + timedelta(days=months * 30)
    key.expires_at = new_expires
    cred_result = await db.execute(
        select(RegistryCredential).where(RegistryCredential.license_id == license_id)
    )
    cred = cred_result.scalar_one_or_none()
    if cred:
        cred.expires_at = new_expires
    await db.flush()
    return {"message": "已延期", "expires_at": new_expires.isoformat()}


@router.get("/modules", response_model=list[ModuleListItem])
async def list_modules(
    controlled_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    q = select(ModuleDefinition).order_by(ModuleDefinition.sort_order, ModuleDefinition.bit_position)
    if controlled_only:
        q = q.where(ModuleDefinition.is_controlled == True)
    result = await db.execute(q)
    return result.scalars().all()


@router.patch("/modules/{module_id}", response_model=ModuleListItem)
async def update_module(
    module_id: str,
    data: ModuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(select(ModuleDefinition).where(ModuleDefinition.id == module_id))
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="模块不存在")
    if data.basic_enabled is not None:
        mod.basic_enabled = data.basic_enabled
    if data.pro_enabled is not None:
        mod.pro_enabled = data.pro_enabled
    if data.team_enabled is not None:
        mod.team_enabled = data.team_enabled
    if data.enterprise_enabled is not None:
        mod.enterprise_enabled = data.enterprise_enabled
    if data.beta_enabled is not None:
        mod.beta_enabled = data.beta_enabled
    if data.sort_order is not None:
        mod.sort_order = data.sort_order
    await db.flush()
    return mod


@router.post("/modules/seed-controlled")
async def seed_controlled_modules(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """一键将 6 个受控模块写入模块授权配置；已存在的 code 不会重复插入。"""
    added = await ensure_controlled_modules(db)
    await db.commit()
    return {"message": "已初始化受控模块", "added": added}


@router.post("/modules", response_model=ModuleListItem)
async def create_module(
    data: ModuleCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    existing = await db.execute(select(ModuleDefinition).where(ModuleDefinition.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="模块标识已存在")
    r = await db.execute(
        select(func.max(ModuleDefinition.bit_position)).where(ModuleDefinition.bit_position >= 0)
    )
    max_bit = r.scalar()
    next_bit = (max_bit if max_bit is not None else -1) + 1
    mod = ModuleDefinition(
        code=data.code,
        name=data.name,
        bit_position=next_bit,
        is_controlled=True,
        basic_enabled=data.basic_enabled,
        pro_enabled=data.pro_enabled,
        team_enabled=data.team_enabled,
        enterprise_enabled=data.enterprise_enabled,
        beta_enabled=data.beta_enabled,
        sort_order=next_bit,
    )
    db.add(mod)
    await db.flush()
    return mod


@router.post("/registry-credentials/sync-modules")
async def sync_registry_credentials_modules(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """批量更新凭证：按当前套餐刷新 allowed_image_tags、module_mask，并重新生成密码写入 htpasswd（8.3 ④）。"""
    result = await db.execute(
        select(RegistryCredential).where(RegistryCredential.license_id.isnot(None))
    )
    creds = result.scalars().all()
    license_ids = {c.license_id for c in creds}
    licenses_result = await db.execute(select(LicenseKey).where(LicenseKey.id.in_(license_ids)))
    licenses = {lk.id: lk for lk in licenses_result.scalars().all()}
    plan_ids = {lk.plan_id for lk in licenses.values() if lk.plan_id}
    if plan_ids:
        plans_result = await db.execute(select(Plan).where(Plan.id.in_(plan_ids)))
        plans_map = {p.id: p.code for p in plans_result.scalars().all()}
    else:
        plans_map = {}
    updated = 0
    for cred in creds:
        lk = licenses.get(cred.license_id)
        if not lk:
            continue
        plan_code = plans_map.get(lk.plan_id) if lk.plan_id else lk.plan_type
        tags = get_allowed_image_tags(plan_code or "basic")
        cred.allowed_image_tags = tags
        lk.module_mask = await get_module_mask(db, plan_code or "basic")
        # 8.3 ④ 批量更新时更新密码：重新生成并写 htpasswd + 加密存库
        new_password = generate_registry_password()
        if write_htpasswd(cred.registry_username, new_password):
            cred.registry_password_enc = encrypt_password(new_password)
        updated += 1
    await db.flush()
    trigger_registry_reload()
    return {"message": "已更新凭证模块权限与密码", "updated": updated}


@router.get("/stats", response_model=StatsOverview)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        return await _get_stats_impl(db)
    except (ProgrammingError, OperationalError, Exception) as e:
        if _is_migration_needed_error(e):
            raise HTTPException(
                status_code=503,
                detail="数据库需先执行迁移：billing_periods 表缺少 name 列。请在 portal-system 目录执行：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_billing_period_name.sql 或 cd api && python scripts/add_billing_period_name_column.py",
            )
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"数据总览加载失败: {str(e)}")


async def _get_stats_impl(db: AsyncSession):
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_30 = now + timedelta(days=30)
    end_7 = now + timedelta(days=7)
    start_30d = now - timedelta(days=30)

    total_users = await db.scalar(select(func.count(PortalUser.id)))
    activated = await db.scalar(select(func.count(LicenseKey.id)).where(LicenseKey.is_used == True))
    total_licenses = await db.scalar(select(func.count(LicenseKey.id)))
    new_month = await db.scalar(
        select(func.count(PortalUser.id)).where(PortalUser.created_at >= start_of_month)
    )
    new_activations = await db.scalar(
        select(func.count(LicenseKey.id)).where(
            LicenseKey.is_used == True,
            LicenseKey.activated_at >= start_of_month,
        )
    )

    period_names = {"monthly": "月付", "quarterly": "季付", "yearly": "年付", "internal": "内测"}

    def make_license_list_item(lk, plan, period, user):
        st = "已作废" if lk.is_revoked else ("已激活" if lk.is_used else ("已过期" if lk.expires_at and lk.expires_at <= now else "未使用"))
        return LicenseListItem(
            id=str(lk.id),
            code=str(lk.code) if lk.code else "",
            plan_type=lk.plan_type or "",
            expires_at=lk.expires_at,
            created_at=lk.created_at,
            created_by=lk.created_by or "",
            assigned_to=str(lk.assigned_to) if lk.assigned_to else None,
            is_used=lk.is_used,
            is_revoked=lk.is_revoked,
            activated_at=lk.activated_at,
            plan_name=plan.name if plan else None,
            period_name=period_names.get(period.code, period.code) if period else None,
            notes=lk.notes,
            machine_limit=lk.machine_limit,
            concurrent_limit=lk.concurrent_limit,
            pull_limit_monthly=lk.pull_limit_monthly,
            assigned_username=user.username if user else None,
            status=st,
        )

    expiring_result = await db.execute(
        select(LicenseKey, Plan, BillingPeriod, PortalUser)
        .outerjoin(Plan, LicenseKey.plan_id == Plan.id)
        .outerjoin(BillingPeriod, LicenseKey.period_id == BillingPeriod.id)
        .outerjoin(PortalUser, LicenseKey.assigned_to == PortalUser.id)
        .where(
            LicenseKey.expires_at >= now,
            LicenseKey.expires_at <= end_30,
        )
        .order_by(LicenseKey.expires_at.asc())
        .limit(20)
    )
    expiring_list = [make_license_list_item(lk, plan, period, user) for lk, plan, period, user in expiring_result.all()]

    expiring_7_result = await db.execute(
        select(LicenseKey, Plan, BillingPeriod, PortalUser)
        .outerjoin(Plan, LicenseKey.plan_id == Plan.id)
        .outerjoin(BillingPeriod, LicenseKey.period_id == BillingPeriod.id)
        .outerjoin(PortalUser, LicenseKey.assigned_to == PortalUser.id)
        .where(
            LicenseKey.expires_at >= now,
            LicenseKey.expires_at <= end_7,
        )
        .order_by(LicenseKey.expires_at.asc())
        .limit(50)
    )
    expiring_7_list = [make_license_list_item(lk, plan, period, user) for lk, plan, period, user in expiring_7_result.all()]

    # 近 30 天注册趋势：按日统计
    trend_result = await db.execute(
        select(PortalUser.created_at).where(PortalUser.created_at >= start_30d)
    )
    trend_rows = trend_result.all()
    from collections import defaultdict
    by_date = defaultdict(int)
    for row in trend_rows:
        val = row[0] if hasattr(row, "__getitem__") else row
        d = val.date() if hasattr(val, "date") else val
        by_date[str(d)] += 1
    registration_trend = []
    for i in range(30):
        day = (now - timedelta(days=29 - i)).date()
        registration_trend.append(RegistrationTrendItem(date=str(day), count=by_date.get(str(day), 0)))

    # 授权码状态分布
    used = await db.scalar(select(func.count(LicenseKey.id)).where(LicenseKey.is_used == True))
    revoked = await db.scalar(select(func.count(LicenseKey.id)).where(LicenseKey.is_revoked == True))
    unused = (total_licenses or 0) - (used or 0) - (revoked or 0)
    if unused < 0:
        unused = 0
    license_status = LicenseStatusCounts(used=used or 0, unused=unused, revoked=revoked or 0)

    plan_breakdown_result = await db.execute(
        select(LicenseKey.plan_id, LicenseKey.plan_type, func.count(LicenseKey.id))
        .where(LicenseKey.is_revoked == False)
        .group_by(LicenseKey.plan_id, LicenseKey.plan_type)
    )
    plan_rows = plan_breakdown_result.all()
    plan_ids = {r[0] for r in plan_rows if r[0]}
    plans_map = {}
    if plan_ids:
        pr = await db.execute(select(Plan).where(Plan.id.in_(plan_ids)))
        plans_map = {p.id: (p.code, p.name) for p in pr.scalars().all()}
    plan_breakdown = []
    for pid, ptype, cnt in plan_rows:
        code, name = plans_map.get(pid, (ptype or "standard", ptype or "标准版"))
        plan_breakdown.append(PlanCountItem(plan_code=code or "standard", plan_name=name or "标准版", count=cnt))

    active_plan_result = await db.execute(
        select(LicenseKey.plan_id, LicenseKey.plan_type, func.count(func.distinct(LicenseKey.assigned_to)))
        .where(LicenseKey.is_used == True, LicenseKey.assigned_to.isnot(None))
        .group_by(LicenseKey.plan_id, LicenseKey.plan_type)
    )
    active_users_by_plan = []
    for pid, ptype, cnt in active_plan_result.all():
        code, name = plans_map.get(pid, (ptype or "standard", ptype or "标准版"))
        active_users_by_plan.append(PlanCountItem(plan_code=code or "standard", plan_name=name or "标准版", count=cnt))

    machine_bindings_total = await db.scalar(select(func.count(MachineBinding.id))) or 0

    pull_top_r = await db.execute(
        select(RegistryCredential.user_id, PortalUser.username, RegistryCredential.pull_count_this_month)
        .join(PortalUser, RegistryCredential.user_id == PortalUser.id)
        .order_by(RegistryCredential.pull_count_this_month.desc())
        .limit(10)
    )
    pull_top10_this_month = [
        PullTopItem(
            user_id=str(row[0]),
            username=str(row[1]) if row[1] else str(row[0])[:8],
            pull_count=int(row[2]) if row[2] is not None else 0,
        )
        for row in pull_top_r.all()
    ]

    alerts = []
    dup_machine_r = await db.execute(
        select(MachineBinding.machine_id, func.count(func.distinct(MachineBinding.user_id)))
        .where(MachineBinding.is_active == True)
        .group_by(MachineBinding.machine_id)
        .having(func.count(func.distinct(MachineBinding.user_id)) > 1)
    )
    for mid, c in dup_machine_r.all():
        alerts.append(f"同一机器绑定多账号：machine_id={mid}，绑定 {c} 个用户")

    return StatsOverview(
        total_users=total_users or 0,
        activated_users=activated or 0,
        total_licenses=total_licenses or 0,
        new_users_this_month=new_month or 0,
        new_activations_this_month=new_activations or 0,
        expiring_licenses=expiring_list,
        expiring_7_days=expiring_7_list,
        registration_trend=registration_trend,
        license_status=license_status,
        plan_breakdown=plan_breakdown,
        active_users_by_plan=active_users_by_plan,
        machine_bindings_total=machine_bindings_total,
        pull_top10_this_month=pull_top10_this_month,
        alerts=alerts,
    )

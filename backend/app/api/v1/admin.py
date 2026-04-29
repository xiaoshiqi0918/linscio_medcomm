"""
Admin 管理后台 API（SaaS 模式独有）
所有端点需要 is_admin=True 的用户身份。
"""
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, and_, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.models.user import User
from app.models.billing import (
    PaymentOrder, RefundRecord, ReconciliationLog, UsageLog, RechargeLog,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["管理后台"])


async def _audit(
    db: AsyncSession, admin_id: int, action: str,
    target_user_id: int | None = None,
    reason: str = "",
    payload: dict | None = None,
) -> None:
    """写入管理员审计日志（静默失败）"""
    try:
        from app.models.billing import AdminAuditLog
        db.add(AdminAuditLog(
            admin_id=admin_id,
            action=action,
            target_user_id=target_user_id,
            payload=payload,
            reason=reason or "",
        ))
    except Exception as exc:
        logger.warning("审计日志写入失败: %s", exc)


# ══════════════════════════════════════════════════════════════
#  仪表盘统计
# ══════════════════════════════════════════════════════════════

class DashboardStats(BaseModel):
    total_users: int
    new_users_today: int
    new_users_7d: int
    total_orders: int
    total_revenue: float
    revenue_today: float
    revenue_7d: float
    total_credits_consumed: float
    active_users_7d: int


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    new_today = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )).scalar() or 0
    new_7d = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )).scalar() or 0

    total_orders = (await db.execute(
        select(func.count(PaymentOrder.id)).where(PaymentOrder.status == "paid")
    )).scalar() or 0
    total_revenue = float((await db.execute(
        select(func.coalesce(func.sum(PaymentOrder.amount_yuan), 0)).where(PaymentOrder.status == "paid")
    )).scalar() or 0)
    revenue_today = float((await db.execute(
        select(func.coalesce(func.sum(PaymentOrder.amount_yuan), 0)).where(
            PaymentOrder.status == "paid", PaymentOrder.paid_at >= today_start
        )
    )).scalar() or 0)
    revenue_7d = float((await db.execute(
        select(func.coalesce(func.sum(PaymentOrder.amount_yuan), 0)).where(
            PaymentOrder.status == "paid", PaymentOrder.paid_at >= week_ago
        )
    )).scalar() or 0)

    total_consumed = float((await db.execute(
        select(func.coalesce(func.sum(UsageLog.cost), 0))
    )).scalar() or 0)

    active_7d = (await db.execute(
        select(func.count(func.distinct(UsageLog.user_id))).where(UsageLog.created_at >= week_ago)
    )).scalar() or 0

    return DashboardStats(
        total_users=total_users,
        new_users_today=new_today,
        new_users_7d=new_7d,
        total_orders=total_orders,
        total_revenue=total_revenue,
        revenue_today=revenue_today,
        revenue_7d=revenue_7d,
        total_credits_consumed=round(total_consumed, 2),
        active_users_7d=active_7d,
    )


# ══════════════════════════════════════════════════════════════
#  用户管理
# ══════════════════════════════════════════════════════════════

class AdminUserItem(BaseModel):
    id: int
    display_name: str | None
    phone: str | None
    is_banned: bool
    is_admin: bool
    credits: float
    gift_credits: float
    promo_credits: float
    total_recharged: float
    total_consumed: float
    created_at: str | None


class UserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminUserItem]


@router.get("/users", response_model=UserListResponse)
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    banned_only: bool = Query(False),
):
    query = select(User).order_by(desc(User.created_at))
    count_q = select(func.count(User.id))

    if search:
        like = f"%{search}%"
        filt = (User.phone.ilike(like)) | (User.display_name.ilike(like))
        query = query.where(filt)
        count_q = count_q.where(filt)
    if banned_only:
        query = query.where(User.is_banned == True)
        count_q = count_q.where(User.is_banned == True)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    users = result.scalars().all()

    return UserListResponse(
        total=total, page=page, page_size=page_size,
        items=[AdminUserItem(
            id=u.id,
            display_name=u.display_name,
            phone=u.phone,
            is_banned=u.is_banned or False,
            is_admin=getattr(u, "is_admin", False) or False,
            credits=float(u.credits or 0),
            gift_credits=float(u.gift_credits or 0),
            promo_credits=float(u.promo_credits or 0),
            total_recharged=float(u.total_recharged or 0),
            total_consumed=float(u.total_consumed or 0),
            created_at=u.created_at.isoformat() if u.created_at else None,
        ) for u in users],
    )


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看用户详情：基础信息 + 积分流水 + 文章列表 + 操作日志"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")

    # 积分流水（最近50条）
    usage_result = await db.execute(
        select(UsageLog)
        .where(UsageLog.user_id == user_id)
        .order_by(desc(UsageLog.created_at))
        .limit(50)
    )
    usage_logs = [
        {
            "id": l.id, "operation": l.operation, "cost": float(l.cost),
            "article_id": l.article_id, "section_id": l.section_id,
            "meta": l.meta,
            "created_at": l.created_at.isoformat() if l.created_at else "",
        }
        for l in usage_result.scalars().all()
    ]

    # 充值记录（最近20条）
    recharge_result = await db.execute(
        select(RechargeLog)
        .where(RechargeLog.user_id == user_id)
        .order_by(desc(RechargeLog.created_at))
        .limit(20)
    )
    recharge_logs = [
        {
            "id": r.id, "order_no": r.order_no,
            "amount_yuan": float(r.amount_yuan),
            "credits_added": float(r.credits_added),
            "bonus_credits": float(r.bonus_credits),
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in recharge_result.scalars().all()
    ]

    # 文章列表（最近20篇）
    try:
        from app.models.article import Article
        art_result = await db.execute(
            select(Article)
            .where(Article.user_id == user_id, Article.deleted_at.is_(None))
            .order_by(desc(Article.updated_at))
            .limit(20)
        )
        articles = [
            {"id": a.id, "topic": a.topic, "status": a.status,
             "content_format": a.content_format,
             "created_at": a.created_at.isoformat() if a.created_at else ""}
            for a in art_result.scalars().all()
        ]
    except Exception:
        articles = []

    # 管理员操作日志（针对此用户）
    from app.models.billing import AdminAuditLog
    audit_result = await db.execute(
        select(AdminAuditLog)
        .where(AdminAuditLog.target_user_id == user_id)
        .order_by(desc(AdminAuditLog.created_at))
        .limit(50)
    )
    audit_logs = [
        {
            "id": a.id, "admin_id": a.admin_id, "action": a.action,
            "reason": a.reason, "payload": a.payload,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        }
        for a in audit_result.scalars().all()
    ]

    return {
        "user": {
            "id": user.id,
            "display_name": user.display_name,
            "phone": user.phone,
            "is_admin": getattr(user, "is_admin", False),
            "is_banned": user.is_banned or False,
            "credits": float(user.credits or 0),
            "gift_credits": float(user.gift_credits or 0),
            "promo_credits": float(user.promo_credits or 0),
            "frozen_credits": float(user.frozen_credits or 0),
            "total_recharged": float(user.total_recharged or 0),
            "total_consumed": float(user.total_consumed or 0),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if getattr(user, "last_login_at", None) else None,
            "admin_note": getattr(user, "admin_note", None),
        },
        "usage_logs": usage_logs,
        "recharge_logs": recharge_logs,
        "articles": articles,
        "audit_logs": audit_logs,
    }


class AdminNoteRequest(BaseModel):
    user_id: int
    note: str


@router.post("/users/note")
async def set_admin_note(
    req: AdminNoteRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """设置客服备注（内部可见）"""
    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if hasattr(user, "admin_note"):
        user.admin_note = req.note
    await _audit(db, admin.id, "set_note",
                 target_user_id=req.user_id, reason=req.note)
    await db.commit()
    return {"success": True}


class BanUserRequest(BaseModel):
    user_id: int
    banned: bool


@router.post("/users/ban")
async def ban_user(
    req: BanUserRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能封禁自己")
    user.is_banned = req.banned
    await _audit(db, admin.id, "ban_user" if req.banned else "unban_user",
                 target_user_id=req.user_id,
                 payload={"banned": req.banned})
    await db.commit()
    return {"success": True, "user_id": req.user_id, "is_banned": req.banned}


class AdjustCreditsRequest(BaseModel):
    user_id: int
    amount: float
    credit_type: str = Field("credits", description="credits / gift_credits / promo_credits")
    reason: str = ""


@router.post("/users/adjust-credits")
async def adjust_credits(
    req: AdjustCreditsRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, req.user_id, with_for_update=True)
    if not user:
        raise HTTPException(404, "用户不存在")

    amount = Decimal(str(req.amount))
    if req.credit_type == "credits":
        user.credits = max(Decimal("0"), (user.credits or Decimal("0")) + amount)
    elif req.credit_type == "gift_credits":
        user.gift_credits = max(Decimal("0"), (user.gift_credits or Decimal("0")) + amount)
    elif req.credit_type == "promo_credits":
        user.promo_credits = max(Decimal("0"), (user.promo_credits or Decimal("0")) + amount)
    else:
        raise HTTPException(400, f"未知积分类型: {req.credit_type}")

    await _audit(db, admin.id, "adjust_credits",
                 target_user_id=req.user_id, reason=req.reason,
                 payload={"credit_type": req.credit_type, "amount": float(amount)})
    await db.commit()
    logger.info(
        "管理员 %d 调整用户 %d 积分: type=%s amount=%s reason=%s",
        admin.id, req.user_id, req.credit_type, amount, req.reason,
    )
    return {"success": True, "user_id": req.user_id, "new_balance": {
        "credits": float(user.credits or 0),
        "gift_credits": float(user.gift_credits or 0),
        "promo_credits": float(user.promo_credits or 0),
    }}


class SetAdminRequest(BaseModel):
    user_id: int
    is_admin: bool


@router.post("/users/set-admin")
async def set_admin(
    req: SetAdminRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    user.is_admin = req.is_admin
    await _audit(db, admin.id, "set_admin",
                 target_user_id=req.user_id,
                 payload={"is_admin": req.is_admin})
    await db.commit()
    return {"success": True, "user_id": req.user_id, "is_admin": req.is_admin}


# ══════════════════════════════════════════════════════════════
#  订单管理
# ══════════════════════════════════════════════════════════════

class AdminOrderItem(BaseModel):
    id: int
    order_no: str
    user_id: int
    user_phone: str | None = None
    channel_code: str
    amount_yuan: str
    credits_to_add: float
    bonus_credits: float
    pay_method: str | None
    status: str
    paid_at: str | None
    created_at: str | None
    refunded_amount: str


class OrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminOrderItem]


@router.get("/orders", response_model=OrderListResponse)
async def list_all_orders(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None),
    user_id: int | None = Query(None),
    channel: str | None = Query(None),
):
    query = select(PaymentOrder).order_by(desc(PaymentOrder.created_at))
    count_q = select(func.count(PaymentOrder.id))

    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
        count_q = count_q.where(PaymentOrder.status == status_filter)
    if user_id:
        query = query.where(PaymentOrder.user_id == user_id)
        count_q = count_q.where(PaymentOrder.user_id == user_id)
    if channel:
        query = query.where(PaymentOrder.channel_code == channel)
        count_q = count_q.where(PaymentOrder.channel_code == channel)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    orders = result.scalars().all()

    user_ids = {o.user_id for o in orders}
    users_result = await db.execute(select(User.id, User.phone).where(User.id.in_(user_ids)))
    phone_map = {uid: phone for uid, phone in users_result.all()}

    return OrderListResponse(
        total=total, page=page, page_size=page_size,
        items=[AdminOrderItem(
            id=o.id, order_no=o.order_no, user_id=o.user_id,
            user_phone=phone_map.get(o.user_id),
            channel_code=o.channel_code,
            amount_yuan=str(o.amount_yuan),
            credits_to_add=float(o.credits_to_add),
            bonus_credits=float(o.bonus_credits),
            pay_method=o.pay_method, status=o.status,
            paid_at=o.paid_at.isoformat() if o.paid_at else None,
            created_at=o.created_at.isoformat() if o.created_at else None,
            refunded_amount=str(o.refunded_amount or 0),
        ) for o in orders],
    )


class AdminRefundRequest(BaseModel):
    order_no: str
    refund_amount: float | None = Field(None, description="为空时自动按规则计算")
    reason: str = ""


@router.post("/orders/refund")
async def admin_refund(
    req: AdminRefundRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.payment.service import payment_service
    result = await payment_service.refund(
        order_no=req.order_no,
        refund_amount_yuan=Decimal(str(req.refund_amount)) if req.refund_amount is not None else None,
        reason=req.reason,
        operator=f"admin:{admin.id}",
        db=db,
    )
    if not result["success"]:
        raise HTTPException(400, result["error"])
    await _audit(db, admin.id, "refund", reason=req.reason,
                 payload={"order_no": req.order_no, "refund_amount": req.refund_amount})
    await db.commit()
    return result


# ══════════════════════════════════════════════════════════════
#  对账记录
# ══════════════════════════════════════════════════════════════

class ReconItem(BaseModel):
    id: int
    bill_date: str
    channel_code: str
    total_orders: int
    matched_orders: int
    mismatched_orders: int
    total_amount: str
    diff_amount: str
    status: str
    details: dict | list | None
    created_at: str | None


@router.get("/reconciliation", response_model=list[ReconItem])
async def list_reconciliation(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    result = await db.execute(
        select(ReconciliationLog)
        .order_by(desc(ReconciliationLog.created_at))
        .offset((page - 1) * page_size).limit(page_size)
    )
    logs = result.scalars().all()
    return [ReconItem(
        id=r.id, bill_date=r.bill_date.isoformat(), channel_code=r.channel_code,
        total_orders=r.total_orders or 0, matched_orders=r.matched_orders or 0,
        mismatched_orders=r.mismatched_orders or 0,
        total_amount=str(r.total_amount or 0), diff_amount=str(r.diff_amount or 0),
        status=r.status, details=r.details,
        created_at=r.created_at.isoformat() if r.created_at else None,
    ) for r in logs]


# ══════════════════════════════════════════════════════════════
#  系统配置
# ══════════════════════════════════════════════════════════════

@router.get("/config")
async def get_system_config(admin: User = Depends(get_admin_user)):
    from app.core.config import settings
    from app.services.payment.service import RECHARGE_PLANS
    from app.services.payment.registry import list_channels
    return {
        "deployment_mode": settings.deployment_mode,
        "payment_channels": list_channels(),
        "recharge_plans": RECHARGE_PLANS,
        "order_expire_minutes": settings.order_expire_minutes,
        "new_user_gift_credits": settings.new_user_gift_credits,
        "gift_credits_validity_days": settings.gift_credits_validity_days,
        "promo_cash_rate": settings.promo_cash_rate,
        "promo_min_withdraw": settings.promo_min_withdraw,
    }


# ══════════════════════════════════════════════════════════════
#  授权码管理
# ══════════════════════════════════════════════════════════════

class AdminLicenseItem(BaseModel):
    id: int
    code: str
    owner_id: int | None
    owner_phone: str | None = None
    credit_type: str
    credits_cost: float
    source: str
    is_used: bool
    device_id: str | None = None
    activated_at: str | None = None
    used_by: str | None
    used_at: str | None
    note: str | None
    created_at: str


@router.get("/licenses", response_model=dict)
async def list_licenses(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_filter: str | None = Query(None),
    used_filter: str | None = Query(None),
):
    from app.models.billing import LicenseCode

    query = select(LicenseCode).order_by(desc(LicenseCode.created_at))
    count_q = select(func.count(LicenseCode.id))

    if source_filter:
        query = query.where(LicenseCode.source == source_filter)
        count_q = count_q.where(LicenseCode.source == source_filter)
    if used_filter == "used":
        query = query.where(LicenseCode.is_used == True)
        count_q = count_q.where(LicenseCode.is_used == True)
    elif used_filter == "unused":
        query = query.where(LicenseCode.is_used == False)
        count_q = count_q.where(LicenseCode.is_used == False)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    codes = result.scalars().all()

    owner_ids = {c.owner_id for c in codes if c.owner_id}
    phone_map = {}
    if owner_ids:
        users_result = await db.execute(select(User.id, User.phone).where(User.id.in_(owner_ids)))
        phone_map = {uid: phone for uid, phone in users_result.all()}

    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [AdminLicenseItem(
            id=c.id, code=c.code, owner_id=c.owner_id,
            owner_phone=phone_map.get(c.owner_id) if c.owner_id else None,
            credit_type=c.credit_type, credits_cost=float(c.credits_cost),
            source=c.source, is_used=c.is_used or False,
            device_id=c.device_id,
            activated_at=c.activated_at.isoformat() if c.activated_at else None,
            used_by=c.used_by, used_at=c.used_at.isoformat() if c.used_at else None,
            note=c.note, created_at=c.created_at.isoformat() if c.created_at else "",
        ) for c in codes],
    }


class GenerateLicensesRequest(BaseModel):
    count: int = Field(1, ge=1, le=100)
    note: str = ""


@router.post("/licenses/generate")
async def generate_licenses(
    req: GenerateLicensesRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员批量生成授权码（不消耗积分）"""
    import secrets
    from app.models.billing import LicenseCode

    LICENSE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    seg = lambda: "".join(secrets.choice(LICENSE_CHARS) for _ in range(4))

    generated = []
    for _ in range(req.count):
        code_str = f"LINSCIO-{seg()}-{seg()}-{seg()}"
        lc = LicenseCode(
            code=code_str,
            owner_id=None,
            credit_type="admin",
            credits_cost=0,
            source="admin_generate",
            note=req.note or f"管理员 {admin.id} 生成",
        )
        db.add(lc)
        generated.append(code_str)

    await _audit(db, admin.id, "generate_licenses",
                 payload={"count": req.count, "note": req.note})
    await db.commit()
    logger.info("管理员 %d 批量生成 %d 个授权码", admin.id, req.count)
    return {"count": len(generated), "codes": generated}


@router.post("/licenses/revoke")
async def revoke_license(
    license_id: int = Query(...),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """撤销/作废授权码"""
    from app.models.billing import LicenseCode
    lc = await db.get(LicenseCode, license_id)
    if not lc:
        raise HTTPException(404, "授权码不存在")
    if lc.is_used:
        raise HTTPException(400, "已使用的授权码无法撤销")
    await _audit(db, admin.id, "revoke_license",
                 payload={"license_id": license_id, "code": lc.code})
    await db.delete(lc)
    await db.commit()
    return {"success": True}


@router.post("/licenses/unbind-device")
async def unbind_license_device(
    license_id: int = Query(...),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员解绑授权码的设备绑定，允许用户在新设备上重新激活"""
    from app.models.billing import LicenseCode
    lc = await db.get(LicenseCode, license_id)
    if not lc:
        raise HTTPException(404, "授权码不存在")
    if not lc.device_id:
        raise HTTPException(400, "该授权码未绑定设备")

    old_device = lc.device_id
    lc.device_id = None
    lc.device_info = None
    lc.is_used = False
    lc.activated_at = None

    await _audit(
        db, admin.id, "unbind_license_device",
        target_user_id=lc.owner_id,
        reason=f"解绑授权码设备: code={lc.code}, old_device={old_device}",
        payload={"license_id": license_id, "old_device_id": old_device},
    )
    await db.commit()
    return {"success": True, "message": f"已解绑设备 {old_device[:16]}..."}


@router.get("/auth/me")
async def admin_me(admin: User = Depends(get_admin_user)):
    """管理员身份确认"""
    return {
        "id": admin.id,
        "display_name": admin.display_name,
        "phone": admin.phone,
        "is_admin": True,
    }


# ══════════════════════════════════════════════════════════════
#  兑现审批
# ══════════════════════════════════════════════════════════════

class WithdrawalListItem(BaseModel):
    id: int
    user_id: int
    display_name: str | None
    phone: str | None
    credits_used: float
    amount_yuan: float
    platform_account: str | None
    wechat_phone: str | None
    promo_credits: float
    status: str
    created_at: str
    reviewed_at: str | None
    paid_at: str | None
    note: str | None


@router.get("/withdrawals", response_model=list[WithdrawalListItem])
async def list_withdrawals(
    status: str | None = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看所有兑现申请"""
    from app.models.referral import WithdrawalLog
    q = select(WithdrawalLog).order_by(desc(WithdrawalLog.created_at)).limit(200)
    if status:
        q = q.where(WithdrawalLog.status == status)
    result = await db.execute(q)
    rows = result.scalars().all()

    items = []
    for w in rows:
        u = await db.get(User, w.user_id)
        items.append(WithdrawalListItem(
            id=w.id,
            user_id=w.user_id,
            display_name=u.display_name if u else None,
            phone=u.phone if u else None,
            credits_used=float(w.credits_used),
            amount_yuan=float(w.amount_yuan),
            platform_account=w.platform_account,
            wechat_phone=w.wechat_phone,
            promo_credits=float(u.promo_credits or 0) if u else 0,
            status=w.status,
            created_at=w.created_at.isoformat() if w.created_at else "",
            reviewed_at=w.reviewed_at.isoformat() if w.reviewed_at else None,
            paid_at=w.paid_at.isoformat() if w.paid_at else None,
            note=w.note,
        ))
    return items


class ReviewWithdrawalRequest(BaseModel):
    withdrawal_id: int
    action: str = Field(..., description="approve / reject / paid")
    note: str | None = None


@router.post("/withdrawals/review")
async def review_withdrawal(
    req: ReviewWithdrawalRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """审批兑现申请：approve（审核通过）→ paid（已打款）/ reject（驳回退还积分）"""
    from app.models.referral import WithdrawalLog
    wl = await db.get(WithdrawalLog, req.withdrawal_id)
    if not wl:
        raise HTTPException(404, "兑现记录不存在")

    now = datetime.now(timezone.utc)

    if req.action == "approve":
        if wl.status != "pending":
            raise HTTPException(400, f"当前状态 {wl.status} 不可审核")
        wl.status = "approved"
        wl.reviewed_by = admin.id
        wl.reviewed_at = now
        wl.note = req.note or wl.note
        await _audit(db, admin.id, "withdrawal_approve",
                     target_user_id=wl.user_id, reason=req.note or "",
                     payload={"withdrawal_id": req.withdrawal_id, "amount_yuan": float(wl.amount_yuan)})
        await db.commit()
        return {"success": True, "status": "approved", "message": "已审核通过，请线下打款后标记 paid"}

    elif req.action == "paid":
        if wl.status not in ("approved",):
            raise HTTPException(400, f"当前状态 {wl.status} 不可标记打款")
        wl.status = "paid"
        wl.paid_at = now
        wl.note = req.note or wl.note
        await _audit(db, admin.id, "withdrawal_paid",
                     target_user_id=wl.user_id,
                     payload={"withdrawal_id": req.withdrawal_id})
        await db.commit()
        return {"success": True, "status": "paid"}

    elif req.action == "reject":
        if wl.status not in ("pending", "approved"):
            raise HTTPException(400, f"当前状态 {wl.status} 不可驳回")
        user = await db.get(User, wl.user_id)
        if user:
            user.promo_credits = (user.promo_credits or Decimal("0")) + wl.credits_used
        wl.status = "rejected"
        wl.reviewed_by = admin.id
        wl.reviewed_at = now
        wl.note = req.note or "管理员驳回"
        await _audit(db, admin.id, "withdrawal_reject",
                     target_user_id=wl.user_id, reason=req.note or "管理员驳回",
                     payload={"withdrawal_id": req.withdrawal_id, "credits_returned": float(wl.credits_used)})
        await db.commit()
        return {"success": True, "status": "rejected", "message": "已驳回，积分已退还"}

    raise HTTPException(400, f"未知操作: {req.action}，可选 approve / reject / paid")


# ══════════════════════════════════════════════════════════════
#  质量补偿券管理
# ══════════════════════════════════════════════════════════════

class IssueVoucherRequest(BaseModel):
    user_id: int
    reason: str = ""
    discount_rate: float = Field(0.50, ge=0.01, le=1.0, description="折扣率，0.50=5折")
    max_uses: int = Field(3, ge=1, le=10)


@router.post("/vouchers/issue")
async def issue_voucher(
    req: IssueVoucherRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """为用户发放质量补偿券"""
    from app.models.billing import CompensationVoucher
    from datetime import timedelta

    target = await db.get(User, req.user_id)
    if not target:
        raise HTTPException(404, "用户不存在")

    voucher = CompensationVoucher(
        user_id=req.user_id,
        discount_rate=Decimal(str(req.discount_rate)),
        max_uses=req.max_uses,
        used_count=0,
        status="active",
        reason=req.reason or f"管理员 {admin.id} 发放",
        issued_by=f"admin:{admin.id}",
        expire_at=datetime.now(timezone.utc) + timedelta(days=90),
    )
    db.add(voucher)
    await _audit(db, admin.id, "issue_voucher",
                 target_user_id=req.user_id, reason=req.reason,
                 payload={"discount_rate": req.discount_rate, "max_uses": req.max_uses})
    await db.commit()
    await db.refresh(voucher)

    logger.info("补偿券发放: admin=%d user=%d voucher=%d", admin.id, req.user_id, voucher.id)
    return {
        "id": voucher.id,
        "user_id": req.user_id,
        "discount_rate": float(voucher.discount_rate),
        "max_uses": voucher.max_uses,
        "expire_at": voucher.expire_at.isoformat() if voucher.expire_at else None,
    }


@router.get("/vouchers")
async def list_vouchers(
    user_id: int | None = Query(None),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看补偿券列表"""
    from app.models.billing import CompensationVoucher
    q = select(CompensationVoucher).order_by(desc(CompensationVoucher.created_at)).limit(200)
    if user_id:
        q = q.where(CompensationVoucher.user_id == user_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": v.id,
            "user_id": v.user_id,
            "discount_rate": float(v.discount_rate),
            "max_uses": v.max_uses,
            "used_count": v.used_count,
            "status": v.status,
            "reason": v.reason,
            "expire_at": v.expire_at.isoformat() if v.expire_at else None,
            "created_at": v.created_at.isoformat() if v.created_at else "",
        }
        for v in rows
    ]


# ══════════════════════════════════════════════════════════════
#  兑换码管理
# ══════════════════════════════════════════════════════════════

import secrets
import string
import uuid as _uuid

REDEEM_TIER_CONFIG: dict[int, dict] = {
    10:  {"prefix": "LS0A", "credits": 10,  "bonus": 0},
    50:  {"prefix": "LS3B", "credits": 50,  "bonus": 3},
    100: {"prefix": "LS5C", "credits": 100, "bonus": 8},
    300: {"prefix": "LS7D", "credits": 300, "bonus": 30},
    500: {"prefix": "LS9E", "credits": 500, "bonus": 60},
}

_REDEEM_CHARSET = string.ascii_uppercase + string.digits


def _generate_redeem_code(prefix: str) -> str:
    rand_part = "".join(secrets.choice(_REDEEM_CHARSET) for _ in range(16))
    return f"{prefix}-{rand_part[:4]}-{rand_part[4:8]}-{rand_part[8:12]}-{rand_part[12:]}"


class GenerateRedeemCodesRequest(BaseModel):
    tier: int = Field(..., description="价位档 10/50/100/300/500")
    count: int = Field(1, ge=1, le=200)


@router.post("/redeem-codes/generate")
async def generate_redeem_codes(
    req: GenerateRedeemCodesRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = REDEEM_TIER_CONFIG.get(req.tier)
    if not cfg:
        raise HTTPException(400, f"不支持的档位: {req.tier}，可选: {list(REDEEM_TIER_CONFIG.keys())}")

    from app.models.billing import RedeemCode

    batch_id = _uuid.uuid4().hex[:16]
    codes_created = []

    for _ in range(req.count):
        for _retry in range(10):
            code = _generate_redeem_code(cfg["prefix"])
            existing = await db.execute(
                select(RedeemCode.id).where(RedeemCode.code == code).limit(1)
            )
            if existing.scalar_one_or_none() is None:
                break
        else:
            raise HTTPException(500, "兑换码生成冲突，请重试")

        rc = RedeemCode(
            code=code,
            tier=req.tier,
            credits=Decimal(str(cfg["credits"])),
            bonus_credits=Decimal(str(cfg["bonus"])),
            batch_id=batch_id,
            created_by=admin.id,
        )
        db.add(rc)
        codes_created.append(code)

    await db.commit()

    await _audit(
        db, admin.id, "generate_redeem_codes",
        reason=f"批量生成兑换码 tier={req.tier} count={req.count}",
        payload={"tier": req.tier, "count": req.count, "batch_id": batch_id},
    )

    return {"batch_id": batch_id, "count": len(codes_created), "codes": codes_created}


class AdminRedeemCodeItem(BaseModel):
    id: int
    code: str
    tier: int
    credits: float
    bonus_credits: float
    status: str
    batch_id: str | None
    used_by: int | None
    used_by_phone: str | None = None
    used_at: str | None
    created_at: str


@router.get("/redeem-codes", response_model=dict)
async def list_redeem_codes(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tier: int | None = Query(None),
    status_filter: str | None = Query(None),
    batch_id: str | None = Query(None),
):
    from app.models.billing import RedeemCode

    query = select(RedeemCode).order_by(desc(RedeemCode.created_at))
    count_q = select(func.count(RedeemCode.id))

    if tier is not None:
        query = query.where(RedeemCode.tier == tier)
        count_q = count_q.where(RedeemCode.tier == tier)
    if status_filter:
        query = query.where(RedeemCode.status == status_filter)
        count_q = count_q.where(RedeemCode.status == status_filter)
    if batch_id:
        query = query.where(RedeemCode.batch_id == batch_id)
        count_q = count_q.where(RedeemCode.batch_id == batch_id)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    rows = result.scalars().all()

    user_ids = {r.used_by for r in rows if r.used_by}
    phone_map = {}
    if user_ids:
        users_r = await db.execute(select(User.id, User.phone).where(User.id.in_(user_ids)))
        phone_map = {uid: phone for uid, phone in users_r.all()}

    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [AdminRedeemCodeItem(
            id=r.id, code=r.code, tier=r.tier,
            credits=float(r.credits), bonus_credits=float(r.bonus_credits),
            status=r.status, batch_id=r.batch_id,
            used_by=r.used_by,
            used_by_phone=phone_map.get(r.used_by) if r.used_by else None,
            used_at=r.used_at.isoformat() if r.used_at else None,
            created_at=r.created_at.isoformat() if r.created_at else "",
        ) for r in rows],
    }


@router.get("/redeem-codes/tiers")
async def get_redeem_tiers(admin: User = Depends(get_admin_user)):
    return [
        {"tier": t, "prefix": c["prefix"], "credits": c["credits"], "bonus": c["bonus"]}
        for t, c in sorted(REDEEM_TIER_CONFIG.items())
    ]


class RevokeRedeemCodesRequest(BaseModel):
    code_ids: list[int] = Field(..., min_length=1, max_length=200)
    reason: str = ""


@router.post("/redeem-codes/revoke")
async def revoke_redeem_codes(
    req: RevokeRedeemCodesRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.billing import RedeemCode

    result = await db.execute(
        select(RedeemCode).where(
            RedeemCode.id.in_(req.code_ids),
            RedeemCode.status == "unused",
        )
    )
    codes = result.scalars().all()
    if not codes:
        raise HTTPException(404, "未找到可作废的兑换码")

    revoked = 0
    for c in codes:
        c.status = "revoked"
        revoked += 1

    await db.commit()

    await _audit(
        db, admin.id, "revoke_redeem_codes",
        reason=req.reason or f"批量作废 {revoked} 个兑换码",
        payload={"code_ids": [c.id for c in codes], "count": revoked},
    )

    return {"revoked": revoked}

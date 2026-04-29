"""
积分接口（SaaS 模式独有）
积分查询 / 流水 / 充值套餐
"""
import csv
import io
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.billing import UsageLog, RechargeLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/credits", tags=["积分"])


class PromoInfo(BaseModel):
    promo_credits: float
    promo_credits_expire_at: str | None
    cash_rate: float
    cash_value_yuan: float
    min_withdraw_credits: int
    can_withdraw: bool


class BalanceResponse(BaseModel):
    credits: float
    gift_credits: float
    gift_credits_expire_at: str | None
    promo: PromoInfo
    frozen_credits: float
    total_available: float
    total_recharged: float
    total_consumed: float


class UsageLogItem(BaseModel):
    id: int
    operation: str
    cost: float
    breakdown: dict | None
    meta: dict | None
    aborted: bool
    article_id: int | None
    section_id: int | None
    created_at: str


class RechargePlan(BaseModel):
    amount_yuan: int
    credits: int
    bonus: int
    unit_price: str


RECHARGE_PLANS: list[dict] = [
    {"amount_yuan": 10, "credits": 10, "bonus": 0, "unit_price": "1.00 元/积分"},
    {"amount_yuan": 50, "credits": 50, "bonus": 3, "unit_price": "0.94 元/积分"},
    {"amount_yuan": 100, "credits": 100, "bonus": 8, "unit_price": "0.93 元/积分"},
    {"amount_yuan": 300, "credits": 300, "bonus": 30, "unit_price": "0.91 元/积分"},
    {"amount_yuan": 500, "credits": 500, "bonus": 60, "unit_price": "0.89 元/积分"},
]


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user: User = Depends(get_current_user)):
    from app.core.config import settings
    promo = float(user.promo_credits or 0)
    cash_rate = settings.promo_cash_rate
    min_withdraw = settings.promo_min_withdraw
    return BalanceResponse(
        credits=float(user.credits or 0),
        gift_credits=float(user.gift_credits or 0),
        gift_credits_expire_at=user.gift_credits_expire_at.isoformat() if user.gift_credits_expire_at else None,
        promo=PromoInfo(
            promo_credits=promo,
            promo_credits_expire_at=user.promo_credits_expire_at.isoformat() if user.promo_credits_expire_at else None,
            cash_rate=cash_rate,
            cash_value_yuan=round(promo * cash_rate, 2),
            min_withdraw_credits=min_withdraw,
            can_withdraw=promo >= min_withdraw,
        ),
        frozen_credits=float(user.frozen_credits or 0),
        total_available=float(user.total_available_credits),
        total_recharged=float(user.total_recharged or 0),
        total_consumed=float(user.total_consumed or 0),
    )


@router.get("/usage-logs")
async def get_usage_logs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    operation: str | None = Query(None),
    month: str | None = Query(None, description="按月筛选 YYYY-MM"),
):
    base_filter = [UsageLog.user_id == user.id]
    if operation:
        base_filter.append(UsageLog.operation == operation)
    if month:
        try:
            year, mon = month.split("-")
            start = datetime(int(year), int(mon), 1)
            end = datetime(int(year) + 1, 1, 1) if int(mon) == 12 else datetime(int(year), int(mon) + 1, 1)
            base_filter.append(UsageLog.created_at >= start)
            base_filter.append(UsageLog.created_at < end)
        except Exception:
            pass

    total = (await db.execute(
        select(func.count(UsageLog.id)).where(*base_filter)
    )).scalar() or 0

    query = (
        select(UsageLog)
        .where(*base_filter)
        .order_by(desc(UsageLog.created_at))
        .offset((page - 1) * page_size).limit(page_size)
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            UsageLogItem(
                id=log.id,
                operation=log.operation,
                cost=float(log.cost),
                breakdown=log.breakdown,
                meta=log.meta,
                aborted=log.aborted,
                article_id=log.article_id,
                section_id=log.section_id,
                created_at=log.created_at.isoformat() if log.created_at else "",
            )
            for log in logs
        ],
    }


class UsageSummary(BaseModel):
    total_cost: float
    total_count: int
    by_operation: dict[str, dict]


@router.get("/usage-summary", response_model=UsageSummary)
async def get_usage_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """最近 N 天消费统计汇总"""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            UsageLog.operation,
            func.sum(UsageLog.cost).label("total"),
            func.count().label("cnt"),
        )
        .where(UsageLog.user_id == user.id, UsageLog.created_at >= since)
        .group_by(UsageLog.operation)
    )
    rows = result.all()

    total_cost = 0.0
    total_count = 0
    by_op: dict[str, dict] = {}
    for op, cost_sum, cnt in rows:
        c = float(cost_sum or 0)
        total_cost += c
        total_count += cnt
        by_op[op] = {"cost": c, "count": cnt}

    return UsageSummary(
        total_cost=round(total_cost, 4),
        total_count=total_count,
        by_operation=by_op,
    )


@router.get("/usage-logs/export")
async def export_usage_logs_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: str | None = Query(None, description="按月筛选，格式 2026-04"),
    operation: str | None = Query(None),
):
    """导出积分流水为 CSV 文件"""
    from datetime import timedelta

    query = (
        select(UsageLog)
        .where(UsageLog.user_id == user.id)
        .order_by(desc(UsageLog.created_at))
    )
    if operation:
        query = query.where(UsageLog.operation == operation)
    if month:
        try:
            year, mon = month.split("-")
            start = datetime(int(year), int(mon), 1)
            if int(mon) == 12:
                end = datetime(int(year) + 1, 1, 1)
            else:
                end = datetime(int(year), int(mon) + 1, 1)
            query = query.where(UsageLog.created_at >= start, UsageLog.created_at < end)
        except Exception:
            pass
    query = query.limit(5000)

    result = await db.execute(query)
    logs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["时间", "操作", "积分变动", "文章ID", "章节ID", "备注"])
    for log in logs:
        ts = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else ""
        note = ""
        if log.meta and isinstance(log.meta, dict):
            note = log.meta.get("reason", log.meta.get("session_id", ""))
        writer.writerow([
            ts,
            log.operation,
            f"-{log.cost}" if float(log.cost) > 0 else str(log.cost),
            log.article_id or "",
            log.section_id or "",
            note,
        ])

    output.seek(0)
    filename = f"credits_{user.id}_{month or 'all'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/plans", response_model=list[RechargePlan])
async def get_recharge_plans():
    return [RechargePlan(**plan) for plan in RECHARGE_PLANS]


# ══════════════════════════════════════════════════════════════
#  兑换码充值
# ══════════════════════════════════════════════════════════════

class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=10, max_length=32)


class RedeemCodeResponse(BaseModel):
    credits: float
    bonus_credits: float
    total_added: float
    message: str


@router.post("/redeem", response_model=RedeemCodeResponse)
async def redeem_code(
    req: RedeemCodeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户提交兑换码充值"""
    from app.models.billing import RedeemCode
    from app.services.credit.service import add_credits
    from app.services.credit.referral_rewards import (
        grant_referral_recharge_reward,
        grant_referred_first_recharge_bonus,
    )

    code_str = req.code.strip().upper()

    result = await db.execute(
        select(RedeemCode).where(RedeemCode.code == code_str).limit(1)
    )
    rc = result.scalar_one_or_none()

    if rc is None:
        raise HTTPException(404, "兑换码不存在")
    if rc.status == "used":
        raise HTTPException(400, "该兑换码已被使用")
    if rc.status == "revoked":
        raise HTTPException(400, "该兑换码已作废")

    rc.status = "used"
    rc.used_by = user.id
    rc.used_at = datetime.now()

    total = rc.credits + rc.bonus_credits
    await add_credits(user.id, total, db, credit_type="credits")

    amount_yuan = Decimal(str(rc.tier))
    await grant_referral_recharge_reward(
        user.id, amount_yuan, rc.credits, db,
        source_id=rc.id, source_type="redeem_code",
    )
    await grant_referred_first_recharge_bonus(
        user.id, amount_yuan, rc.credits, db,
        source_id=rc.id, source_type="redeem_code",
    )

    await db.commit()

    logger.info(
        "兑换码充值成功: user=%d code=%s credits=%s bonus=%s",
        user.id, rc.code, rc.credits, rc.bonus_credits,
    )

    return RedeemCodeResponse(
        credits=float(rc.credits),
        bonus_credits=float(rc.bonus_credits),
        total_added=float(total),
        message=f"充值成功！获得 {float(rc.credits)} 积分"
               + (f" + {float(rc.bonus_credits)} 赠送积分" if rc.bonus_credits > 0 else ""),
    )


# ══════════════════════════════════════════════════════════════
#  质量补偿券（用户端）
# ══════════════════════════════════════════════════════════════

class VoucherItem(BaseModel):
    id: int
    discount_rate: float
    max_uses: int
    used_count: int
    remaining: int
    status: str
    expire_at: str | None
    reason: str | None


@router.get("/vouchers", response_model=list[VoucherItem])
async def my_vouchers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看我的补偿券"""
    from app.models.billing import CompensationVoucher
    result = await db.execute(
        select(CompensationVoucher)
        .where(CompensationVoucher.user_id == user.id)
        .order_by(desc(CompensationVoucher.created_at))
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        VoucherItem(
            id=v.id,
            discount_rate=float(v.discount_rate),
            max_uses=v.max_uses,
            used_count=v.used_count,
            remaining=max(0, v.max_uses - v.used_count),
            status=v.status,
            expire_at=v.expire_at.isoformat() if v.expire_at else None,
            reason=v.reason,
        )
        for v in rows
    ]


# ══════════════════════════════════════════════════════════════
#  授权码兑换
# ══════════════════════════════════════════════════════════════

LICENSE_COST = {
    "credits": Decimal("600"),
    "promo_credits": Decimal("6000"),
}


class RedeemLicenseRequest(BaseModel):
    credit_type: str = Field(..., description="credits 或 promo_credits")


class ClaimLicenseRequest(BaseModel):
    code: str = Field(..., min_length=8, max_length=32)


@router.post("/claim-license")
async def claim_license(
    req: ClaimLicenseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户输入管理员生成的授权码，绑定到自己账户"""
    from app.models.billing import LicenseCode

    code_str = req.code.strip().upper()
    result = await db.execute(
        select(LicenseCode).where(LicenseCode.code == code_str).limit(1)
    )
    lc = result.scalar_one_or_none()

    if lc is None:
        raise HTTPException(404, "授权码不存在")
    if lc.owner_id is not None and lc.owner_id != user.id:
        raise HTTPException(400, "该授权码已被其他用户领取")
    if lc.owner_id == user.id:
        return {"code": lc.code, "message": "该授权码已绑定到您的账户"}

    lc.owner_id = user.id
    await db.commit()

    logger.info("授权码领取: user=%d code=%s", user.id, lc.code)
    return {"code": lc.code, "message": "授权码领取成功，已绑定到您的账户"}


class LicenseCodeItem(BaseModel):
    id: int
    code: str
    credit_type: str
    credits_cost: float
    is_used: bool
    device_id: str | None = None
    activated_at: str | None = None
    used_by: str | None
    used_at: str | None
    created_at: str


@router.post("/redeem-license")
async def redeem_license(
    req: RedeemLicenseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用积分兑换客户端授权码"""
    import secrets
    from app.models.billing import LicenseCode

    cost = LICENSE_COST.get(req.credit_type)
    if cost is None:
        raise HTTPException(400, f"不支持的积分类型: {req.credit_type}，可选: credits / promo_credits")

    await db.refresh(user, with_for_update=True)

    if req.credit_type == "credits":
        regular = Decimal(str(user.credits or 0))
        gift = Decimal(str(user.gift_credits or 0))
        from datetime import datetime
        now = datetime.utcnow()
        if user.gift_credits_expire_at and user.gift_credits_expire_at.replace(tzinfo=None) < now:
            gift = Decimal("0")
        total = regular + gift
        if total < cost:
            raise HTTPException(400, f"积分不足，需要 {cost}，当前可用 {total}（充值 {regular} + 赠送 {gift}）")
        remaining = cost
        if gift > 0:
            deduct_gift = min(gift, remaining)
            user.gift_credits = gift - deduct_gift
            remaining -= deduct_gift
        if remaining > 0:
            user.credits = regular - remaining
    else:
        balance = Decimal(str(user.promo_credits or 0))
        if balance < cost:
            raise HTTPException(400, f"推广积分不足，需要 {cost}，当前 {balance}")
        user.promo_credits = balance - cost

    LICENSE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    seg = lambda: "".join(secrets.choice(LICENSE_CHARS) for _ in range(4))
    code_str = f"LINSCIO-{seg()}-{seg()}-{seg()}"
    license_code = LicenseCode(
        code=code_str,
        owner_id=user.id,
        credit_type=req.credit_type,
        credits_cost=cost,
        source="redeem",
    )
    db.add(license_code)
    await db.commit()

    logger.info(
        "授权码兑换: user=%d type=%s cost=%s code=%s",
        user.id, req.credit_type, cost, code_str,
    )
    return {"code": code_str, "credit_type": req.credit_type, "credits_cost": float(cost)}


@router.get("/my-licenses", response_model=list[LicenseCodeItem])
async def get_my_licenses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看我兑换的授权码"""
    from app.models.billing import LicenseCode

    result = await db.execute(
        select(LicenseCode)
        .where(LicenseCode.owner_id == user.id)
        .order_by(desc(LicenseCode.created_at))
        .limit(50)
    )
    codes = result.scalars().all()
    return [
        LicenseCodeItem(
            id=c.id,
            code=c.code,
            credit_type=c.credit_type,
            credits_cost=float(c.credits_cost),
            is_used=c.is_used or False,
            device_id=c.device_id,
            activated_at=c.activated_at.isoformat() if c.activated_at else None,
            used_by=c.used_by,
            used_at=c.used_at.isoformat() if c.used_at else None,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in codes
    ]


# ══════════════════════════════════════════════════════════════
#  桌面端激活（设备绑定）
# ══════════════════════════════════════════════════════════════

class ActivateLicenseRequest(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=128,
                           description="设备唯一标识（如 MAC 地址哈希 / 硬件指纹）")
    device_info: dict | None = Field(None,
                                     description="可选设备详情：hostname, os, arch, cpu 等")


class ActivateLicenseResponse(BaseModel):
    status: str
    license_code: str
    message: str


@router.post("/activate-license", response_model=ActivateLicenseResponse)
async def activate_license(
    req: ActivateLicenseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    桌面端首次登录时调用：绑定设备 ID 到授权码。
    - 若用户名下有已绑定该设备的授权码 → 直接通过
    - 若用户名下有未激活的授权码 → 绑定设备并标记激活
    - 若用户名下所有授权码都已绑定其他设备 → 拒绝
    """
    from app.models.billing import LicenseCode

    result = await db.execute(
        select(LicenseCode)
        .where(LicenseCode.owner_id == user.id)
        .order_by(LicenseCode.created_at)
    )
    licenses = result.scalars().all()

    if not licenses:
        raise HTTPException(403, "您还没有客户端授权码，请先在 Web 端兑换或领取")

    for lc in licenses:
        if lc.device_id == req.device_id:
            return ActivateLicenseResponse(
                status="already_activated",
                license_code=lc.code,
                message="该设备已激活",
            )

    unbound = next((lc for lc in licenses if not lc.is_used), None)
    if unbound is None:
        raise HTTPException(
            403,
            "授权码已绑定到其他设备，如需更换设备请在 Web 端「设置」中解绑（每 30 天可解绑 1 次）"
        )

    unbound.is_used = True
    unbound.device_id = req.device_id
    unbound.device_info = req.device_info
    unbound.used_by = user.phone or str(user.id)
    unbound.used_at = datetime.now()
    unbound.activated_at = datetime.now()
    await db.commit()

    logger.info(
        "授权码激活: user=%d code=%s device=%s",
        user.id, unbound.code, req.device_id,
    )

    return ActivateLicenseResponse(
        status="activated",
        license_code=unbound.code,
        message="激活成功，授权码已绑定到当前设备",
    )


class LicenseStatusResponse(BaseModel):
    has_license: bool
    activated: bool
    device_match: bool
    license_code: str | None = None
    message: str


@router.post("/license-status", response_model=LicenseStatusResponse)
async def check_license_status(
    req: ActivateLicenseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """桌面端定期检查授权状态：验证当前设备是否有有效绑定"""
    from app.models.billing import LicenseCode

    result = await db.execute(
        select(LicenseCode).where(
            LicenseCode.owner_id == user.id,
            LicenseCode.device_id == req.device_id,
            LicenseCode.is_used == True,
        ).limit(1)
    )
    matched = result.scalar_one_or_none()

    if matched:
        return LicenseStatusResponse(
            has_license=True, activated=True, device_match=True,
            license_code=matched.code,
            message="授权有效",
        )

    any_license = await db.execute(
        select(LicenseCode).where(LicenseCode.owner_id == user.id).limit(1)
    )
    has_any = any_license.scalar_one_or_none() is not None

    return LicenseStatusResponse(
        has_license=has_any, activated=False, device_match=False,
        message="当前设备未授权" if has_any else "无授权码",
    )


# ══════════════════════════════════════════════════════════════
#  用户自助解绑设备
# ══════════════════════════════════════════════════════════════

UNBIND_COOLDOWN_DAYS = 30


class UnbindDeviceResponse(BaseModel):
    success: bool
    message: str
    next_unbind_available_at: str | None = None


@router.post("/unbind-device", response_model=UnbindDeviceResponse)
async def unbind_device(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户自助解绑设备。30 天内仅可解绑 1 次。"""
    from app.models.billing import LicenseCode
    from datetime import timedelta, timezone

    result = await db.execute(
        select(LicenseCode).where(
            LicenseCode.owner_id == user.id,
            LicenseCode.is_used == True,
        ).limit(1)
    )
    activated = result.scalar_one_or_none()

    if not activated:
        raise HTTPException(400, "您没有已激活的授权码，无需解绑")

    if activated.last_unbound_at:
        cooldown_end = activated.last_unbound_at + timedelta(days=UNBIND_COOLDOWN_DAYS)
        now = datetime.now(timezone.utc)
        if now < cooldown_end:
            days_left = (cooldown_end - now).days + 1
            return UnbindDeviceResponse(
                success=False,
                message=f"解绑冷却中，还需等待 {days_left} 天",
                next_unbind_available_at=cooldown_end.isoformat(),
            )

    old_device = activated.device_id
    activated.device_id = None
    activated.device_info = None
    activated.is_used = False
    activated.activated_at = None
    activated.last_unbound_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "用户自助解绑: user=%d code=%s old_device=%s",
        user.id, activated.code, old_device,
    )

    return UnbindDeviceResponse(
        success=True,
        message="设备已解绑，您可以在新设备上重新激活",
    )

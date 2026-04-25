"""
积分服务 — 三级优先级扣费（赠送 → 推广 → 充值）
桌面模式下所有积分相关操作直接短路通过。
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import is_desktop
from app.models.user import User
from app.models.billing import UsageLog

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    def __init__(self, required: Decimal, available: Decimal):
        self.required = required
        self.available = available
        super().__init__(f"积分不足: 需要 {required}, 可用 {available}")


async def check_balance(user_id: int, required: Decimal, db: AsyncSession) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError(f"用户不存在: {user_id}")
    if is_desktop():
        return user
    if user.is_banned:
        raise PermissionError("账号已被封禁")
    available = user.total_available_credits
    if available < required:
        raise InsufficientCreditsError(required, available)
    return user


async def deduct_credits(
    user_id: int,
    cost: Decimal,
    db: AsyncSession,
    *,
    operation: str,
    article_id: int | None = None,
    section_id: int | None = None,
    meta: dict[str, Any] | None = None,
    aborted: bool = False,
) -> dict:
    if is_desktop():
        return {"success": True, "breakdown": {}, "remaining": Decimal("999999")}
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        return {"success": False, "reason": "user_not_found"}

    remaining_cost = cost
    breakdown: dict[str, float] = {}
    from datetime import timezone
    now_ts = datetime.now(timezone.utc)

    gift_deduct = Decimal("0")
    promo_deduct = Decimal("0")

    if (
        user.gift_credits > 0
        and (not user.gift_credits_expire_at or user.gift_credits_expire_at > now_ts)
    ):
        gift_deduct = min(user.gift_credits, remaining_cost)
        remaining_cost -= gift_deduct

    if remaining_cost > 0 and user.promo_credits > 0 and (
        not user.promo_credits_expire_at or user.promo_credits_expire_at > now_ts
    ):
        promo_deduct = min(user.promo_credits, remaining_cost)
        remaining_cost -= promo_deduct

    if remaining_cost > 0 and user.credits < remaining_cost:
        return {"success": False, "reason": "insufficient_credits"}

    if gift_deduct > 0:
        user.gift_credits -= gift_deduct
        breakdown["gift"] = float(gift_deduct)
    if promo_deduct > 0:
        user.promo_credits -= promo_deduct
        breakdown["promo"] = float(promo_deduct)
    if remaining_cost > 0:
        user.credits -= remaining_cost
        breakdown["credits"] = float(remaining_cost)

    user.total_consumed += cost

    log = UsageLog(
        user_id=user.id,
        article_id=article_id,
        section_id=section_id,
        operation=operation,
        cost=cost,
        breakdown=breakdown,
        meta=meta or {},
        aborted=aborted,
    )
    db.add(log)
    await db.flush()

    remaining = user.credits + user.gift_credits + user.promo_credits
    return {
        "success": True,
        "breakdown": breakdown,
        "remaining": remaining,
        "log_id": log.id,
    }


async def freeze_credits(user_id: int, amount: Decimal, db: AsyncSession) -> None:
    if is_desktop():
        return
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise ValueError(f"用户不存在: {user_id}")
    available = user.total_available_credits
    if available < amount:
        raise InsufficientCreditsError(amount, available)
    user.frozen_credits += amount
    await db.flush()


async def unfreeze_credits(user_id: int, amount: Decimal, db: AsyncSession) -> None:
    if is_desktop():
        return
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise ValueError(f"用户不存在: {user_id}")
    user.frozen_credits = max(Decimal("0"), user.frozen_credits - amount)
    await db.flush()


async def try_use_voucher(user_id: int, cost: Decimal, db: AsyncSession) -> Decimal:
    """尝试使用用户的有效补偿券抵扣费用，返回抵扣后的实际费用"""
    if is_desktop():
        return cost
    from app.models.billing import CompensationVoucher
    from datetime import timezone
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(CompensationVoucher).where(
            CompensationVoucher.user_id == user_id,
            CompensationVoucher.status == "active",
        ).order_by(CompensationVoucher.created_at.asc())
    )
    vouchers = result.scalars().all()

    for v in vouchers:
        if v.used_count >= v.max_uses:
            continue
        if v.expire_at and v.expire_at < now:
            v.status = "expired"
            continue
        discount = Decimal(str(v.discount_rate))
        actual = (cost * discount).quantize(Decimal("0.0001"))
        v.used_count += 1
        if v.used_count >= v.max_uses:
            v.status = "used_up"
        await db.flush()
        logger.info("补偿券 %d 已使用(%d/%d)，费用 %s → %s", v.id, v.used_count, v.max_uses, cost, actual)
        return actual

    return cost


async def add_credits(
    user_id: int,
    amount: Decimal,
    db: AsyncSession,
    *,
    credit_type: str = "credits",
) -> Decimal:
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise ValueError(f"用户不存在: {user_id}")

    if credit_type == "credits":
        user.credits += amount
        user.total_recharged += amount
        return user.credits
    elif credit_type == "gift_credits":
        user.gift_credits += amount
        return user.gift_credits
    elif credit_type == "promo_credits":
        user.promo_credits += amount
        return user.promo_credits
    else:
        raise ValueError(f"未知积分类型: {credit_type}")

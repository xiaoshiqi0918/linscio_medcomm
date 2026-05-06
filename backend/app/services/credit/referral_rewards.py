"""
推广返利逻辑 — 从 PaymentService 中抽取，供在线支付和兑换码充值共用。
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _promo_expire_at() -> datetime:
    from app.core.config import settings
    from dateutil.relativedelta import relativedelta
    return datetime.now(timezone.utc) + relativedelta(months=settings.promo_credits_validity_months)


async def grant_referral_recharge_reward(
    user_id: int,
    amount_yuan: Decimal,
    credits_to_add: Decimal,
    db: AsyncSession,
    *,
    source_id: int | None = None,
    source_type: str = "payment",
) -> None:
    """好友充值返推广积分：充值 >=50 元时，基础积分 10% 奖励给推荐人"""
    from app.models.user import User

    user = await db.get(User, user_id)
    if not user or not user.referred_by:
        return

    if amount_yuan < Decimal("50"):
        return

    reward = (credits_to_add * Decimal("0.10")).quantize(Decimal("0.0001"))
    if reward <= 0:
        return

    referrer = await db.get(User, user.referred_by)
    if not referrer:
        return

    referrer.promo_credits = (referrer.promo_credits or Decimal("0")) + reward
    referrer.promo_credits_expire_at = _promo_expire_at()

    try:
        from app.models.referral import ReferralLog
        log = ReferralLog(
            referrer_id=referrer.id,
            referred_id=user.id,
            trigger_type="recharge",
            related_recharge_id=source_id,
            reward_credits=reward,
        )
        db.add(log)
    except ImportError:
        pass

    logger.info(
        "推广返利[%s]: referrer=%d referred=%d reward=%s",
        source_type, referrer.id, user.id, reward,
    )


async def grant_referred_first_recharge_bonus(
    user_id: int,
    amount_yuan: Decimal,
    credits_to_add: Decimal,
    db: AsyncSession,
    *,
    source_id: int | None = None,
    source_type: str = "payment",
    exclude_order_id: int | None = None,
) -> None:
    """被推广人首次充值（>=50元）-> 本人获得本次充值额 20% 推广积分"""
    from app.models.user import User
    from app.models.billing import PaymentOrder, RedeemCode
    from app.services.payment.order_manager import OrderStatus

    user = await db.get(User, user_id)
    if not user or not user.referred_by:
        return

    if amount_yuan < Decimal("50"):
        return

    # Check prior paid payment orders
    po_q = select(PaymentOrder).where(
        PaymentOrder.user_id == user_id,
        PaymentOrder.status == OrderStatus.PAID,
    )
    if exclude_order_id:
        po_q = po_q.where(PaymentOrder.id != exclude_order_id)
    prior_payment = await db.execute(po_q.limit(1))
    if prior_payment.scalar_one_or_none() is not None:
        return

    # Check prior used redeem codes
    rc_q = select(RedeemCode).where(
        RedeemCode.used_by == user_id,
        RedeemCode.status == "used",
    )
    if source_type == "redeem_code" and source_id:
        rc_q = rc_q.where(RedeemCode.id != source_id)
    prior_redeem = await db.execute(rc_q.limit(1))
    if prior_redeem.scalar_one_or_none() is not None:
        return

    bonus = (credits_to_add * Decimal("0.20")).quantize(Decimal("0.0001"))
    if bonus <= 0:
        return

    user.promo_credits = (user.promo_credits or Decimal("0")) + bonus
    user.promo_credits_expire_at = _promo_expire_at()

    try:
        from app.models.referral import ReferralLog
        log = ReferralLog(
            referrer_id=user.referred_by,
            referred_id=user.id,
            trigger_type="first_recharge_bonus",
            related_recharge_id=source_id,
            reward_credits=bonus,
        )
        db.add(log)
    except ImportError:
        pass

    logger.info(
        "被推广人首充奖励[%s]: user=%d bonus=%s",
        source_type, user.id, bonus,
    )


async def grant_referral_license_download_reward(
    user_id: int,
    db: AsyncSession,
    *,
    source_id: int | None = None,
) -> bool:
    """
    被推广人首次成功下载客户端（且名下持有有效授权码）→ 推广人获得固定推广积分。

    幂等保护：若已存在 (referrer_id, referred_id, trigger_type='license_download') 的 ReferralLog，
    直接返回 False 不重复发放。

    返回 True 表示本次发放成功。
    """
    from app.core.config import settings
    from app.models.user import User
    from app.models.billing import LicenseCode
    from app.models.referral import ReferralLog

    user = await db.get(User, user_id)
    if not user or not user.referred_by:
        return False

    has_license = await db.scalar(
        select(LicenseCode.id).where(LicenseCode.owner_id == user_id).limit(1)
    )
    if not has_license:
        return False

    already = await db.scalar(
        select(ReferralLog.id).where(
            ReferralLog.referrer_id == user.referred_by,
            ReferralLog.referred_id == user.id,
            ReferralLog.trigger_type == "license_download",
        ).limit(1)
    )
    if already:
        return False

    referrer = await db.get(User, user.referred_by)
    if not referrer:
        return False

    reward = Decimal(str(settings.referral_license_download_reward))
    if reward <= 0:
        return False

    referrer.promo_credits = (referrer.promo_credits or Decimal("0")) + reward
    referrer.promo_credits_expire_at = _promo_expire_at()

    log = ReferralLog(
        referrer_id=referrer.id,
        referred_id=user.id,
        trigger_type="license_download",
        related_recharge_id=source_id,
        reward_credits=reward,
    )
    db.add(log)

    logger.info(
        "授权码下载奖励: referrer=%d referred=%d reward=%s",
        referrer.id, user.id, reward,
    )
    return True

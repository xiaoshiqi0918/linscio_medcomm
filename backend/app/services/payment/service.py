"""
PaymentService — 支付中台统一业务入口
所有支付操作（下单、回调、查询、关闭、退款）通过此服务调用，
API 层只做参数解析和权限校验。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, desc, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import PaymentOrder, RefundRecord
from app.services.payment.order_manager import (
    OrderStatus,
    transition_order,
    InvalidTransitionError,
    is_terminal,
)
from app.services.payment.registry import get_channel

logger = logging.getLogger(__name__)

RECHARGE_PLANS: dict[int, dict] = {
    10:  {"credits": 10,  "bonus": 0},
    50:  {"credits": 50,  "bonus": 3},
    100: {"credits": 100, "bonus": 8},
    300: {"credits": 300, "bonus": 30},
    500: {"credits": 500, "bonus": 60},
}


def _generate_order_no() -> str:
    return uuid.uuid4().hex[:24]


def _generate_refund_no() -> str:
    return f"R{uuid.uuid4().hex[:23]}"


class PaymentService:
    """支付中台服务，所有方法接收 db session，不自行管理事务边界"""

    # ── 创建订单 ──────────────────────────────────────────

    async def create_order(
        self,
        user_id: int,
        amount_yuan: int,
        channel_code: str,
        pay_method: str,
        client_ip: str,
        db: AsyncSession,
        user_agent: str = "",
    ) -> dict:
        plan = RECHARGE_PLANS.get(amount_yuan)
        if not plan:
            raise ValueError(f"不支持的充值金额: {amount_yuan} 元")

        adapter = get_channel(channel_code)
        order_no = _generate_order_no()
        amount_str = f"{amount_yuan}.00"

        order = PaymentOrder(
            user_id=user_id,
            order_no=order_no,
            channel_code=channel_code,
            amount_yuan=Decimal(amount_str),
            credits_to_add=Decimal(str(plan["credits"])),
            bonus_credits=Decimal(str(plan["bonus"])),
            pay_method=pay_method,
            status=OrderStatus.CREATED,
            client_ip=client_ip,
            user_agent=user_agent or None,
        )
        db.add(order)
        await db.flush()

        result = await adapter.create_payment(
            order_no=order_no,
            amount_yuan=amount_str,
            subject=f"LinScio MedComm 积分充值 {amount_yuan}元",
            pay_method=pay_method,
            client_ip=client_ip,
            extra={"param": str(user_id)},
        )

        if not result.success:
            order.status = OrderStatus.CLOSED.value
            order.closed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"success": False, "error": result.error}

        transition_order(order, OrderStatus.PAYING)
        order.channel_order_id = result.channel_order_id or None
        await db.commit()

        return {
            "success": True,
            "order_no": order_no,
            "qrcode": result.qrcode_url,
            "pay_page_url": result.pay_page_url,
            "amount_yuan": amount_yuan,
            "credits": plan["credits"],
            "bonus": plan["bonus"],
            "raw": result.raw_response,
        }

    # ── 回调处理（幂等） ──────────────────────────────────

    async def handle_callback(
        self,
        channel_code: str,
        params: dict,
        db: AsyncSession,
    ) -> str:
        adapter = get_channel(channel_code)

        if not adapter.verify_callback(params):
            logger.warning("支付回调签名验证失败: channel=%s params=%s", channel_code, params)
            return "fail"

        trade_status = params.get("trade_status", "")
        if trade_status != "TRADE_SUCCESS":
            return "success"

        order_no = params.get("out_trade_no", "")
        money = params.get("money", "0")

        order = await self._get_order_by_no(order_no, db)
        if not order:
            logger.warning("回调订单不存在: %s", order_no)
            return "fail"

        if order.status == OrderStatus.PAID:
            return "success"

        if str(order.amount_yuan) != money:
            logger.warning("回调金额不匹配: 订单 %s 期望 %s 实际 %s", order_no, order.amount_yuan, money)
            return "fail"

        order.notify_raw = params
        order.channel_order_id = params.get("trade_no", "") or order.channel_order_id
        await self._complete_payment(order, db)

        return "success"

    # ── 主动查询+同步 ─────────────────────────────────────

    async def query_and_sync(
        self,
        order_no: str,
        user_id: int | None,
        db: AsyncSession,
    ) -> dict:
        order = await self._get_order_by_no(order_no, db)
        if not order:
            return {"found": False}
        if user_id is not None and order.user_id != user_id:
            return {"found": False}

        if order.status in (OrderStatus.PAYING, OrderStatus.CREATED):
            adapter = get_channel(order.channel_code)
            remote = await adapter.query_order(order_no)
            if remote.success and remote.paid:
                order.channel_order_id = remote.channel_order_id or order.channel_order_id
                await self._complete_payment(order, db)

        return {
            "found": True,
            "order_no": order.order_no,
            "status": order.status,
            "amount_yuan": str(order.amount_yuan),
            "credits_to_add": float(order.credits_to_add),
            "bonus_credits": float(order.bonus_credits),
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }

    # ── 关闭未支付订单 ────────────────────────────────────

    async def close_order(self, order_no: str, user_id: int, db: AsyncSession) -> dict:
        order = await self._get_order_by_no(order_no, db)
        if not order or order.user_id != user_id:
            return {"success": False, "error": "订单不存在"}

        try:
            transition_order(order, OrderStatus.CLOSED)
        except InvalidTransitionError:
            return {"success": False, "error": f"当前状态 {order.status} 不允许关闭"}

        await db.commit()
        return {"success": True, "order_no": order_no, "status": order.status}

    # ── 退款 ──────────────────────────────────────────────

    async def refund(
        self,
        order_no: str,
        refund_amount_yuan: Decimal | None,
        reason: str,
        operator: str,
        db: AsyncSession,
    ) -> dict:
        """
        退款，自动适用业务规则：
        - 24h 内未消费 → 全额退款
        - 已消费 → 退未消费部分 - 5% 渠道手续费
        - 超过 7 天 → 不退款
        - refund_amount_yuan=None 时自动计算，传值时强制按该金额退（管理员覆盖）
        """
        order = await self._get_order_by_no(order_no, db)
        if not order:
            return {"success": False, "error": "订单不存在"}

        if order.status not in (OrderStatus.PAID, OrderStatus.PARTIAL_REFUND.value):
            return {"success": False, "error": f"当前状态 {order.status} 不允许退款"}

        CHANNEL_FEE_RATE = Decimal("0.05")
        now = datetime.now(timezone.utc)
        paid_at = order.paid_at
        if paid_at and paid_at.tzinfo is None:
            from datetime import timezone as _tz
            paid_at = paid_at.replace(tzinfo=_tz.utc)

        if refund_amount_yuan is None:
            if paid_at and (now - paid_at).days >= 7:
                return {"success": False, "error": "充值超过 7 天，不可退款。余额可继续使用"}

            from app.models.billing import UsageLog
            consumed_q = await db.execute(
                select(func.coalesce(func.sum(UsageLog.cost), 0))
                .where(UsageLog.user_id == order.user_id)
                .where(UsageLog.created_at >= order.paid_at)
            )
            consumed_credits = Decimal(str(consumed_q.scalar() or 0))
            total_credits = order.credits_to_add + order.bonus_credits

            if paid_at and (now - paid_at).total_seconds() < 86400 and consumed_credits == 0:
                refund_amount_yuan = order.amount_yuan
            else:
                unused_ratio = max(Decimal("0"), (total_credits - consumed_credits) / total_credits) if total_credits > 0 else Decimal("0")
                raw_refund = (order.amount_yuan * unused_ratio).quantize(Decimal("0.01"))
                fee = (raw_refund * CHANNEL_FEE_RATE).quantize(Decimal("0.01"))
                refund_amount_yuan = max(Decimal("0"), raw_refund - fee)

            if refund_amount_yuan <= 0:
                return {"success": False, "error": "已消费完毕，无可退金额"}

        remaining = order.amount_yuan - (order.refunded_amount or Decimal("0"))
        if refund_amount_yuan > remaining:
            return {"success": False, "error": f"退款金额 {refund_amount_yuan} 超过可退 {remaining}"}

        adapter = get_channel(order.channel_code)
        refund_no = _generate_refund_no()

        try:
            result = await adapter.refund(order_no, str(refund_amount_yuan), reason)
        except NotImplementedError:
            result = None

        ratio = refund_amount_yuan / order.amount_yuan
        credits_to_deduct = ((order.credits_to_add + order.bonus_credits) * ratio).quantize(Decimal("0.0001"))

        refund_record = RefundRecord(
            order_id=order.id,
            refund_no=refund_no,
            channel_refund_id=result.refund_id if result and result.success else None,
            refund_amount_yuan=refund_amount_yuan,
            credits_deducted=credits_to_deduct,
            reason=reason,
            status="success" if (result is None or result.success) else "pending",
            operator=operator,
            completed_at=datetime.now(timezone.utc) if (result is None or result.success) else None,
        )
        db.add(refund_record)

        order.refunded_amount = (order.refunded_amount or Decimal("0")) + refund_amount_yuan
        new_status = (
            OrderStatus.FULL_REFUND if order.refunded_amount >= order.amount_yuan
            else OrderStatus.PARTIAL_REFUND
        )
        transition_order(order, new_status)

        from app.services.credit.service import deduct_credits
        await deduct_credits(
            user_id=order.user_id,
            cost=credits_to_deduct,
            db=db,
            operation="refund_deduction",
            meta={"order_no": order_no, "refund_no": refund_no},
        )

        await db.commit()

        return {
            "success": True,
            "refund_no": refund_no,
            "refund_amount": str(refund_amount_yuan),
            "credits_deducted": float(credits_to_deduct),
            "order_status": order.status,
        }

    # ── 订单列表 ──────────────────────────────────────────

    async def list_orders(
        self,
        user_id: int,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status_filter: str | None = None,
    ) -> dict:
        query = (
            select(PaymentOrder)
            .where(PaymentOrder.user_id == user_id)
            .order_by(desc(PaymentOrder.created_at))
        )
        if status_filter:
            query = query.where(PaymentOrder.status == status_filter)

        count_query = select(PaymentOrder.id).where(PaymentOrder.user_id == user_id)
        if status_filter:
            count_query = count_query.where(PaymentOrder.status == status_filter)

        from sqlalchemy import func
        total_result = await db.execute(select(func.count()).select_from(count_query.subquery()))
        total = total_result.scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        orders = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._order_to_dict(o) for o in orders],
        }

    # ── 单个订单详情 ──────────────────────────────────────

    async def get_order_detail(
        self,
        order_no: str,
        user_id: int | None,
        db: AsyncSession,
    ) -> dict | None:
        order = await self._get_order_by_no(order_no, db)
        if not order:
            return None
        if user_id is not None and order.user_id != user_id:
            return None
        return self._order_to_dict(order)

    # ── 批量过期未支付订单 ────────────────────────────────

    async def expire_stale_orders(
        self,
        timeout_minutes: int,
        db: AsyncSession,
    ) -> int:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

        result = await db.execute(
            select(PaymentOrder).where(
                and_(
                    PaymentOrder.status.in_([OrderStatus.CREATED, OrderStatus.PAYING]),
                    PaymentOrder.created_at < cutoff,
                )
            )
        )
        stale = result.scalars().all()
        count = 0
        for order in stale:
            try:
                transition_order(order, OrderStatus.EXPIRED)
                count += 1
            except InvalidTransitionError:
                pass

        if count > 0:
            await db.commit()
            logger.info("已过期 %d 个超时订单", count)
        return count

    # ── 私有方法 ──────────────────────────────────────────

    async def _complete_payment(self, order: PaymentOrder, db: AsyncSession) -> None:
        """到账处理（幂等）：转状态 + 加积分 + 推广返利 + 被推广人首充奖励"""
        if order.status == OrderStatus.PAID:
            return

        transition_order(order, OrderStatus.PAID)

        from app.services.credit.service import add_credits
        total = order.credits_to_add + order.bonus_credits
        await add_credits(order.user_id, total, db, credit_type="credits")

        await self._grant_referral_recharge_reward(order, db)
        await self._grant_referred_first_recharge_bonus(order, db)

        await db.commit()

        logger.info(
            "支付到账: user=%d order=%s amount=%s credits=%s bonus=%s",
            order.user_id, order.order_no, order.amount_yuan,
            order.credits_to_add, order.bonus_credits,
        )

    def _promo_expire_at(self) -> datetime:
        from app.core.config import settings
        from dateutil.relativedelta import relativedelta
        return datetime.now(timezone.utc) + relativedelta(months=settings.promo_credits_validity_months)

    async def _grant_referral_recharge_reward(
        self, order: PaymentOrder, db: AsyncSession
    ) -> None:
        from app.services.credit.referral_rewards import grant_referral_recharge_reward
        await grant_referral_recharge_reward(
            order.user_id, order.amount_yuan, order.credits_to_add, db,
            source_id=order.id, source_type="payment",
        )

    async def _grant_referred_first_recharge_bonus(
        self, order: PaymentOrder, db: AsyncSession
    ) -> None:
        from app.services.credit.referral_rewards import grant_referred_first_recharge_bonus
        await grant_referred_first_recharge_bonus(
            order.user_id, order.amount_yuan, order.credits_to_add, db,
            source_id=order.id, source_type="payment",
            exclude_order_id=order.id,
        )

    async def _get_order_by_no(self, order_no: str, db: AsyncSession) -> PaymentOrder | None:
        result = await db.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        return result.scalar_one_or_none()

    def _order_to_dict(self, o: PaymentOrder) -> dict:
        return {
            "id": o.id,
            "order_no": o.order_no,
            "channel_code": o.channel_code,
            "amount_yuan": str(o.amount_yuan),
            "credits_to_add": float(o.credits_to_add),
            "bonus_credits": float(o.bonus_credits),
            "pay_method": o.pay_method,
            "status": o.status,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "refunded_amount": str(o.refunded_amount or 0),
        }


payment_service = PaymentService()

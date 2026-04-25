"""
对账服务
每日定时拉取渠道账单与本地 PaymentOrder 进行比对，
发现差异写入 ReconciliationLog，自动补单漏到账的订单。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import PaymentOrder, ReconciliationLog
from app.services.payment.order_manager import OrderStatus
from app.services.payment.registry import list_channels, get_channel

logger = logging.getLogger(__name__)


async def run_reconciliation(bill_date: date, db: AsyncSession) -> None:
    """对 bill_date 当天的所有渠道执行对账"""
    for channel_code in list_channels():
        try:
            await _reconcile_channel(channel_code, bill_date, db)
        except Exception:
            logger.exception("对账失败: channel=%s date=%s", channel_code, bill_date)


async def _reconcile_channel(channel_code: str, bill_date: date, db: AsyncSession) -> None:
    adapter = get_channel(channel_code)

    start_dt = datetime(bill_date.year, bill_date.month, bill_date.day, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)

    result = await db.execute(
        select(PaymentOrder).where(
            and_(
                PaymentOrder.channel_code == channel_code,
                PaymentOrder.created_at >= start_dt,
                PaymentOrder.created_at < end_dt,
            )
        )
    )
    local_orders = result.scalars().all()

    try:
        channel_bills = await adapter.download_bill(bill_date.isoformat())
    except NotImplementedError:
        channel_bills = []

    total_orders = len(local_orders)
    matched = 0
    mismatched = 0
    total_amount = Decimal("0")
    matched_amount = Decimal("0")
    diff_details: list[dict] = []

    if channel_bills:
        channel_map = {b.get("order_no", b.get("out_trade_no", "")): b for b in channel_bills}

        for order in local_orders:
            total_amount += order.amount_yuan
            bill = channel_map.pop(order.order_no, None)

            if bill is None:
                if order.status == OrderStatus.PAID:
                    mismatched += 1
                    diff_details.append({
                        "type": "local_paid_no_channel",
                        "order_no": order.order_no,
                        "amount": str(order.amount_yuan),
                    })
                else:
                    matched += 1
                    matched_amount += order.amount_yuan
            else:
                bill_status = bill.get("status", "")
                bill_amount = bill.get("money", bill.get("amount", "0"))
                if order.status == OrderStatus.PAID and str(order.amount_yuan) == str(bill_amount):
                    matched += 1
                    matched_amount += order.amount_yuan
                else:
                    mismatched += 1
                    diff_details.append({
                        "type": "amount_or_status_mismatch",
                        "order_no": order.order_no,
                        "local_status": order.status,
                        "local_amount": str(order.amount_yuan),
                        "channel_status": bill_status,
                        "channel_amount": str(bill_amount),
                    })

        for order_no, bill in channel_map.items():
            mismatched += 1
            diff_details.append({
                "type": "channel_paid_no_local",
                "order_no": order_no,
                "channel_amount": str(bill.get("money", bill.get("amount", "0"))),
            })
    else:
        for order in local_orders:
            total_amount += order.amount_yuan

            if order.status in (OrderStatus.CREATED, OrderStatus.PAYING):
                remote = await adapter.query_order(order.order_no)
                if remote.success and remote.paid:
                    from app.services.payment.service import payment_service
                    order.channel_order_id = remote.channel_order_id or order.channel_order_id
                    await payment_service._complete_payment(order, db)
                    diff_details.append({
                        "type": "auto_补单",
                        "order_no": order.order_no,
                        "amount": str(order.amount_yuan),
                    })
                    mismatched += 1
                else:
                    matched += 1
            else:
                matched += 1
                if order.status == OrderStatus.PAID:
                    matched_amount += order.amount_yuan

    diff_amount = total_amount - matched_amount
    status = "completed" if mismatched == 0 else "has_diff"

    recon = ReconciliationLog(
        bill_date=bill_date,
        channel_code=channel_code,
        total_orders=total_orders,
        matched_orders=matched,
        mismatched_orders=mismatched,
        total_amount=total_amount,
        matched_amount=matched_amount,
        diff_amount=diff_amount,
        details=diff_details if diff_details else None,
        status=status,
    )
    db.add(recon)
    await db.commit()

    logger.info(
        "对账完成: channel=%s date=%s total=%d matched=%d mismatch=%d diff=¥%s",
        channel_code, bill_date, total_orders, matched, mismatched, diff_amount,
    )

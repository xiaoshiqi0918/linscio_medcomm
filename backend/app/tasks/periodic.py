"""
SaaS 定时任务 — 基于 asyncio 的轻量级后台调度
在应用 lifespan 中启动，关闭时自动取消。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_running_tasks: list[asyncio.Task] = []


async def _expire_stale_orders_loop(interval_seconds: int = 300):
    """每 5 分钟检查一次，关闭超时未支付的订单"""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            from app.core.config import settings
            from app.core.database import AsyncSessionLocal
            from app.services.payment.service import payment_service

            async with AsyncSessionLocal() as db:
                count = await payment_service.expire_stale_orders(
                    timeout_minutes=settings.order_expire_minutes, db=db,
                )
                if count > 0:
                    logger.info("定时过期: 已关闭 %d 个超时订单", count)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("定时过期订单任务异常")


async def _daily_reconciliation_loop():
    """每日凌晨 2:00 执行前一天的对账"""
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 18  # UTC 18:00 ≈ CST 02:00
            if now.hour >= target_hour:
                from datetime import timedelta
                tomorrow = now.date() + timedelta(days=1)
                target = datetime(tomorrow.year, tomorrow.month, tomorrow.day, target_hour, 0, 0, tzinfo=timezone.utc)
            else:
                target = datetime(now.year, now.month, now.day, target_hour, 0, 0, tzinfo=timezone.utc)

            wait_seconds = (target - now).total_seconds()
            logger.info("对账任务将在 %.0f 秒后执行", wait_seconds)
            await asyncio.sleep(wait_seconds)

            from app.core.database import AsyncSessionLocal
            from app.services.payment.reconciliation import run_reconciliation
            from datetime import timedelta

            bill_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
            async with AsyncSessionLocal() as db:
                await run_reconciliation(bill_date, db)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("每日对账任务异常")
            await asyncio.sleep(3600)


async def _cleanup_stale_streaming_sessions_loop(interval_seconds: int = 60):
    """每分钟扫描超时心跳的孤儿 SSE 会话，按已记录 token 扣费"""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            from app.core.database import AsyncSessionLocal
            from app.services.streaming_session import cleanup_stale_sessions

            async with AsyncSessionLocal() as db:
                count = await cleanup_stale_sessions(db)
                if count > 0:
                    logger.info("定时清理: 处理了 %d 个超时 SSE 会话", count)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("定时清理 SSE 会话任务异常")


async def _daily_balance_snapshot_loop():
    """每日 23:55 UTC (约 CST 07:55) 写入余额快照，作为对账锚点"""
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 15  # UTC 15:55 ≈ CST 23:55
            target_minute = 55
            if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
                from datetime import timedelta
                tomorrow = now.date() + timedelta(days=1)
                target = datetime(tomorrow.year, tomorrow.month, tomorrow.day,
                                  target_hour, target_minute, 0, tzinfo=timezone.utc)
            else:
                target = datetime(now.year, now.month, now.day,
                                  target_hour, target_minute, 0, tzinfo=timezone.utc)

            wait_seconds = (target - now).total_seconds()
            logger.info("余额快照任务将在 %.0f 秒后执行", wait_seconds)
            await asyncio.sleep(wait_seconds)

            from app.core.database import AsyncSessionLocal
            from app.services.observability import daily_balance_snapshot

            async with AsyncSessionLocal() as db:
                await daily_balance_snapshot(db)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("每日余额快照任务异常")
            await asyncio.sleep(3600)


async def _daily_credit_reconciliation_loop():
    """每日 UTC 19:00 (约 CST 03:00) 执行积分对账"""
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 19
            if now.hour >= target_hour:
                from datetime import timedelta
                tomorrow = now.date() + timedelta(days=1)
                target = datetime(tomorrow.year, tomorrow.month, tomorrow.day,
                                  target_hour, 0, 0, tzinfo=timezone.utc)
            else:
                target = datetime(now.year, now.month, now.day,
                                  target_hour, 0, 0, tzinfo=timezone.utc)

            wait_seconds = (target - now).total_seconds()
            logger.info("积分对账任务将在 %.0f 秒后执行", wait_seconds)
            await asyncio.sleep(wait_seconds)

            from app.core.database import AsyncSessionLocal
            from app.services.observability import daily_credit_reconciliation

            async with AsyncSessionLocal() as db:
                await daily_credit_reconciliation(db)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("每日积分对账任务异常")
            await asyncio.sleep(3600)


def start_periodic_tasks():
    """启动所有定时任务（在 lifespan 中调用）"""
    _running_tasks.append(asyncio.create_task(_expire_stale_orders_loop()))
    _running_tasks.append(asyncio.create_task(_daily_reconciliation_loop()))
    _running_tasks.append(asyncio.create_task(_cleanup_stale_streaming_sessions_loop()))
    _running_tasks.append(asyncio.create_task(_daily_balance_snapshot_loop()))
    _running_tasks.append(asyncio.create_task(_daily_credit_reconciliation_loop()))
    logger.info("已启动 %d 个定时任务", len(_running_tasks))


async def stop_periodic_tasks():
    """取消所有定时任务（在 lifespan 中调用）"""
    for task in _running_tasks:
        task.cancel()
    if _running_tasks:
        await asyncio.gather(*_running_tasks, return_exceptions=True)
    _running_tasks.clear()
    logger.info("已停止所有定时任务")

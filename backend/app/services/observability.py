"""
可观测性服务 — 告警 / 快照 / 对账 / Prometheus 指标
仅在 SaaS 模式下活跃；桌面端调用安全空跑。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 1. send_alert — 微信 Webhook 推送告警
# ═══════════════════════════════════════════════════════════════════

async def send_alert(alert_type: str, payload: dict | list | str) -> None:
    """发送告警到微信企业机器人 Webhook（静默失败）"""
    try:
        from app.core.config import settings
        webhook = settings.alert_wechat_webhook
        if not webhook:
            logger.warning("send_alert: ALERT_WECHAT_WEBHOOK 未配置，跳过")
            return

        import httpx

        body = {
            "msgtype": "markdown",
            "markdown": {
                "content": (
                    f"**[MedComm SaaS 告警]** `{alert_type}`\n\n"
                    f"```json\n{_truncate(str(payload), 2000)}\n```"
                ),
            },
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook, json=body)
            if resp.status_code != 200:
                logger.error("send_alert HTTP %d: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.error("send_alert 失败: %s", exc)


def _truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[:max_len] + "..."


# ═══════════════════════════════════════════════════════════════════
# 2. 每日余额快照
# ═══════════════════════════════════════════════════════════════════

async def daily_balance_snapshot(db: AsyncSession, snapshot_dt: date | None = None):
    """为所有活跃用户写入余额快照"""
    from app.models.user import User
    from app.models.billing import UserBalanceSnapshot

    target_date = snapshot_dt or datetime.now(timezone.utc).date()

    result = await db.execute(
        select(User).where(User.is_active == True)  # noqa: E712
    )
    users = result.scalars().all()

    created = 0
    for user in users:
        exists = await db.execute(
            select(UserBalanceSnapshot.id).where(
                UserBalanceSnapshot.user_id == user.id,
                UserBalanceSnapshot.snapshot_date == target_date,
            )
        )
        if exists.scalar():
            continue

        db.add(UserBalanceSnapshot(
            user_id=user.id,
            snapshot_date=target_date,
            credits=user.credits or 0,
            gift_credits=user.gift_credits or 0,
            promo_credits=user.promo_credits or 0,
            frozen_credits=user.frozen_credits or 0,
        ))
        created += 1

    await db.commit()
    logger.info("每日快照: %s 创建 %d 条，共 %d 个活跃用户", target_date, created, len(users))
    return created


# ═══════════════════════════════════════════════════════════════════
# 3. 每日积分对账
# ═══════════════════════════════════════════════════════════════════

async def daily_credit_reconciliation(db: AsyncSession, bill_date: date | None = None):
    """对账：用户余额变动 == 流水汇总，返回异常列表"""
    from app.models.user import User
    from app.models.billing import UsageLog, RechargeLog, UserBalanceSnapshot

    target = bill_date or (datetime.now(timezone.utc) - timedelta(days=1)).date()
    yesterday = target - timedelta(days=1)

    day_start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    discrepancies: list[dict] = []

    result = await db.execute(
        select(User).where(User.is_active == True)  # noqa: E712
    )
    users = result.scalars().all()

    for user in users:
        usage_row = await db.execute(
            select(func.coalesce(func.sum(UsageLog.cost), 0)).where(
                UsageLog.user_id == user.id,
                UsageLog.created_at >= day_start,
                UsageLog.created_at < day_end,
            )
        )
        usage_sum = Decimal(str(usage_row.scalar() or 0))

        recharge_row = await db.execute(
            select(
                func.coalesce(func.sum(RechargeLog.credits_added + RechargeLog.bonus_credits), 0)
            ).where(
                RechargeLog.user_id == user.id,
                RechargeLog.status == "paid",
                RechargeLog.created_at >= day_start,
                RechargeLog.created_at < day_end,
            )
        )
        recharge_sum = Decimal(str(recharge_row.scalar() or 0))

        expected_delta = recharge_sum - usage_sum

        snap_yesterday = await db.execute(
            select(UserBalanceSnapshot).where(
                UserBalanceSnapshot.user_id == user.id,
                UserBalanceSnapshot.snapshot_date == yesterday,
            )
        )
        snap_y = snap_yesterday.scalar()
        if not snap_y:
            continue

        balance_yesterday = (
            Decimal(str(snap_y.credits or 0))
            + Decimal(str(snap_y.gift_credits or 0))
        )

        balance_today = Decimal(str(user.credits or 0)) + Decimal(str(user.gift_credits or 0))
        actual_delta = balance_today - balance_yesterday

        diff = abs(actual_delta - expected_delta)
        if diff > Decimal("0.01"):
            discrepancies.append({
                "user_id": user.id,
                "expected_delta": str(expected_delta),
                "actual_delta": str(actual_delta),
                "diff": str(diff),
            })

    if discrepancies:
        logger.warning("积分对账异常: %d 个用户, %s", len(discrepancies), discrepancies)
        await send_alert("credit_reconciliation_failed", discrepancies)
    else:
        logger.info("积分对账: %s 全部通过 (%d 个用户)", target, len(users))

    return discrepancies


# ═══════════════════════════════════════════════════════════════════
# 4. Prometheus 指标
# ═══════════════════════════════════════════════════════════════════

_METRICS_REGISTRY: dict | None = None


def _ensure_metrics():
    """懒初始化 Prometheus 指标"""
    global _METRICS_REGISTRY
    if _METRICS_REGISTRY is not None:
        return _METRICS_REGISTRY

    try:
        from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

        registry = CollectorRegistry()
        _METRICS_REGISTRY = {
            "registry": registry,
            "llm_calls": Counter(
                "medcomm_llm_calls_total",
                "LLM 调用总数",
                ["task_type", "model", "status"],
                registry=registry,
            ),
            "llm_latency": Histogram(
                "medcomm_llm_latency_seconds",
                "LLM 调用延迟",
                ["task_type", "model"],
                buckets=[0.5, 1, 2, 5, 10, 30, 60],
                registry=registry,
            ),
            "llm_cost_usd": Counter(
                "medcomm_llm_cost_usd_total",
                "LLM 累计成本 (USD)",
                ["model"],
                registry=registry,
            ),
            "sse_active": Gauge(
                "medcomm_sse_active_connections",
                "当前活跃 SSE 连接数",
                registry=registry,
            ),
            "sse_disconnects": Counter(
                "medcomm_sse_disconnects_total",
                "SSE 异常断开次数",
                ["reason"],
                registry=registry,
            ),
            "http_requests": Counter(
                "medcomm_http_requests_total",
                "HTTP 请求数",
                ["method", "path", "status"],
                registry=registry,
            ),
            "http_latency": Histogram(
                "medcomm_http_latency_seconds",
                "HTTP 请求延迟",
                ["method", "path"],
                buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5],
                registry=registry,
            ),
            "credits_used": Counter(
                "medcomm_credits_used_total",
                "积分消耗总量",
                ["operation"],
                registry=registry,
            ),
            "recharge_amount": Counter(
                "medcomm_recharge_yuan_total",
                "充值金额 (元)",
                registry=registry,
            ),
        }
        return _METRICS_REGISTRY
    except ImportError:
        logger.debug("prometheus_client 未安装，指标暴露不可用")
        return None


def record_llm_call(task_type: str, model: str, status: str,
                    latency_s: float = 0, cost_usd: float = 0):
    """在 Prometheus 中记录一次 LLM 调用"""
    m = _ensure_metrics()
    if not m:
        return
    m["llm_calls"].labels(task_type=task_type, model=model, status=status).inc()
    if latency_s > 0:
        m["llm_latency"].labels(task_type=task_type, model=model).observe(latency_s)
    if cost_usd > 0:
        m["llm_cost_usd"].labels(model=model).inc(cost_usd)


def record_http_request(method: str, path: str, status: int, latency_s: float):
    """在 Prometheus 中记录 HTTP 请求"""
    m = _ensure_metrics()
    if not m:
        return
    m["http_requests"].labels(method=method, path=path, status=str(status)).inc()
    m["http_latency"].labels(method=method, path=path).observe(latency_s)


def record_credits_used(operation: str, amount: float):
    """记录积分消耗"""
    m = _ensure_metrics()
    if not m:
        return
    m["credits_used"].labels(operation=operation).inc(amount)


def record_recharge(amount_yuan: float):
    """记录充值金额"""
    m = _ensure_metrics()
    if not m:
        return
    m["recharge_amount"].inc(amount_yuan)


def get_prometheus_registry():
    """获取 prometheus registry，用于 /metrics 端点"""
    m = _ensure_metrics()
    return m["registry"] if m else None

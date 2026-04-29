"""
统一计费服务 — billing_session 生命周期管理

流程：start → (LLM 调用自动记录到 llm_call_logs) → settle / abort
结算时从 llm_call_logs 聚合真实 token 用量，按 model_prices 计算积分。
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func as sa_func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import is_saas, is_desktop

logger = logging.getLogger(__name__)

_STALE_THRESHOLD_MINUTES = 10
_MAX_CONCURRENT_SESSIONS = 5
_DEFAULT_MARKUP = Decimal("8.0")


async def start_billing_session(
    user_id: int,
    business_type: str,
    estimated_cost: Decimal,
    db: AsyncSession,
    *,
    business_ref: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> str:
    """开启计费会话：幂等检查 → 预检余额 → 冻结积分 → 创建 session 记录。
    idempotency_key 非空时，重复请求直接返回已有 session_id（防止重复扣费）。
    """
    if not is_saas():
        return str(uuid.uuid4())

    if idempotency_key:
        from app.models.billing import BillingSession
        existing = await db.execute(
            select(BillingSession).where(
                BillingSession.user_id == user_id,
                BillingSession.idempotency_key == idempotency_key,
            )
        )
        found = existing.scalar_one_or_none()
        if found:
            logger.info("idempotent hit: user=%d key=%s → session=%s", user_id, idempotency_key, found.session_id)
            return found.session_id

    from app.services.credit.service import check_balance, freeze_credits
    await check_balance(user_id, estimated_cost, db)
    await freeze_credits(user_id, estimated_cost, db)

    from app.models.billing import BillingSession
    session_id = str(uuid.uuid4())
    session = BillingSession(
        session_id=session_id,
        user_id=user_id,
        business_type=business_type,
        business_ref=business_ref,
        idempotency_key=idempotency_key,
        estimated_cost=estimated_cost,
        status="computing",
    )
    db.add(session)
    await db.flush()
    return session_id


async def settle_billing_session(
    session_id: str,
    db: AsyncSession,
    *,
    override_cost: Decimal | None = None,
) -> Decimal:
    """正常结算。override_cost 用于非 LLM 流程（翻译/导出），直接指定费用；
    默认从 llm_call_logs 聚合计算。最终不超过 estimated_cost。
    """
    if not is_saas():
        return Decimal("0")

    from app.models.billing import BillingSession
    session = await db.get(BillingSession, session_id, with_for_update=True)
    if not session or session.status not in ("computing", "pending"):
        return Decimal("0")

    if override_cost is not None:
        actual_cost = override_cost
    else:
        actual_cost = await _calc_session_cost(session_id, db)
    actual_cost = min(actual_cost, session.estimated_cost)

    from app.services.credit.service import unfreeze_credits, deduct_credits
    await unfreeze_credits(session.user_id, session.estimated_cost, db)

    if actual_cost > 0:
        await deduct_credits(
            session.user_id, actual_cost, db,
            operation=session.business_type,
            meta={
                "billing_session_id": session_id,
                "business_ref": session.business_ref,
            },
        )

    session.status = "settled"
    session.actual_cost = actual_cost
    session.settled_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(
        "billing_session settled: %s type=%s estimated=%s actual=%s",
        session_id, session.business_type, session.estimated_cost, actual_cost,
    )
    return actual_cost


async def abort_billing_session(
    session_id: str,
    db: AsyncSession,
    *,
    reason: str = "client_disconnect",
) -> Decimal:
    """中断结算：策略 A — 全额退还，不向用户收费。
    失败的 LLM 调用成本由平台承担（早期体验优先）。
    后期可改为策略 B（按已成功的 token 比例结算）。
    """
    if not is_saas():
        return Decimal("0")

    from app.models.billing import BillingSession
    session = await db.get(BillingSession, session_id, with_for_update=True)
    if not session or session.status not in ("computing", "pending"):
        return Decimal("0")

    from app.services.credit.service import unfreeze_credits
    await unfreeze_credits(session.user_id, session.estimated_cost, db)

    session.status = "aborted"
    session.actual_cost = Decimal("0")
    session.settled_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(
        "billing_session aborted (full refund): %s reason=%s estimated=%s",
        session_id, reason, session.estimated_cost,
    )
    return Decimal("0")


async def touch_billing_session(session_id: str, db: AsyncSession) -> None:
    """更新心跳时间，防止被清理"""
    if not is_saas():
        return
    from app.models.billing import BillingSession
    session = await db.get(BillingSession, session_id)
    if session and session.status == "computing":
        session.last_activity_at = datetime.now(timezone.utc)
        await db.flush()


async def cleanup_stale_billing_sessions(db: AsyncSession) -> int:
    """清理超时的计费会话"""
    if not is_saas():
        return 0

    from app.models.billing import BillingSession
    threshold = datetime.now(timezone.utc) - timedelta(minutes=_STALE_THRESHOLD_MINUTES)
    result = await db.execute(
        select(BillingSession).where(
            BillingSession.status == "computing",
            BillingSession.last_activity_at < threshold,
        )
    )
    stale = result.scalars().all()
    count = 0
    for s in stale:
        try:
            await abort_billing_session(s.session_id, db, reason="server_timeout")
            count += 1
        except Exception as exc:
            logger.error("清理超时计费会话 %s 失败: %s", s.session_id, exc)
    if count > 0:
        await db.commit()
        logger.info("清理了 %d 个超时计费会话", count)
    return count


async def estimate_cost_for_task(
    business_type: str,
    input_chars: int = 0,
    target_word_count: int = 0,
) -> Decimal:
    """根据业务类型预估费用，用于前端展示和余额预检。
    这里保留简单的阶梯预估，实际结算以 token 用量为准。"""
    from app.services.credit.pricing import (
        calc_generation_cost, calc_literature_cost, calc_optimization_cost,
        calc_translation_cost, calc_ai_assist_cost, calc_literature_filter_cost,
        calc_medpic_prompt_cost, calc_keyword_design_cost,
        LiteratureAnalysisMode,
    )
    if business_type == "generation":
        return calc_generation_cost(target_word_count or 2000)
    elif business_type == "literature_analyze":
        return calc_literature_cost(input_chars, LiteratureAnalysisMode.ABSTRACT)
    elif business_type == "translation":
        return calc_translation_cost(input_chars)
    elif business_type == "polish":
        return calc_optimization_cost(input_chars)
    elif business_type == "ai_assist":
        return calc_ai_assist_cost(input_chars)
    elif business_type == "literature_filter":
        return calc_literature_filter_cost(input_chars)
    elif business_type == "medpic_prompt":
        return calc_medpic_prompt_cost()
    elif business_type == "keyword_design":
        return calc_keyword_design_cost()
    return Decimal("1")


# ── 内部：从 llm_call_logs 聚合 session 成本 ─────────────────

async def _calc_session_cost(session_id: str, db: AsyncSession) -> Decimal:
    """查询 billing_session 内所有 LLM 调用，按 model_prices 计算积分"""
    from app.models.billing import LlmCallLog, ModelPrice

    result = await db.execute(
        select(
            LlmCallLog.model,
            sa_func.sum(LlmCallLog.tokens_in).label("total_in"),
            sa_func.sum(LlmCallLog.tokens_out).label("total_out"),
        )
        .where(
            LlmCallLog.billing_session_id == session_id,
            LlmCallLog.cost_billable == True,
        )
        .group_by(LlmCallLog.model)
    )
    rows = result.all()

    if not rows:
        return Decimal("0")

    prices_result = await db.execute(
        select(ModelPrice).where(ModelPrice.is_active == True)
    )
    prices = {p.model: p for p in prices_result.scalars().all()}

    total_credits = Decimal("0")
    for model_name, total_in, total_out in rows:
        tokens_in = int(total_in or 0)
        tokens_out = int(total_out or 0)
        price = prices.get(model_name)
        if price:
            cost_usd = (
                Decimal(tokens_in) / Decimal("1000000") * price.price_in_per_mtok
                + Decimal(tokens_out) / Decimal("1000000") * price.price_out_per_mtok
            )
            credits = cost_usd * price.markup_ratio
        else:
            credits = (Decimal(tokens_in + tokens_out) / Decimal("1000000") * Decimal("2") * _DEFAULT_MARKUP)
        total_credits += credits

    return total_credits.quantize(Decimal("0.01"))

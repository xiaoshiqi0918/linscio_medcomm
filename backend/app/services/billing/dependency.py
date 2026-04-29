"""
FastAPI 计费会话依赖 — 两种用法：

1. 非流式（普通请求）：使用 billing_session dependency
2. SSE 流式：手动调用 open_billing_session / close_billing_session

提供 contextvars 让 openai_client 自动拿到当前 billing_session_id。
"""
import contextvars
import logging
from decimal import Decimal
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import is_saas

logger = logging.getLogger(__name__)

# ── 全局 contextvar：当前线程/协程的 billing_session_id ──
current_billing_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_billing_session_id", default=None,
)


def get_billing_session_id() -> str | None:
    """供 openai_client 等底层模块调用，获取当前 billing_session_id"""
    return current_billing_session_id.get()


async def open_billing_session(
    user_id: int,
    business_type: str,
    estimated_cost: Decimal,
    db: AsyncSession,
    *,
    business_ref: dict | None = None,
    idempotency_key: str | None = None,
) -> str:
    """手动开启 billing session 并设置 contextvar。
    SSE 流式场景使用：在流开始前调用，流结束后手动 close。
    idempotency_key: 防止前端 retry 导致重复扣费。
    """
    from app.services.billing.service import start_billing_session
    session_id = await start_billing_session(
        user_id, business_type, estimated_cost, db,
        business_ref=business_ref,
        idempotency_key=idempotency_key,
    )
    current_billing_session_id.set(session_id)
    return session_id


async def close_billing_session(
    session_id: str,
    db: AsyncSession,
    *,
    success: bool = True,
    reason: str = "client_disconnect",
    override_cost: Decimal | None = None,
) -> Decimal:
    """手动关闭 billing session。SSE 场景在 finally 中调用。
    override_cost: 非 LLM 流程（翻译/导出）直接指定结算费用。
    """
    try:
        if success:
            from app.services.billing.service import settle_billing_session
            return await settle_billing_session(session_id, db, override_cost=override_cost)
        else:
            from app.services.billing.service import abort_billing_session
            return await abort_billing_session(session_id, db, reason=reason)
    finally:
        current_billing_session_id.set(None)

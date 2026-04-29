"""
SSE 流式会话管理 — 9.2 ~ 9.7 完整状态机
start → heartbeat(每200 token) → complete / abort
Redis 做热数据缓存，streaming_sessions 表做最终 source of truth。
"""
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import is_saas

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_TOKENS = 200
_REDIS_KEY_TTL = 600  # 10 min
_STALE_THRESHOLD_MINUTES = 5
_MAX_CONCURRENT_STREAMS = 3


class TooManyConcurrentStreamsError(Exception):
    pass


async def start_streaming_session(
    user_id: int,
    task_type: str,
    estimated_cost: Decimal,
    db: AsyncSession,
    *,
    article_id: int | None = None,
    section_id: int | None = None,
) -> str:
    """流开始前：预扣积分 + 创建会话 + 并发数检查"""
    if not is_saas():
        return str(uuid.uuid4())

    from app.core.redis import redis_sse

    # 并发流限制
    user_streams_key = f"user_streams:{user_id}"
    try:
        count = await redis_sse.scard(user_streams_key)
        if count >= _MAX_CONCURRENT_STREAMS:
            raise TooManyConcurrentStreamsError(
                f"同时进行的生成任务不能超过 {_MAX_CONCURRENT_STREAMS} 个，请等待当前任务完成后重试"
            )
    except TooManyConcurrentStreamsError:
        raise
    except Exception as exc:
        logger.debug("Redis 并发数检查失败（忽略）: %s", exc)

    # 预扣积分
    from app.services.credit.service import check_balance, freeze_credits
    await check_balance(user_id, estimated_cost, db)
    await freeze_credits(user_id, estimated_cost, db)

    # 创建 DB 会话记录
    from app.models.billing import StreamingSession
    session_id = str(uuid.uuid4())
    session = StreamingSession(
        session_id=session_id,
        user_id=user_id,
        article_id=article_id,
        section_id=section_id,
        task_type=task_type,
        estimated_cost=estimated_cost,
        status="streaming",
    )
    db.add(session)
    await db.flush()

    # 注册到 Redis 并发集合
    try:
        await redis_sse.sadd(user_streams_key, session_id)
        await redis_sse.expire(user_streams_key, _REDIS_KEY_TTL)
        await redis_sse.hset(f"stream:{session_id}", mapping={
            "user_id": str(user_id),
            "tokens_in": "0",
            "tokens_out": "0",
            "last_beat": str(time.time()),
        })
        await redis_sse.expire(f"stream:{session_id}", _REDIS_KEY_TTL)
    except Exception as exc:
        logger.debug("Redis 会话注册失败（忽略）: %s", exc)

    return session_id


async def update_streaming_progress(
    session_id: str,
    tokens_in: int,
    tokens_out: int,
) -> None:
    """每 200 token 调用一次，写入 Redis 心跳"""
    if not is_saas():
        return
    try:
        from app.core.redis import redis_sse
        await redis_sse.hset(f"stream:{session_id}", mapping={
            "tokens_in": str(tokens_in),
            "tokens_out": str(tokens_out),
            "last_beat": str(time.time()),
        })
        await redis_sse.expire(f"stream:{session_id}", _REDIS_KEY_TTL)
    except Exception as exc:
        logger.debug("Redis 心跳写入失败（不阻塞流）: %s", exc)


async def complete_streaming_session(
    session_id: str,
    final_tokens_in: int,
    final_tokens_out: int,
    db: AsyncSession,
    *,
    actual_word_count: int | None = None,
    model_tier: str | None = None,
    include_embedding: bool = False,
) -> Decimal:
    """流正常完成：按实际产出字数 + 实际模型档位扣费，否则按预估全额扣费。"""
    if not is_saas():
        return Decimal("0")

    from app.models.billing import StreamingSession
    from app.models.user import User
    from app.services.credit.service import unfreeze_credits, deduct_credits

    session = await db.get(StreamingSession, session_id, with_for_update=True)
    if not session or session.status != "streaming":
        return Decimal("0")

    if actual_word_count is not None and actual_word_count > 0:
        from app.services.credit.pricing import calc_generation_cost
        tier = model_tier or "standard"
        actual_cost = calc_generation_cost(actual_word_count, model_tier=tier, include_embedding=include_embedding)
        actual_cost = min(actual_cost, session.estimated_cost)
    else:
        actual_cost = session.estimated_cost

    await unfreeze_credits(session.user_id, session.estimated_cost, db)
    await deduct_credits(
        session.user_id, actual_cost, db,
        operation=session.task_type,
        article_id=session.article_id,
        section_id=session.section_id,
        meta={"session_id": session_id},
    )

    session.status = "completed"
    session.actual_cost = actual_cost
    session.actual_tokens_in = final_tokens_in
    session.actual_tokens_out = final_tokens_out
    session.completed_at = datetime.now(timezone.utc)
    await db.flush()

    await _cleanup_redis(session_id, session.user_id)
    return actual_cost


async def abort_streaming_session(
    session_id: str,
    db: AsyncSession,
    *,
    reason: str = "client_disconnect",
) -> Decimal:
    """流中断：按 Redis 累计 token 比例扣费"""
    if not is_saas():
        return Decimal("0")

    from app.models.billing import StreamingSession
    from app.services.credit.service import unfreeze_credits, deduct_credits
    from app.services.credit.pricing import calc_cost_from_token_ratio

    session = await db.get(StreamingSession, session_id, with_for_update=True)
    if not session or session.status != "streaming":
        return Decimal("0")

    # 从 Redis 获取进度
    actual_tokens_in = 0
    actual_tokens_out = 0
    try:
        from app.core.redis import redis_sse
        progress = await redis_sse.hgetall(f"stream:{session_id}")
        actual_tokens_in = int(progress.get("tokens_in", 0))
        actual_tokens_out = int(progress.get("tokens_out", 0))
    except Exception as exc:
        logger.debug("Redis 进度读取失败: %s", exc)

    actual_cost = Decimal("0")
    total_tokens = actual_tokens_in + actual_tokens_out
    if total_tokens > 0:
        estimated_total = max(
            int(session.estimated_cost * 1000),
            total_tokens,
        )
        actual_cost = calc_cost_from_token_ratio(
            session.estimated_cost, total_tokens, estimated_total,
        )

    await unfreeze_credits(session.user_id, session.estimated_cost, db)
    if actual_cost > 0:
        await deduct_credits(
            session.user_id, actual_cost, db,
            operation=session.task_type,
            article_id=session.article_id,
            section_id=session.section_id,
            meta={"session_id": session_id, "aborted": True, "reason": reason},
            aborted=True,
        )

    session.status = "aborted"
    session.actual_cost = actual_cost
    session.actual_tokens_in = actual_tokens_in
    session.actual_tokens_out = actual_tokens_out
    session.completed_at = datetime.now(timezone.utc)
    await db.flush()

    await _cleanup_redis(session_id, session.user_id)
    logger.info(
        "SSE 会话中断: session=%s reason=%s tokens=%d cost=%s",
        session_id, reason, total_tokens, actual_cost,
    )
    return actual_cost


async def cleanup_stale_sessions(db: AsyncSession) -> int:
    """扫描超时心跳孤儿会话，按已记录 token 扣费"""
    if not is_saas():
        return 0

    from app.models.billing import StreamingSession
    threshold = datetime.now(timezone.utc) - timedelta(minutes=_STALE_THRESHOLD_MINUTES)
    result = await db.execute(
        select(StreamingSession)
        .where(
            StreamingSession.status == "streaming",
            StreamingSession.last_heartbeat_at < threshold,
        )
    )
    stale_sessions = result.scalars().all()
    count = 0
    for session in stale_sessions:
        try:
            await abort_streaming_session(
                session.session_id, db, reason="server_timeout",
            )
            count += 1
        except Exception as exc:
            logger.error("清理孤儿会话 %s 失败: %s", session.session_id, exc)
    if count > 0:
        await db.commit()
        logger.info("清理了 %d 个超时 SSE 会话", count)
    return count


async def _cleanup_redis(session_id: str, user_id: int) -> None:
    """清理 Redis 中的会话数据"""
    try:
        from app.core.redis import redis_sse
        await redis_sse.delete(f"stream:{session_id}")
        await redis_sse.srem(f"user_streams:{user_id}", session_id)
    except Exception:
        pass


class StreamingTokenCounter:
    """在 SSE 生成器中追踪 token 数并定期写入心跳"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.tokens_in = 0
        self.tokens_out = 0
        self._last_heartbeat_tokens = 0

    async def add_output_tokens(self, text: str) -> None:
        self.tokens_out += max(len(text) // 4, 1)
        if self.tokens_out - self._last_heartbeat_tokens >= _HEARTBEAT_INTERVAL_TOKENS:
            self._last_heartbeat_tokens = self.tokens_out
            await update_streaming_progress(
                self.session_id, self.tokens_in, self.tokens_out,
            )

    def set_input_tokens(self, count: int) -> None:
        self.tokens_in = count

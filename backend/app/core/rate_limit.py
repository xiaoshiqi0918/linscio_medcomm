"""
API 限流 + 分布式操作锁 — Redis 计数器
桌面模式使用内存 stub，功能等价但无跨进程隔离。
"""
import logging

from fastapi import HTTPException, Request

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

_redis = get_redis(4)


# ═══════════════════════════════════════════════════════════════════
# 分布式操作锁 — 防止同一用户同操作并发提交
# ═══════════════════════════════════════════════════════════════════

class OperationLockFailed(Exception):
    """未能获取操作锁"""
    pass


async def acquire_operation_lock(user_id: int, operation: str, ttl: int = 60) -> bool:
    """
    尝试获取用户级操作锁。
    返回 True 表示成功获取；False 表示已有相同操作在进行中。
    锁自动在 ttl 秒后过期（兜底防死锁）。
    """
    from app.core.redis import get_redis as _get_lock_redis
    lock_redis = _get_lock_redis(1)
    key = f"op_lock:{user_id}:{operation}"
    result = await lock_redis.set(key, "1", ex=ttl, nx=True)
    return result is not None and result is not False


async def release_operation_lock(user_id: int, operation: str) -> None:
    """释放操作锁"""
    from app.core.redis import get_redis as _get_lock_redis
    lock_redis = _get_lock_redis(1)
    key = f"op_lock:{user_id}:{operation}"
    await lock_redis.delete(key)


async def require_operation_lock(user_id: int, operation: str, ttl: int = 60) -> None:
    """获取操作锁，失败则抛 429"""
    acquired = await acquire_operation_lock(user_id, operation, ttl)
    if not acquired:
        raise HTTPException(
            status_code=429,
            detail=f"操作进行中，请勿重复提交（{operation}）",
        )


async def _check_rate(key: str, limit: int, window: int) -> tuple[bool, int]:
    current = await _redis.incr(key)
    if current == 1:
        await _redis.expire(key, window)
    return current <= limit, current


async def check_login_rate(phone: str) -> None:
    key = f"rl:login:{phone}"
    allowed, count = await _check_rate(key, limit=5, window=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="登录请求过于频繁，请 1 分钟后再试")


async def check_register_rate(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"rl:register:{ip}"
    allowed, count = await _check_rate(key, limit=3, window=3600)
    if not allowed:
        raise HTTPException(status_code=429, detail="注册请求过于频繁，请稍后再试")


async def check_generate_rate(user_id: int) -> None:
    key = f"rl:generate:{user_id}"
    allowed, count = await _check_rate(key, limit=10, window=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="生成请求过于频繁，请 1 分钟后再试")


async def check_recharge_rate(user_id: int) -> None:
    key = f"rl:recharge:{user_id}"
    allowed, count = await _check_rate(key, limit=5, window=3600)
    if not allowed:
        raise HTTPException(status_code=429, detail="充值请求过于频繁，请稍后再试")

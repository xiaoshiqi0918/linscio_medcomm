"""
Redis 连接管理
桌面模式下提供内存 stub，不依赖 Redis。
"""
import logging
from app.core.config import settings, is_desktop

logger = logging.getLogger(__name__)


class _MemoryStub:
    """桌面端 Redis 替代 — 单进程内存字典，接口兼容"""
    def __init__(self):
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, *, ex: int | None = None, **kw):
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)

    async def incr(self, key: str):
        val = int(self._store.get(key, "0")) + 1
        self._store[key] = str(val)
        return val

    async def hset(self, name: str, mapping: dict | None = None, **kw):
        current = self._store.get(name)
        if not isinstance(current, dict):
            current = {}
        if mapping:
            current.update({str(k): str(v) for k, v in mapping.items()})
        current.update({str(k): str(v) for k, v in kw.items()})
        self._store[name] = current  # type: ignore[assignment]

    async def hgetall(self, name: str) -> dict:
        val = self._store.get(name)
        return val if isinstance(val, dict) else {}

    async def expire(self, key: str, seconds: int):
        pass

    async def scard(self, key: str) -> int:
        val = self._store.get(key)
        return len(val) if isinstance(val, set) else 0

    async def sadd(self, key: str, *values):
        current = self._store.get(key)
        if not isinstance(current, set):
            current = set()
        current.update(str(v) for v in values)
        self._store[key] = current  # type: ignore[assignment]

    async def srem(self, key: str, *values):
        current = self._store.get(key)
        if isinstance(current, set):
            for v in values:
                current.discard(str(v))

    async def close(self):
        self._store.clear()


if is_desktop():
    _pool_cache: dict[int, _MemoryStub] = {}

    def get_redis(db: int = 0) -> _MemoryStub:
        if db not in _pool_cache:
            _pool_cache[db] = _MemoryStub()
        return _pool_cache[db]

    redis_lock = get_redis(1)
    redis_sse = get_redis(2)
    redis_jwt = get_redis(3)

    async def close_all_redis():
        for r in _pool_cache.values():
            await r.close()
        _pool_cache.clear()

else:
    import redis.asyncio as aioredis
    from urllib.parse import urlparse

    _parsed = urlparse(settings.redis_url)
    _password_part = f":{_parsed.password}@" if _parsed.password else "@"
    _base_url = f"{_parsed.scheme}://{_password_part}{_parsed.hostname}:{_parsed.port or 6379}"

    _pool_cache_real: dict[int, aioredis.Redis] = {}

    def get_redis(db: int = 0) -> aioredis.Redis:  # type: ignore[return]
        if db not in _pool_cache_real:
            _pool_cache_real[db] = aioredis.from_url(
                f"{_base_url}/{db}",
                decode_responses=True,
                max_connections=20,
            )
        return _pool_cache_real[db]

    redis_lock = get_redis(settings.redis_lock_db)
    redis_sse = get_redis(settings.redis_sse_db)
    redis_jwt = get_redis(settings.redis_jwt_blacklist_db)

    async def close_all_redis():
        for r in _pool_cache_real.values():
            await r.close()
        _pool_cache_real.clear()

"""从 DB 加载用户 LLM provider 偏好（带进程级缓存）。"""
from __future__ import annotations

import json
import time
from typing import Optional

_cache: dict[int, tuple[float, dict[str, str] | None]] = {}
_CACHE_TTL = 300  # 5 min


async def load_user_provider_prefs(user_id: int) -> Optional[dict[str, str]]:
    now = time.monotonic()
    cached = _cache.get(user_id)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    prefs = await _load_from_db(user_id)
    _cache[user_id] = (now, prefs)
    return prefs


def invalidate_cache(user_id: int) -> None:
    _cache.pop(user_id, None)


async def _load_from_db(user_id: int) -> dict[str, str] | None:
    from app.core.database import AsyncSessionLocal
    from app.services.user_settings import UserSettingService

    try:
        async with AsyncSessionLocal() as db:
            raw = await UserSettingService.get(db, user_id, "model_preferences", "")
            if not raw:
                return None
            return json.loads(raw)
    except Exception:
        return None

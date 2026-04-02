"""
到期凭证从 htpasswd 中清理的定时任务（8.3 ③）。
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import RegistryCredential
from app.services.registry_service import remove_from_htpasswd, trigger_registry_reload


async def cleanup_expired_htpasswd_entries() -> int:
    """
    查询所有已过期的 registry_credentials，从 htpasswd 中删除对应用户，并触发 Registry 重载。
    返回本次删除的用户数。
    """
    now = datetime.now(timezone.utc)
    removed = 0
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(RegistryCredential.registry_username).where(
                RegistryCredential.expires_at.isnot(None),
                RegistryCredential.expires_at < now,
            )
        )
        usernames = [row[0] for row in r.all()]
    for username in usernames:
        if remove_from_htpasswd(username):
            removed += 1
    if removed > 0:
        trigger_registry_reload()
    return removed


async def htpasswd_cleanup_loop() -> None:
    """后台循环：按配置间隔执行到期清理。"""
    interval = getattr(settings, "HTPASSWD_CLEANUP_INTERVAL_SECONDS", 3600) or 0
    if interval <= 0:
        return
    while True:
        await asyncio.sleep(interval)
        try:
            await cleanup_expired_htpasswd_entries()
        except Exception:
            pass

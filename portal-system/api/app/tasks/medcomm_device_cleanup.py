"""
MedComm 换机码定时清理：每天删除 created_at 超过 1 天的记录（设计 2.1）
"""
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models.medcomm_models import MedcommDeviceChangeCode


async def cleanup_medcomm_device_change_codes() -> int:
    """
    删除 created_at < NOW() - 1天 的换机码记录。
    返回本次删除的行数。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            delete(MedcommDeviceChangeCode).where(
                MedcommDeviceChangeCode.created_at < cutoff
            )
        )
        await db.commit()
        return r.rowcount or 0


async def medcomm_device_cleanup_loop() -> None:
    """后台循环：每 24 小时执行一次换机码表清理。"""
    interval = 86400  # 24 小时
    while True:
        await asyncio.sleep(interval)
        try:
            await cleanup_medcomm_device_change_codes()
        except Exception:
            pass

"""
MedComm v3 速率限制（基于 medcomm_security_limits）
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.medcomm_models import MedcommSecurityLimit


async def check_locked(
    db: AsyncSession,
    limit_type: str,
    identifier: str,
) -> datetime | None:
    """若被锁定返回 locked_until，否则 None"""
    r = await db.execute(
        select(MedcommSecurityLimit).where(
            MedcommSecurityLimit.limit_type == limit_type,
            MedcommSecurityLimit.identifier == identifier,
        )
    )
    row = r.scalar_one_or_none()
    if not row or not row.locked_until:
        return None
    now = datetime.now(timezone.utc)
    lu = row.locked_until
    if getattr(lu, "tzinfo", None) is None:
        lu = lu.replace(tzinfo=timezone.utc)
    if lu > now:
        return lu
    return None


async def record_failure(
    db: AsyncSession,
    limit_type: str,
    identifier: str,
    max_failures: int,
    lockout_minutes: int,
) -> None:
    """记录失败，超过阈值则锁定"""
    now = datetime.now(timezone.utc)
    r = await db.execute(
        select(MedcommSecurityLimit).where(
            MedcommSecurityLimit.limit_type == limit_type,
            MedcommSecurityLimit.identifier == identifier,
        )
    )
    row = r.scalar_one_or_none()
    if not row:
        locked_until = None
        if max_failures <= 1 and lockout_minutes != 0:
            locked_until = (
                now + timedelta(minutes=lockout_minutes)
                if lockout_minutes > 0
                else now.replace(year=2099, month=12, day=31, hour=23, minute=59, second=59)
            )
        row = MedcommSecurityLimit(
            limit_type=limit_type,
            identifier=identifier,
            fail_count=1,
            last_fail_at=now,
            updated_at=now,
            locked_until=locked_until,
        )
        db.add(row)
    else:
        row.fail_count = (row.fail_count or 0) + 1
        row.last_fail_at = now
        row.updated_at = now
        if row.fail_count >= max_failures:
            if lockout_minutes > 0:
                row.locked_until = now + timedelta(minutes=lockout_minutes)
            elif lockout_minutes == -1:
                # 永久锁，需管理员解锁（使用 2099 表示）
                row.locked_until = now.replace(year=2099, month=12, day=31, hour=23, minute=59, second=59)
    await db.flush()


PERMANENT_LOCK_YEAR = 2099


async def record_cooldown(
    db: AsyncSession,
    limit_type: str,
    identifier: str,
    cooldown_minutes: int = 1,
) -> None:
    """记录操作并设置冷却期（如验证码发送 1 分钟内不可重复）"""
    now = datetime.now(timezone.utc)
    r = await db.execute(
        select(MedcommSecurityLimit).where(
            MedcommSecurityLimit.limit_type == limit_type,
            MedcommSecurityLimit.identifier == identifier,
        )
    )
    row = r.scalar_one_or_none()
    if not row:
        row = MedcommSecurityLimit(
            limit_type=limit_type,
            identifier=identifier,
            fail_count=0,
            last_fail_at=now,
            updated_at=now,
            locked_until=now + timedelta(minutes=cooldown_minutes),
        )
        db.add(row)
    else:
        row.locked_until = now + timedelta(minutes=cooldown_minutes)
        row.updated_at = now
    await db.flush()


async def reset_failures(
    db: AsyncSession,
    limit_type: str,
    identifier: str,
) -> None:
    r = await db.execute(
        select(MedcommSecurityLimit).where(
            MedcommSecurityLimit.limit_type == limit_type,
            MedcommSecurityLimit.identifier == identifier,
        )
    )
    row = r.scalar_one_or_none()
    if row:
        row.fail_count = 0
        row.locked_until = None
        row.updated_at = datetime.now(timezone.utc)

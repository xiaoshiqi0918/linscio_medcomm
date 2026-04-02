"""
生成次数管控（7.x）：每台机器每 90 天周期按内容类型计数。
周期从授权码激活日起算，每 90 天为一周期；基础版/专业版/团队版有上限，旗舰版/内测版不限。
"""
from datetime import date, timedelta, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LicenseKey, Plan, GenerationQuota, GenerationRecord

CYCLE_DAYS = 90
CONTENT_TYPES = ("schola", "medcomm", "qcc")

# 各套餐每台机器每 90 天上限： (schola, medcomm, qcc)，0 表示不限
QUOTA_LIMITS_BY_PLAN = {
    "basic": (1, 2, 1),
    "professional": (1, 2, 1),
    "team": (1, 2, 1),
    "enterprise": (0, 0, 0),
    "beta": (0, 0, 0),
}


def get_quota_limit(plan_code: str, content_type: str) -> int:
    """返回该套餐下某内容类型的每机每周期上限，0 表示不限。"""
    if content_type not in CONTENT_TYPES:
        return 0
    limits = QUOTA_LIMITS_BY_PLAN.get(plan_code, (0, 0, 0))
    idx = CONTENT_TYPES.index(content_type)
    return limits[idx]


def get_cycle_bounds(activated_at: datetime | None) -> tuple[date, date] | None:
    """
    根据授权码激活日计算当前所处 90 天周期的起止日期（均为 date）。
    激活日为首日，第 1 周期为 [激活日, 激活日+89天]，第 2 周期为 [激活日+90天, 激活日+179天] ...
    若未激活则返回 None。
    """
    if not activated_at:
        return None
    start = activated_at.date() if hasattr(activated_at, "date") else activated_at
    if isinstance(start, datetime):
        start = start.date()
    today = date.today()
    if today < start:
        return None
    elapsed = (today - start).days
    cycle_index = elapsed // CYCLE_DAYS
    cycle_start = start + timedelta(days=cycle_index * CYCLE_DAYS)
    cycle_end = cycle_start + timedelta(days=CYCLE_DAYS - 1)
    return cycle_start, cycle_end


def get_next_cycle_start(activated_at: datetime | None) -> date | None:
    """当前周期结束日的次日（下一周期开始日）。"""
    bounds = get_cycle_bounds(activated_at)
    if not bounds:
        return None
    _, cycle_end = bounds
    return cycle_end + timedelta(days=1)


async def get_or_create_quota_row(
    db: AsyncSession,
    license_id: str,
    machine_id: str,
    content_type: str,
    cycle_start: date,
    cycle_end: date,
    quota_limit: int,
) -> GenerationQuota:
    """获取或创建本周期本机本类型的 generation_quotas 行。"""
    r = await db.execute(
        select(GenerationQuota).where(
            GenerationQuota.license_id == license_id,
            GenerationQuota.machine_id == machine_id,
            GenerationQuota.content_type == content_type,
            GenerationQuota.cycle_start == cycle_start,
        )
    )
    row = r.scalar_one_or_none()
    if row:
        return row
    row = GenerationQuota(
        license_id=license_id,
        machine_id=machine_id,
        content_type=content_type,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        used_count=0,
        quota_limit=quota_limit,
    )
    db.add(row)
    await db.flush()
    return row


async def check_and_use_quota(
    db: AsyncSession,
    license_key: LicenseKey,
    machine_id: str,
    content_type: str,
    user_id: str | None = None,
    project_id: str | None = None,
) -> tuple[bool, str | None, date | None, int, int]:
    """
    校验并在未超限时扣减一次生成次数。
    返回: (allowed, error_message, cycle_reset_date, used, limit)
    - allowed=True 时 error_message 为 None，已写入 generation_records 并 +1 used_count。
    - allowed=False 时返回提示文案与下一周期开始日（用于前端展示剩余天数）。
    """
    if content_type not in CONTENT_TYPES:
        return False, "不支持的内容类型", None, 0, 0

    plan_code = license_key.plan_type
    if license_key.plan_id:
        p = await db.get(Plan, license_key.plan_id)
        if p:
            plan_code = p.code
    limit = get_quota_limit(plan_code or "basic", content_type)

    activated_at = license_key.activated_at
    bounds = get_cycle_bounds(activated_at)
    if not bounds:
        return False, "授权未激活或激活日异常", None, 0, limit
    cycle_start, cycle_end = bounds

    # 不限则直接通过，不写 generation_quotas
    if limit == 0:
        rec = GenerationRecord(
            license_id=license_key.id,
            machine_id=machine_id,
            user_id=user_id,
            content_type=content_type,
            project_id=project_id,
            cycle_start=cycle_start,
        )
        db.add(rec)
        await db.flush()
        next_start = cycle_end + timedelta(days=1)
        return True, None, next_start, 0, 0

    quota_row = await get_or_create_quota_row(
        db, str(license_key.id), machine_id, content_type, cycle_start, cycle_end, limit
    )
    used = quota_row.used_count
    if used >= limit:
        next_start = cycle_end + timedelta(days=1)
        return False, f"本周期{content_type}生成次数已用完（{used}/{limit}）", next_start, used, limit

    quota_row.used_count = used + 1
    rec = GenerationRecord(
        license_id=license_key.id,
        machine_id=machine_id,
        user_id=user_id,
        content_type=content_type,
        project_id=project_id,
        cycle_start=cycle_start,
    )
    db.add(rec)
    await db.flush()
    next_start = cycle_end + timedelta(days=1)
    return True, None, next_start, used + 1, limit


async def reset_quota_for_license(
    db: AsyncSession,
    license_id: str,
    machine_id: str | None = None,
) -> int:
    """
    将指定授权码（及可选机器）在当前 90 天周期内的 generation_quotas.used_count 置为 0。
    返回被重置的行数。
    """
    from sqlalchemy import update
    r = await db.execute(select(LicenseKey).where(LicenseKey.id == license_id))
    key = r.scalar_one_or_none()
    if not key:
        return 0
    bounds = get_cycle_bounds(key.activated_at)
    if not bounds:
        return 0
    cycle_start, _ = bounds
    stmt = (
        update(GenerationQuota)
        .where(
            GenerationQuota.license_id == license_id,
            GenerationQuota.cycle_start == cycle_start,
        )
    )
    if machine_id:
        stmt = stmt.where(GenerationQuota.machine_id == machine_id)
    result = await db.execute(stmt.values(used_count=0))
    await db.flush()
    return result.rowcount

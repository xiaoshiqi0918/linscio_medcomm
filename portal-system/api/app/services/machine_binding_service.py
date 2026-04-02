"""机器绑定与解绑：自助解绑规则、管理员解绑时的更换次数限制（8.2）。"""
from datetime import date, timedelta, datetime

REPLACE_PERIOD_DAYS = 365

# 各套餐每周期可更换机器次数（仅管理员解绑时校验），None 表示不限
REPLACE_LIMIT_BY_PLAN = {
    "basic": 1,
    "professional": 2,
    "team": None,
    "enterprise": None,
    "beta": None,
}


def get_replace_period_start(activated_at: datetime | None) -> date | None:
    """从授权激活日起，每 365 天为一周期，返回当前周期起始日。"""
    if not activated_at:
        return None
    start = activated_at.date() if hasattr(activated_at, "date") else activated_at
    if isinstance(start, datetime):
        start = start.date()
    today = date.today()
    if today < start:
        return None
    elapsed = (today - start).days
    period_index = elapsed // REPLACE_PERIOD_DAYS
    return start + timedelta(days=period_index * REPLACE_PERIOD_DAYS)


def get_replace_limit(plan_code: str) -> int | None:
    """该套餐每周期可解绑次数，None 表示不限。"""
    return REPLACE_LIMIT_BY_PLAN.get(plan_code)


def can_replace_machine(
    plan_code: str,
    replace_period_start: date | None,
    replace_count_used: int,
    current_period_start: date | None,
) -> tuple[bool, str | None]:
    """
    管理员解绑时：当前周期是否还可更换机器。
    返回 (allowed, error_message)。
    """
    limit = get_replace_limit(plan_code)
    if limit is None:
        return True, None
    if current_period_start is None:
        return False, "无法计算更换周期（授权未激活）"
    if replace_period_start is None or replace_period_start < current_period_start:
        return True, None
    if replace_count_used >= limit:
        return False, f"本周期更换次数已用完（{replace_count_used}/{limit}），下一周期可再更换"
    return True, None

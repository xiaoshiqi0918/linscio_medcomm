# 全栈方案 §5.2：根据 maintenance_until 实时计算账号状态
from datetime import datetime, timezone, timedelta
from app.models import PortalUser

GRACE_PERIOD_DAYS = 30


def compute_account_status(user: PortalUser) -> str:
    """
    根据 maintenance_until 实时计算账号状态。
    不依赖数据库中存储的 account_status，避免定时任务漏跑导致状态不一致。
    颁发令牌时调用此函数，不直接读 user.account_status。
    cancelled 状态须在调用前先检查 user.account_status。
    """
    if getattr(user, "account_status", None) == "cancelled":
        return "cancelled"
    if user.plan is None or user.maintenance_until is None:
        return "registered"

    now = datetime.now(timezone.utc)
    maintenance_until = user.maintenance_until
    if maintenance_until.tzinfo is None:
        maintenance_until = maintenance_until.replace(tzinfo=timezone.utc)
    grace_until = maintenance_until + timedelta(days=GRACE_PERIOD_DAYS)

    if now <= maintenance_until:
        return "active"
    if now <= grace_until:
        return "grace"
    return "suspended"

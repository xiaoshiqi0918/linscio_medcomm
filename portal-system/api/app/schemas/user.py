from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class UserProfile(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class ActivateLicenseRequest(BaseModel):
    code: str


class LicenseInfo(BaseModel):
    is_activated: bool
    plan_type: Optional[str] = None
    plan_name: Optional[str] = None
    period_name: Optional[str] = None
    machine_limit: Optional[int] = None
    concurrent_limit: Optional[int] = None
    pull_limit_monthly: Optional[int] = None
    allowed_image_tags: Optional[List[str]] = None
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None

    class Config:
        from_attributes = True


class RegistryCredentialResponse(BaseModel):
    registry_url: str
    username: str
    password: str
    allowed_image_tags: Optional[List[str]] = None


class MachineBindingItem(BaseModel):
    id: str
    machine_id: str
    machine_name: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    is_active: bool
    is_online: bool = False
    machine_id_display: str = ""

    class Config:
        from_attributes = True


class MachineListResponse(BaseModel):
    bindings: List[MachineBindingItem] = []
    machine_limit: int = 1
    binding_count: int = 0
    slots_remaining: Optional[int] = None
    plan_name: Optional[str] = None
    can_self_unbind: bool = False
    unbind_hint: Optional[str] = None


class QuotaTypeItem(BaseModel):
    content_type: str
    used: int
    limit: int
    exhausted: bool


class QuotaMachineItem(BaseModel):
    machine_id: str
    machine_id_display: str
    machine_name: Optional[str] = None
    types: List[QuotaTypeItem] = []


class QuotaSummaryResponse(BaseModel):
    cycle_start: Optional[str] = None
    cycle_end: Optional[str] = None
    next_reset_date: Optional[str] = None
    machines: List[QuotaMachineItem] = []


class PullQuotaResponse(BaseModel):
    """门户「本月拉取次数」：已用、上限、重置日（自然月）。"""
    used: int = 0
    limit: Optional[int] = None  # None 表示不限
    reset_at: Optional[str] = None  # 下月 1 日 YYYY-MM-DD

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class UserListItem(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    plan: Optional[str] = None
    maintenance_until: Optional[datetime] = None
    machine_limit: Optional[int] = None
    account_status: Optional[str] = None

    class Config:
        from_attributes = True


class LicenseListItem(BaseModel):
    id: str
    code: str
    plan_type: str
    expires_at: datetime
    created_at: datetime
    created_by: str
    assigned_to: Optional[str] = None
    is_used: bool
    is_revoked: bool = False
    activated_at: Optional[datetime] = None
    plan_name: Optional[str] = None
    period_name: Optional[str] = None
    notes: Optional[str] = None
    machine_limit: Optional[int] = None
    concurrent_limit: Optional[int] = None
    pull_limit_monthly: Optional[int] = None
    assigned_username: Optional[str] = None
    status: Optional[str] = None  # 未使用/已激活/已过期/已作废
    machine_bound_count: Optional[int] = None
    instance_active_count: Optional[int] = None
    pull_used_this_month: Optional[int] = None

    class Config:
        from_attributes = True


class LicenseDetailItem(LicenseListItem):
    machine_bound_count: int = 0
    instance_active_count: int = 0
    pull_used_this_month: Optional[int] = None


class LicenseBatchCreate(BaseModel):
    count: int = Field(default=10, ge=1, le=100, description="生成数量，1-100")
    months_valid: int = 12
    plan_type: str = "standard"
    plan_code: Optional[str] = None
    period_code: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500, description="备注，最多500字")


class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    plan: Optional[str] = None
    maintenance_until: Optional[datetime] = None
    machine_limit: Optional[int] = None


class ModuleListItem(BaseModel):
    id: str
    code: str
    name: str
    bit_position: int
    is_controlled: bool
    basic_enabled: bool
    pro_enabled: bool
    team_enabled: bool
    enterprise_enabled: bool = True
    beta_enabled: bool = True
    sort_order: int

    class Config:
        from_attributes = True


class ModuleUpdateRequest(BaseModel):
    basic_enabled: Optional[bool] = None
    pro_enabled: Optional[bool] = None
    team_enabled: Optional[bool] = None
    enterprise_enabled: Optional[bool] = None
    beta_enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class ModuleCreateRequest(BaseModel):
    name: str
    code: str
    basic_enabled: bool = False
    pro_enabled: bool = True
    team_enabled: bool = True
    enterprise_enabled: bool = True
    beta_enabled: bool = True


class LicenseExtendRequest(BaseModel):
    months: int = 1


class PlanOption(BaseModel):
    code: str
    name: str

    class Config:
        from_attributes = True


class PlanOptionDetail(BaseModel):
    """套餐选项（含分级授权与镜像管控限制，供批量生成弹窗展示）。"""
    code: str
    name: str
    machine_limit: Optional[int] = None
    concurrent_limit: Optional[int] = None
    pull_limit_monthly: Optional[int] = None

    class Config:
        from_attributes = True


class PeriodOption(BaseModel):
    code: str
    name: str  # 月付/季付/年付/内测

    class Config:
        from_attributes = True


# 套餐与周期管理（列表含 id，供编辑）
class PlanManageItem(BaseModel):
    id: str
    code: str
    name: str
    plan_char: str
    machine_limit: int = 1
    concurrent_limit: int = 1
    pull_limit_monthly: Optional[int] = None
    price_monthly: float = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class PlanCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=60)
    plan_char: str = Field(..., min_length=1, max_length=1)
    machine_limit: int = Field(1, ge=0)
    concurrent_limit: int = Field(1, ge=0)
    pull_limit_monthly: Optional[int] = Field(None, ge=0)
    price_monthly: float = Field(0, ge=0)
    is_active: bool = True


class PlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    plan_char: Optional[str] = Field(None, min_length=1, max_length=1)
    machine_limit: Optional[int] = Field(None, ge=0)
    concurrent_limit: Optional[int] = Field(None, ge=0)
    pull_limit_monthly: Optional[int] = Field(None, ge=0)
    price_monthly: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class PeriodManageItem(BaseModel):
    id: str
    code: str
    name: Optional[str] = None
    period_char: str
    months: int
    discount_rate: float = 1

    class Config:
        from_attributes = True


class BillingPeriodCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: Optional[str] = Field(None, max_length=60)
    period_char: str = Field(..., min_length=1, max_length=1)
    months: int = Field(..., ge=1)
    discount_rate: float = Field(1, ge=0, le=1)


class BillingPeriodUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=60)
    period_char: Optional[str] = Field(None, min_length=1, max_length=1)
    months: Optional[int] = Field(None, ge=1)
    discount_rate: Optional[float] = Field(None, ge=0, le=1)


class RegistrationTrendItem(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class LicenseStatusCounts(BaseModel):
    used: int
    unused: int
    revoked: int


class PlanCountItem(BaseModel):
    plan_code: str
    plan_name: str
    count: int


class PullTopItem(BaseModel):
    username: str
    user_id: str
    pull_count: int


class QuotaResetRequest(BaseModel):
    """重置生成次数：指定授权码，可选指定机器（不传则重置该授权下所有机器当前周期）。"""
    license_id: str
    machine_id: Optional[str] = None


class StatsOverview(BaseModel):
    total_users: int
    activated_users: int
    total_licenses: int
    new_users_this_month: int
    new_activations_this_month: int = 0
    expiring_licenses: List[LicenseListItem] = []
    expiring_7_days: List[LicenseListItem] = []
    registration_trend: List[RegistrationTrendItem] = []
    license_status: LicenseStatusCounts = LicenseStatusCounts(used=0, unused=0, revoked=0)
    plan_breakdown: List[PlanCountItem] = []
    active_users_by_plan: List[PlanCountItem] = []
    machine_bindings_total: int = 0
    pull_top10_this_month: List[PullTopItem] = []
    alerts: List[str] = []

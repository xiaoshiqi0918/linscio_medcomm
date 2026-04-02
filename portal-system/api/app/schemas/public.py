"""公开接口 Schema（无需登录，如门户价格页、下载）"""
from decimal import Decimal
from pydantic import BaseModel


class PlanPricingItem(BaseModel):
    """单套餐在价格页的展示数据，对应 4.1～4.3 定价体系。"""
    plan_code: str
    plan_name: str
    price_monthly: float  # 月付（基准）
    price_quarterly: float  # 季付总价（月付×3×0.9）
    equivalent_monthly_quarterly: float  # 季付折合月价
    price_yearly: float  # 年付总价（月付×12×0.8）
    equivalent_monthly_yearly: float  # 年付折合月价
    savings_yearly: float  # 年付较月付节省金额（元）


class PricingResponse(BaseModel):
    """门户价格页 API 返回：仅含公开展示套餐（不含内测版）。"""
    plans: list[PlanPricingItem]


# ---------- 下载中心 ----------


class CurrentVersionResponse(BaseModel):
    """当前可下载版本信息（GET /public/download/current-version）"""
    version: str
    file_size: int | None = None
    release_notes: str | None = None


class PresignRequest(BaseModel):
    license_code: str


class PresignResponse(BaseModel):
    """预签名下载链接返回（POST /public/download/presign-url）"""
    download_url: str
    expires_in_seconds: int
    version: str
    file_size: int | None = None
    doc_url: str = "/docs"

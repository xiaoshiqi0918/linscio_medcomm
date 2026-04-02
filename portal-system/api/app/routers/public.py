"""公开接口（无需登录）：门户价格页等"""
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Plan
from app.schemas.public import PlanPricingItem, PricingResponse

router = APIRouter(tags=["public"])


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(db: AsyncSession = Depends(get_db)):
    """
    门户价格页数据。返回各套餐月付/季付/年付价格（内测版不展示）。
    季付 = 月付×3×9折，年付 = 月付×12×8折，与方案 4.1～4.4 一致。
    """
    result = await db.execute(
        select(Plan).where(Plan.code != "beta", Plan.is_active == True).order_by(Plan.price_monthly.asc())
    )
    plans = result.scalars().all()
    items = []
    for p in plans:
        pm = float(p.price_monthly)
        pq = round(pm * 3 * 0.9, 1)  # 季付
        py = round(pm * 12 * 0.8, 0)  # 年付
        items.append(PlanPricingItem(
            plan_code=p.code,
            plan_name=p.name,
            price_monthly=pm,
            price_quarterly=pq,
            equivalent_monthly_quarterly=round(pq / 3, 1),
            price_yearly=py,
            equivalent_monthly_yearly=round(py / 12, 1),
            savings_yearly=round(pm * 12 - py, 0),
        ))
    return PricingResponse(plans=items)

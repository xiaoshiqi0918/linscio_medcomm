"""生成次数校验接口（7.5）：应用内新建项目时调用，校验并扣减本周期本机该类型次数。"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import LicenseKey, Plan
from app.services.quota_service import (
    check_and_use_quota,
    get_cycle_bounds,
    get_quota_limit,
    CONTENT_TYPES,
)

router = APIRouter(prefix="/quota", tags=["quota"])


class QuotaCheckRequest(BaseModel):
    license_key: str
    machine_id: str
    content_type: str  # schola / medcomm / qcc
    project_id: str | None = None
    user_id: str | None = None


class QuotaCheckOkResponse(BaseModel):
    allowed: bool = True
    content_type: str
    used: int
    limit: int  # 0 表示不限
    cycle_start: str  # YYYY-MM-DD
    cycle_end: str
    next_reset_date: str


@router.post("/check")
async def quota_check(
    data: QuotaCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    新建项目前校验生成次数。未超限时立即扣减一次并返回 200；超限返回 403。
    """
    if data.content_type not in CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="content_type 须为 schola / medcomm / qcc 之一")

    code = data.license_key.strip().upper()
    r = await db.execute(
        select(LicenseKey).where(
            LicenseKey.code == code,
            LicenseKey.is_used == True,
            LicenseKey.is_revoked == False,
        )
    )
    license_key = r.scalar_one_or_none()
    if not license_key:
        raise HTTPException(status_code=404, detail="授权码无效或未激活")

    if license_key.expires_at and license_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="授权已过期，请续费")

    bounds = get_cycle_bounds(license_key.activated_at)
    if not bounds:
        raise HTTPException(status_code=400, detail="无法计算当前周期（授权未激活或激活日异常）")
    cycle_start, cycle_end = bounds
    next_reset = cycle_end + timedelta(days=1)

    allowed, err_msg, reset_date, used, lim = await check_and_use_quota(
        db,
        license_key,
        data.machine_id,
        data.content_type,
        user_id=data.user_id,
        project_id=data.project_id,
    )

    if allowed:
        await db.commit()
        return QuotaCheckOkResponse(
            content_type=data.content_type,
            used=used,
            limit=lim,
            cycle_start=cycle_start.isoformat(),
            cycle_end=cycle_end.isoformat(),
            next_reset_date=(reset_date or next_reset).isoformat(),
        )
    raise HTTPException(
        status_code=403,
        detail={
            "allowed": False,
            "message": err_msg or "本周期生成次数已用完",
            "used": used,
            "limit": lim,
            "next_reset_date": (reset_date or next_reset).isoformat(),
        },
    )


@router.get("/status")
async def quota_status(
    license_key: str,
    machine_id: str,
    db: AsyncSession = Depends(get_db),
):
    """仅查询本机本周期各类型已用/上限，不扣减。用于应用内展示进度条。"""
    code = license_key.strip().upper()
    r = await db.execute(
        select(LicenseKey).where(
            LicenseKey.code == code,
            LicenseKey.is_used == True,
            LicenseKey.is_revoked == False,
        )
    )
    license_key_obj = r.scalar_one_or_none()
    if not license_key_obj:
        raise HTTPException(status_code=404, detail="授权码无效或未激活")

    plan_code = license_key_obj.plan_type
    if license_key_obj.plan_id:
        p = await db.get(Plan, license_key_obj.plan_id)
        if p:
            plan_code = p.code
    bounds = get_cycle_bounds(license_key_obj.activated_at)
    if not bounds:
        return {"cycle_start": None, "cycle_end": None, "types": []}
    cycle_start, cycle_end = bounds
    next_reset = cycle_end + timedelta(days=1)

    from app.models import GenerationQuota
    out = []
    for ct in CONTENT_TYPES:
        lim = get_quota_limit(plan_code or "basic", ct)
        q = await db.execute(
            select(GenerationQuota).where(
                GenerationQuota.license_id == license_key_obj.id,
                GenerationQuota.machine_id == machine_id,
                GenerationQuota.content_type == ct,
                GenerationQuota.cycle_start == cycle_start,
            )
        )
        row = q.scalar_one_or_none()
        used = row.used_count if row else 0
        out.append({
            "content_type": ct,
            "used": used,
            "limit": lim,
            "exhausted": lim > 0 and used >= lim,
        })
    return {
        "cycle_start": cycle_start.isoformat(),
        "cycle_end": cycle_end.isoformat(),
        "next_reset_date": next_reset.isoformat(),
        "types": out,
    }

"""
桌面客户端专用 SaaS API（Bearer JWT = 与 Web 同一套账号）。
替代原 linscio.com.cn 门户的授权状态查询。
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/license-status")
async def client_license_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    返回与旧门户 `POST /api/license/status` 兼容的结构，供 Electron 主进程解析。
    使用权：账号未封禁且名下至少有一条已归属的客户端授权码（LicenseCode.owner_id）。
    学科包版本推送已下线，specialties 恒为空；请用户在客户端本地上传安装包。
    """
    from app.models.billing import LicenseCode

    if getattr(user, "is_banned", False):
        return {
            "base": {
                "valid": False,
                "expires_at": None,
                "days_remaining": None,
                "is_trial": False,
            },
            "specialties": [],
            "version_policies": [],
        }

    cnt = await db.scalar(
        select(func.count(LicenseCode.id)).where(LicenseCode.owner_id == user.id)
    )
    valid = (cnt or 0) > 0

    return {
        "base": {
            "valid": valid,
            "expires_at": None,
            "days_remaining": None,
            "is_trial": False,
        },
        "specialties": [],
        "version_policies": [],
    }

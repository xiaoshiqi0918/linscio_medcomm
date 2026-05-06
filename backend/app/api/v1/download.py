"""
客户端下载 API — SaaS 模式
流程：用户持有有效授权码(LicenseCode) → 验证 → 从 COS manifest 获取版本 → 返回预签名下载 URL
每次下载都记录 DownloadLog，支持版本追踪和下载统计。
"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

PLATFORM_EXT = {"win-x64": "exe", "mac-arm64": "dmg", "mac-x64": "dmg"}


def _parse_version_tuple(v: str) -> tuple[int, ...]:
    """用于版本比较的简化语义化版本（提取数字段）。"""
    import re

    s = (v or "0").strip()
    parts = re.findall(r"\d+", s)
    if not parts:
        return (0,)
    return tuple(int(x) for x in parts[:6])


def _version_compare(a: str, b: str) -> int:
    """-1 表示 a<b，0 相等，1 表示 a>b。"""
    ta, tb = _parse_version_tuple(a), _parse_version_tuple(b)
    maxlen = max(len(ta), len(tb))
    ta = ta + (0,) * (maxlen - len(ta))
    tb = tb + (0,) * (maxlen - len(tb))
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def _find_product(manifest: dict, product_id: str) -> tuple[dict | None, str]:
    canonical_id = product_id
    prod = None
    for p in manifest.get("products", []):
        if (p.get("id") or "").lower() == product_id.lower():
            prod = p
            canonical_id = p["id"]
            break
    return prod, canonical_id


# ── Electron：仅主程序更新检查（学科包改由客户端本地上传安装）──────────


class UpdateCheckRequest(BaseModel):
    """与 Electron `auth-checker.checkSoftwareUpdate` 请求体对齐。"""

    product_id: str = Field(default="medcomm")
    platform: str = Field(..., description="mac-arm64 / mac-x64 / win-x64")
    software_version: str = Field(default="0.0.0")


@router.post("/update-check")
async def client_update_check(
    req: UpdateCheckRequest,
    user: User = Depends(get_current_user),
):
    """
    桌面客户端检查主程序更新（Bearer JWT）。
    学科包不再有云端分发；响应中 specialty_updates / drawing_pack_updates 恒为空。
    """
    from app.core.config import settings
    from app.services.cos import read_manifest, generate_presigned_download_url

    manifest = read_manifest()
    prod, canonical_id = _find_product(manifest, req.product_id)
    min_cv = manifest.get("min_client_version") or None

    if not prod:
        return {
            "base_valid": True,
            "has_software_update": False,
            "latest_version": None,
            "min_client_version": min_cv,
            "specialty_updates": [],
            "drawing_pack_updates": [],
        }

    latest_ver = str(prod.get("latest_version") or "0.0.0")
    has_sw = _version_compare(latest_ver, req.software_version) > 0
    if has_sw:
        allowed = prod.get("platforms") or []
        if allowed and req.platform not in allowed:
            has_sw = False

    download_url = None
    update_filename = None
    if has_sw and settings.cos_secret_id:
        overrides = prod.get("download_files") or {}
        if req.platform in overrides:
            update_filename = overrides[req.platform]
        else:
            ext = PLATFORM_EXT.get(req.platform, "dmg")
            update_filename = f"LinScio-MedComm-{latest_ver}-{req.platform}.{ext}"
        cos_key = f"releases/{canonical_id}/v{latest_ver}/{update_filename}"
        try:
            download_url = generate_presigned_download_url(cos_key, expires=7200)
        except Exception:
            logger.exception("生成主程序预签名 URL 失败")
    elif has_sw and not settings.cos_secret_id:
        logger.warning("COS 未配置，无法返回安装包下载地址")

    return {
        "base_valid": True,
        "has_software_update": has_sw,
        "latest_version": latest_ver,
        "download_url": download_url,
        "update_download_url": download_url,
        "update_filename": update_filename,
        "update_size_bytes": 0,
        "update_sha256": None,
        "release_notes": prod.get("release_notes"),
        "platform_status": prod.get("platform_status"),
        "min_client_version": min_cv,
        "specialty_updates": [],
        "drawing_pack_updates": [],
        "changelog": prod.get("changelog"),
    }


# ── 公开接口：产品信息 ──────────────────────────────────────

@router.get("/product-info")
async def get_product_info():
    """公开接口：返回产品版本、平台列表（从 COS manifest 读取）"""
    from app.services.cos import read_manifest
    manifest = read_manifest()

    products = {}
    for prod in manifest.get("products", []):
        products[prod["id"]] = {
            "id": prod["id"],
            "name": prod.get("name", prod["id"]),
            "latest_version": prod.get("latest_version", "0.0.0"),
            "platforms": prod.get("platforms", []),
            "platform_status": prod.get("platform_status", {}),
            "download_files": prod.get("download_files", {}),
            "release_notes": prod.get("release_notes"),
            "system_requirements": prod.get("system_requirements", {}),
            "changelog": prod.get("changelog", []),
        }

    return {
        "products": products,
        "specialties": manifest.get("specialties", []),
        "drawing_packs": manifest.get("drawing_packs", []),
    }


# ── 需登录接口：下载软件 ────────────────────────────────────

class SoftwareDownloadRequest(BaseModel):
    product_id: str = Field(default="medcomm")
    platform: str = Field(..., description="mac-arm64 / mac-x64 / win-x64")


@router.post("/software")
async def download_software(
    req: SoftwareDownloadRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    下载客户端安装包。
    前置条件：用户持有至少一个有效授权码。
    每次下载写入 download_logs 追踪版本分布。
    """
    from app.models.billing import LicenseCode, DownloadLog
    result = await db.execute(
        select(LicenseCode).where(
            LicenseCode.owner_id == user.id,
        ).order_by(LicenseCode.created_at).limit(1)
    )
    license_code = result.scalar_one_or_none()
    if not license_code:
        raise HTTPException(status_code=403, detail="no_valid_license")

    from app.services.cos import read_manifest, generate_presigned_download_url
    manifest = read_manifest()

    prod = None
    canonical_id = req.product_id
    for p in manifest.get("products", []):
        if (p.get("id") or "").lower() == req.product_id.lower():
            prod = p
            canonical_id = p["id"]
            break

    latest_ver = (prod or {}).get("latest_version", "1.0.0")

    allowed = (prod or {}).get("platforms", [])
    if allowed and req.platform not in allowed:
        raise HTTPException(status_code=400, detail="platform_unavailable")

    overrides = (prod or {}).get("download_files", {})
    if req.platform in overrides:
        filename = overrides[req.platform]
    else:
        ext = PLATFORM_EXT.get(req.platform, "dmg")
        filename = f"LinScio-MedComm-{latest_ver}-{req.platform}.{ext}"

    cos_key = f"releases/{canonical_id}/v{latest_ver}/{filename}"

    from app.core.config import settings
    if not settings.cos_secret_id:
        raise HTTPException(status_code=503, detail="下载服务暂不可用，COS 未配置")

    download_url = generate_presigned_download_url(cos_key, expires=7200)

    client_ip = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:300]
    dl_log = DownloadLog(
        user_id=user.id,
        product_id=canonical_id,
        version=latest_ver,
        platform=req.platform,
        filename=filename,
        license_code_id=license_code.id,
        client_ip=client_ip,
        user_agent=ua,
    )
    db.add(dl_log)
    await db.commit()

    logger.info(
        "客户端下载: user=%d platform=%s version=%s log_id=%d",
        user.id, req.platform, latest_ver, dl_log.id,
    )

    if user.referred_by:
        try:
            from app.services.credit.referral_rewards import (
                grant_referral_license_download_reward,
            )
            granted = await grant_referral_license_download_reward(
                user.id, db, source_id=dl_log.id,
            )
            if granted:
                await db.commit()
        except Exception:
            logger.exception("授权码下载推广奖励发放失败 user=%d", user.id)

    return {
        "download_url": download_url,
        "filename": filename,
        "version": latest_ver,
    }


# ── 用户下载记录 ────────────────────────────────────────────

@router.get("/my-downloads")
async def get_my_downloads(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """查看我的下载记录"""
    from app.models.billing import DownloadLog
    result = await db.execute(
        select(DownloadLog)
        .where(DownloadLog.user_id == user.id)
        .order_by(desc(DownloadLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "product_id": log.product_id,
            "version": log.version,
            "platform": log.platform,
            "filename": log.filename,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


# ── Admin：版本分布统计 ──────────────────────────────────────

@router.get("/stats/version-distribution")
async def version_distribution(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """客户端版本分布统计（仅管理员）"""
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    from app.models.billing import DownloadLog

    # 每个版本+平台的下载人数（去重 user_id）
    result = await db.execute(
        select(
            DownloadLog.version,
            DownloadLog.platform,
            func.count(func.distinct(DownloadLog.user_id)).label("users"),
            func.count(DownloadLog.id).label("downloads"),
        )
        .group_by(DownloadLog.version, DownloadLog.platform)
        .order_by(desc("downloads"))
    )
    rows = result.all()

    total_users_result = await db.execute(
        select(func.count(func.distinct(DownloadLog.user_id)))
    )
    total_users = total_users_result.scalar() or 0

    total_downloads_result = await db.execute(
        select(func.count(DownloadLog.id))
    )
    total_downloads = total_downloads_result.scalar() or 0

    return {
        "total_users": total_users,
        "total_downloads": total_downloads,
        "distribution": [
            {
                "version": row.version,
                "platform": row.platform,
                "users": row.users,
                "downloads": row.downloads,
            }
            for row in rows
        ],
    }

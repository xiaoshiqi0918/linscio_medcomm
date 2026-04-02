"""公开下载接口：授权码校验 + 当前版本 + COS 预签名 URL + 下载日志"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import LicenseKey, ReleaseVersion, DownloadLog
from app.schemas.public import (
    CurrentVersionResponse,
    PresignRequest,
    PresignResponse,
)
from app.services.license_service import validate_license_format
from app.services.cos_service import generate_presign_url, is_cos_configured

router = APIRouter(prefix="/public/download", tags=["public"])
PRESIGN_EXPIRES = 7200  # 2 小时


@router.get("/current-version", response_model=CurrentVersionResponse)
async def get_current_version(db: AsyncSession = Depends(get_db)):
    """当前可下载版本信息，供下载页展示「当前最新版 v x.x.x」。无当前版本时 404。"""
    r = await db.execute(
        select(ReleaseVersion).where(ReleaseVersion.is_current == True).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="暂无可用版本")
    return CurrentVersionResponse(
        version=row.version,
        file_size=row.file_size,
        release_notes=row.release_notes,
    )


@router.post("/presign-url", response_model=PresignResponse)
async def post_presign_url(
    data: PresignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    校验授权码后返回当前版本的 COS 预签名下载链接（2 小时有效），并记录下载日志。
    授权码须：格式正确、未作废、未过期（不要求已激活）。
    """
    code = data.license_code.strip().upper()
    ok, err = validate_license_format(code)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "授权码格式错误")

    r = await db.execute(select(LicenseKey).where(LicenseKey.code == code))
    license_key = r.scalar_one_or_none()
    if not license_key:
        raise HTTPException(status_code=404, detail="授权码无效")
    if license_key.is_revoked:
        raise HTTPException(status_code=403, detail="该授权码已作废，请联系管理员")
    now = datetime.now(timezone.utc)
    if license_key.expires_at <= now:
        raise HTTPException(status_code=403, detail="该授权码已过期，请续费后重试")

    rv = await db.execute(
        select(ReleaseVersion).where(ReleaseVersion.is_current == True).limit(1)
    )
    release = rv.scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="暂无可用版本，请稍后再试")

    if not is_cos_configured():
        raise HTTPException(
            status_code=503,
            detail="下载服务暂未配置，请联系管理员",
        )
    try:
        download_url = generate_presign_url(release.file_key, expires_in=PRESIGN_EXPIRES)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent") or None
    db.add(
        DownloadLog(
            license_id=license_key.id,
            version=release.version,
            client_ip=client_ip,
            user_agent=user_agent[:500] if user_agent else None,
        )
    )
    await db.commit()

    return PresignResponse(
        download_url=download_url,
        expires_in_seconds=PRESIGN_EXPIRES,
        version=release.version,
        file_size=release.file_size,
        doc_url="/docs",
    )

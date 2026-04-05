"""
MedComm v3：更新检查、软件下载、学科包下载、下载完成回调
"""
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ReleaseVersion
from app.models.medcomm_models import (
    MedcommUserLicense,
    MedcommUserSpecialty,
    MedcommDownloadLog,
    MedcommSpecialtyVersionPolicy,
)
from app.schemas.medcomm import (
    MedcommUpdateCheckRequest,
    MedcommUpdateCheckResponse,
    MedcommSoftwareUpdateInfo,
    MedcommSpecialtyUpdateItem,
    MedcommSoftwareDownloadRequest,
    MedcommSoftwareDownloadResponse,
    MedcommDownloadCompleteRequest,
    MedcommSpecialtyDownloadRequest,
    MedcommSpecialtyDownloadResponse,
)
from app.services.cos_service import generate_presign_url, is_cos_configured
from app.services.medcomm_manifest_service import (
    load_specialty_manifest,
    specialty_remote_info,
    compare_versions,
)
from app.routers.medcomm_license import get_medcomm_user, security

router = APIRouter(prefix="/medcomm", tags=["medcomm-update-download"])

DOWNLOAD_ANOMALY_THRESHOLD = 5

PLATFORM_EXT = {
    "win-x64": "zip",
    "mac-arm64": "dmg",
    "mac-x64": "dmg",
}


def _platform_file_key(base_file_key: str, version: str, platform: str | None) -> str:
    """Derive a platform-specific COS key from the base file_key.

    Convention: same directory, filename = LinScio-MedComm-{ver}-{platform}.{ext}
    Falls back to base_file_key if platform is unknown.
    """
    if not platform or platform not in PLATFORM_EXT:
        return base_file_key
    ext = PLATFORM_EXT[platform]
    directory = base_file_key.rsplit("/", 1)[0] if "/" in base_file_key else ""
    fname = f"LinScio-MedComm-{version}-{platform}.{ext}"
    return f"{directory}/{fname}" if directory else fname


async def _check_download_anomaly(
    db: AsyncSession, user_id: int, resource_id: str
) -> bool:
    """同 user_id + resource_id 当日生成签名 URL 超过 5 次则标记需人工审核"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    r = await db.execute(
        select(func.count(MedcommDownloadLog.id)).where(
            MedcommDownloadLog.user_id == user_id,
            MedcommDownloadLog.resource_id == resource_id,
            MedcommDownloadLog.created_at >= today_start,
        )
    )
    count = r.scalar() or 0
    return count >= DOWNLOAD_ANOMALY_THRESHOLD


def _version_tuple(v: str) -> tuple:
    parts = []
    for x in (v or "0").strip().lstrip("v").split("."):
        try:
            parts.append(int(x))
        except ValueError:
            parts.append(0)
    return tuple(parts[:4] or [0])


def _software_has_update(client_ver: str, server_ver: str) -> bool:
    return _version_tuple(server_ver) > _version_tuple(client_ver)


@router.post("/update/check", response_model=MedcommUpdateCheckResponse)
async def medcomm_update_check(
    body: MedcommUpdateCheckRequest,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """合并检查软件与学科包更新（Bearer access_token 或 session_token）"""
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    ul = await db.execute(
        select(MedcommUserLicense).where(MedcommUserLicense.user_id == user.id)
    )
    lic = ul.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    base_valid = bool(
        lic and lic.expires_at and lic.expires_at > now and lic.access_token
    )

    manifest = load_specialty_manifest()
    specialty_updates: list[MedcommSpecialtyUpdateItem] = []

    r = await db.execute(
        select(MedcommUserSpecialty).where(MedcommUserSpecialty.user_id == user.id)
    )
    owned = {s.specialty_id for s in r.scalars().all()}

    pol_r = await db.execute(select(MedcommSpecialtyVersionPolicy))
    policies = {p.specialty_id: p for p in pol_r.scalars().all()}

    for sid, local_v in (body.specialties or {}).items():
        if sid not in owned:
            continue
        info = specialty_remote_info(manifest, sid)
        remote_v = info.get("version")
        if not remote_v:
            continue
        cmp = compare_versions(local_v, remote_v)
        has_update = cmp < 0
        full_pkg = info.get("full_package") or {}
        force_update = False
        force_msg = None
        pol = policies.get(sid)
        if pol and pol.force_min_version and compare_versions(local_v, pol.force_min_version) < 0:
            force_update = True
            force_msg = pol.policy_message
        if pol and pol.force_max_version and compare_versions(local_v, pol.force_max_version) > 0:
            force_update = True
            force_msg = pol.policy_message or force_msg

        chlog = []
        for c in info.get("changelog") or []:
            if isinstance(c, dict) and c.get("version") == remote_v:
                chlog = c.get("changes") or []
                break

        specialty_updates.append(
            MedcommSpecialtyUpdateItem(
                id=sid,
                latest_version=remote_v,
                has_update=has_update,
                size_mb=full_pkg.get("size_mb"),
                full_size_mb=full_pkg.get("size_mb"),
                changelog=chlog if isinstance(chlog, list) else [],
                force_update=force_update,
                force_message=force_msg,
            )
        )

    has_sw = False
    sw_info = None
    rv = await db.execute(
        select(ReleaseVersion).where(ReleaseVersion.is_current == True).limit(1)
    )
    release = rv.scalar_one_or_none()
    if release and base_valid and _software_has_update(body.software_version, release.version):
        has_sw = True
        url = None
        size_mb = None
        if is_cos_configured():
            try:
                fk = _platform_file_key(release.file_key, release.version, body.platform)
                url = generate_presign_url(fk, expires_in=3600)
                if release.file_size:
                    size_mb = round(release.file_size / (1024 * 1024), 2)
            except Exception:
                url = None
        sw_info = MedcommSoftwareUpdateInfo(
            version=release.version,
            release_notes=release.release_notes,
            download_url=url,
            size_mb=size_mb,
        )

    return MedcommUpdateCheckResponse(
        base_valid=base_valid,
        has_software_update=has_sw,
        software=sw_info,
        specialty_updates=specialty_updates,
    )


@router.post("/download/software", response_model=MedcommSoftwareDownloadResponse)
async def medcomm_download_software(
    body: MedcommSoftwareDownloadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """获取软件安装包预签名 URL（授权有效期内；Bearer access_token）"""
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    ul = await db.execute(
        select(MedcommUserLicense).where(MedcommUserLicense.user_id == user.id)
    )
    lic = ul.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not lic or not lic.expires_at or lic.expires_at <= now:
        return MedcommSoftwareDownloadResponse(
            success=False,
            error="license_expired",
        )
    if not lic.access_token:
        return MedcommSoftwareDownloadResponse(
            success=False,
            error="not_activated",
        )

    rv = await db.execute(
        select(ReleaseVersion).where(ReleaseVersion.is_current == True).limit(1)
    )
    release = rv.scalar_one_or_none()
    if not release:
        return MedcommSoftwareDownloadResponse(success=False, error="no_release")

    if not is_cos_configured():
        return MedcommSoftwareDownloadResponse(success=False, error="cos_not_configured")

    try:
        fk = _platform_file_key(release.file_key, release.version, body.platform)
        url = generate_presign_url(fk, expires_in=3600)
    except Exception as e:
        return MedcommSoftwareDownloadResponse(success=False, error=str(e))

    client_ip = request.client.host if request.client else ""
    ua = (request.headers.get("user-agent") or "")[:500]
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:64]
    needs_review = await _check_download_anomaly(db, user.id, release.version)
    log = MedcommDownloadLog(
        user_id=user.id,
        download_type="software",
        resource_id=release.version,
        platform=body.platform[:30] if body.platform else None,
        signed_url_hash=url_hash,
        client_ip=client_ip[:45] if client_ip else None,
        user_agent=ua,
        needs_review=1 if needs_review else 0,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    ext = PLATFORM_EXT.get(body.platform, fk.rsplit(".", 1)[-1] if "." in fk else "bin")
    fname = f"LinScio-MedComm-{release.version}-{body.platform or 'unknown'}.{ext}"
    size_mb = round(release.file_size / (1024 * 1024), 2) if release.file_size else None

    return MedcommSoftwareDownloadResponse(
        success=True,
        download_url=url,
        filename=fname,
        size_mb=size_mb,
        download_log_id=log.id,
    )


@router.post("/download/complete")
async def medcomm_download_complete(
    body: MedcommDownloadCompleteRequest,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """下载完成回调"""
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    r = await db.execute(
        select(MedcommDownloadLog).where(
            MedcommDownloadLog.id == body.download_log_id,
            MedcommDownloadLog.user_id == user.id,
        )
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    row.completed = 1
    row.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True}


@router.post("/specialty/download", response_model=MedcommSpecialtyDownloadResponse)
async def medcomm_specialty_download(
    body: MedcommSpecialtyDownloadRequest,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """学科包下载预签名 URL（需已购买该学科）"""
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    r = await db.execute(
        select(MedcommUserSpecialty).where(
            MedcommUserSpecialty.user_id == user.id,
            MedcommUserSpecialty.specialty_id == body.specialty_id,
        )
    )
    if not r.scalar_one_or_none():
        return MedcommSpecialtyDownloadResponse(success=False, error="not_purchased")

    manifest = load_specialty_manifest()
    info = specialty_remote_info(manifest, body.specialty_id)
    remote_v = info.get("version")
    if not remote_v or remote_v != body.version:
        return MedcommSpecialtyDownloadResponse(
            success=False,
            error="version_not_found",
        )

    full_pkg = info.get("full_package") or {}
    patch_map = info.get("patch_from") or {}
    package_type = "full"
    pkg_meta = full_pkg
    if body.from_version and isinstance(patch_map, dict):
        patch = patch_map.get(body.from_version)
        if patch and isinstance(patch, dict):
            package_type = "patch"
            pkg_meta = patch

    fname = pkg_meta.get("filename") or f"{body.specialty_id}-{body.version}-full.db"
    file_key = f"specialties/{body.specialty_id}/v{body.version}/{fname}"

    if not is_cos_configured():
        return MedcommSpecialtyDownloadResponse(success=False, error="cos_not_configured")

    try:
        url = generate_presign_url(file_key, expires_in=7200)
    except Exception:
        return MedcommSpecialtyDownloadResponse(
            success=False,
            error="object_not_found",
        )

    resource_id = f"{body.specialty_id}@{body.version}"
    needs_review = await _check_download_anomaly(db, user.id, resource_id)
    log = MedcommDownloadLog(
        user_id=user.id,
        download_type="specialty",
        resource_id=resource_id,
        platform=None,
        signed_url_hash=hashlib.sha256(url.encode()).hexdigest()[:64],
        needs_review=1 if needs_review else 0,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return MedcommSpecialtyDownloadResponse(
        success=True,
        package_type=package_type,
        download_url=url,
        filename=fname,
        size_mb=pkg_meta.get("size_mb"),
        md5=pkg_meta.get("md5"),
        download_log_id=log.id,
        expires_in=7200,
    )


@router.get("/specialty/{specialty_id}/documents")
async def medcomm_specialty_documents(
    specialty_id: str,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """学科包关联文档列表（预签名 URL + Deep Link 占位）"""
    user = await get_medcomm_user(cred, db)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    r = await db.execute(
        select(MedcommUserSpecialty).where(
            MedcommUserSpecialty.user_id == user.id,
            MedcommUserSpecialty.specialty_id == specialty_id,
        )
    )
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="未购买该学科包")

    manifest = load_specialty_manifest()
    info = specialty_remote_info(manifest, specialty_id)
    docs_out = []
    for d in info.get("documents") or []:
        if not isinstance(d, dict):
            continue
        fn = d.get("filename") or "doc.pdf"
        title = d.get("title") or fn
        key = f"specialties/{specialty_id}/documents/{fn}"
        url = None
        if is_cos_configured():
            try:
                url = generate_presign_url(key, expires_in=3600)
            except Exception:
                url = None
        deep_link = f"linscio://import/document?specialty={specialty_id}&title={title}"
        if url:
            from urllib.parse import quote
            deep_link += f"&url={quote(url, safe='')}"
        docs_out.append(
            {
                "filename": fn,
                "title": title,
                "size_mb": d.get("size_mb"),
                "download_url": url,
                "deep_link": deep_link,
            }
        )
    return {"documents": docs_out}

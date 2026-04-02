# 云端管控接口规范 9.1～9.3：heartbeat、latest-version、tauri-update（Bearer 鉴权：portal JWT 或 container-token）
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PortalUser, ContainerToken, ClientHeartbeat, AppVersion
from app.schemas.client import (
    HeartbeatRequest,
    HeartbeatResponse,
    LatestVersionResponse,
    TauriUpdateResponse,
)
from app.services.auth_service import decode_access_token

router = APIRouter(prefix="/client", tags=["client"])
security = HTTPBearer(auto_error=False)


def _version_tuple(v: str) -> tuple:
    """将版本号转为可比较元组，如 '1.2.3' -> (1, 2, 3)。"""
    parts = []
    for x in (v or "0").strip().lstrip("v").split("."):
        try:
            parts.append(int(x))
        except ValueError:
            parts.append(0)
    return tuple(parts[:4] or [0])  # 最多 4 段


def _version_gt(a: str, b: str) -> bool:
    """是否 a > b。"""
    return _version_tuple(a) > _version_tuple(b)


async def get_client_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> PortalUser:
    """Bearer：优先解析为 portal JWT，否则按 container-token (ls_tok_xxx) 查表取 user_id。"""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="缺少或无效的 Authorization")
    token = credentials.credentials.strip()

    user_id = decode_access_token(token)
    if user_id:
        r = await db.execute(select(PortalUser).where(PortalUser.id == user_id))
        user = r.scalar_one_or_none()
        if user and user.is_active:
            return user
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    if token.startswith("ls_tok_"):
        r = await db.execute(
            select(ContainerToken).where(
                ContainerToken.token == token,
                ContainerToken.is_revoked == False,
            )
        )
        ct = r.scalar_one_or_none()
        if not ct:
            raise HTTPException(status_code=401, detail="令牌无效或已失效")
        if ct.expires_at and ct.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="令牌已过期")
        ru = await db.execute(select(PortalUser).where(PortalUser.id == ct.user_id))
        user = ru.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        return user

    raise HTTPException(status_code=401, detail="无效的 Authorization")


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def client_heartbeat(
    body: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_client_user),
):
    """9.1 心跳接口：记录 client_heartbeats，响应包含心跳间隔、force_update、force_rollback、公告。"""
    h = ClientHeartbeat(
        user_id=user.id,
        machine_id=body.machine_id.strip(),
        app_version=body.app_version,
        os_type=body.os_type,
        os_version=body.os_version,
        uptime_seconds=body.uptime_seconds,
        deployment=body.deployment or "desktop",
    )
    db.add(h)
    await db.commit()

    r = await db.execute(
        select(AppVersion).where(AppVersion.is_current == True).limit(1)
    )
    current = r.scalar_one_or_none()
    if not current:
        return HeartbeatResponse(
            ok=True,
            next_interval_seconds=1800,
            force_update=None,
            force_rollback=None,
            announcement=None,
        )
    return HeartbeatResponse(
        ok=True,
        next_interval_seconds=1800,
        force_update=current.force_update,
        force_rollback=bool(current.rollback_version),
        announcement=current.announcement,
    )


@router.get("/latest-version", response_model=LatestVersionResponse)
async def latest_version(
    current_version: str | None = Query(None, description="客户端当前版本，用于计算 has_update"),
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_client_user),
):
    """9.2 版本检测接口：返回 latest_version、has_update、force_update、release_notes、download_urls、min_supported_version。"""
    r = await db.execute(
        select(AppVersion).where(AppVersion.is_current == True).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        return LatestVersionResponse(
            latest_version="0.0.0",
            version="0.0.0",
            has_update=False,
            force_update=False,
            release_notes=None,
            download_urls={"windows": "", "macos": "", "linux": ""},
            min_supported_version=None,
        )
    latest = row.version
    has_update = bool(
        current_version and _version_gt(latest, current_version)
    )
    return LatestVersionResponse(
        latest_version=latest,
        version=latest,
        has_update=has_update,
        force_update=row.force_update,
        release_notes=row.release_notes,
        download_urls={
            "windows": row.download_url_windows or "",
            "macos": row.download_url_macos or "",
            "linux": row.download_url_linux or "",
        },
        min_supported_version=row.min_supported_version,
    )


@router.get("/tauri-update")
async def tauri_update(
    current_version: str | None = Query(None, description="当前客户端版本"),
    platform: str | None = Query(None, description="Tauri 平台 ID，如 darwin-aarch64、windows-x86_64"),
    db: AsyncSession = Depends(get_db),
):
    """9.3 Tauri Updater 端点：符合 Tauri 标准 JSON。当前已是最新时返回 204 No Content。"""
    r = await db.execute(
        select(AppVersion).where(AppVersion.is_current == True).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        return Response(status_code=204)
    latest = row.version
    if current_version and not _version_gt(latest, current_version):
        return Response(status_code=204)

    # 从 tauri_platforms 取当前平台的 url、signature；若无则用通用 download_url_* 映射
    url = ""
    signature = None
    if row.tauri_platforms and isinstance(row.tauri_platforms, dict) and platform:
        plat = row.tauri_platforms.get(platform) or row.tauri_platforms.get(platform.replace("-", "_"))
        if isinstance(plat, dict):
            url = plat.get("url") or ""
            signature = plat.get("signature")
    if not url and platform:
        if "windows" in platform:
            url = row.download_url_windows or ""
        elif "darwin" in platform or "macos" in platform:
            url = row.download_url_macos or ""
        elif "linux" in platform:
            url = row.download_url_linux or ""
    if not url:
        url = row.download_url_windows or row.download_url_macos or row.download_url_linux or ""

    pub_date = None
    if row.pub_date:
        pub_date = row.pub_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    return TauriUpdateResponse(
        version=latest,
        notes=row.release_notes,
        pub_date=pub_date,
        url=url,
        signature=signature,
    )

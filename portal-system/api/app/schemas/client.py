# 云端管控接口规范 9.1～9.3：heartbeat、latest-version、tauri-update
from pydantic import BaseModel
from typing import Optional


# ----- 9.1 心跳 -----
class HeartbeatRequest(BaseModel):
    app_version: Optional[str] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    machine_id: str
    uptime_seconds: Optional[int] = None
    deployment: Optional[str] = "desktop"


class HeartbeatResponse(BaseModel):
    ok: bool = True
    next_interval_seconds: Optional[int] = None  # 心跳间隔（秒）
    force_update: Optional[bool] = None
    force_rollback: Optional[bool] = None
    announcement: Optional[str] = None


# ----- 9.2 版本检测 -----
class LatestVersionResponse(BaseModel):
    latest_version: str
    version: Optional[str] = None  # 兼容旧字段，与 latest_version 一致
    has_update: bool = False
    force_update: Optional[bool] = None
    release_notes: Optional[str] = None
    download_urls: Optional[dict] = None  # {"windows":"","macos":"","linux":""}
    min_supported_version: Optional[str] = None


# ----- 9.3 Tauri Updater 标准 JSON（单平台） -----
class TauriUpdateResponse(BaseModel):
    version: str
    notes: Optional[str] = None
    pub_date: Optional[str] = None  # ISO 8601
    url: str
    signature: Optional[str] = None

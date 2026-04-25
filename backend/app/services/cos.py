"""
腾讯云 COS 服务 — 客户端安装包下载
- 优先从 COS 读取 manifest.json（产品版本信息）
- COS 不可用时自动降级到本地 deploy/cos-manifest.json
- 生成预签名下载 URL
"""
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_manifest_cache: dict[str, Any] = {}
_manifest_ts: float = 0
_CACHE_TTL = 300  # 5 分钟缓存

_LOCAL_MANIFEST = Path(__file__).resolve().parent.parent.parent.parent / "deploy" / "cos-manifest.json"


def _get_cos_client():
    from qcloud_cos import CosConfig, CosS3Client
    config = CosConfig(
        Region=settings.cos_region,
        SecretId=settings.cos_secret_id,
        SecretKey=settings.cos_secret_key,
    )
    return CosS3Client(config)


def _manifest_bucket() -> str:
    return settings.cos_bucket_manifest or settings.cos_bucket_releases


def read_manifest() -> dict:
    """读取 manifest.json，带 5 分钟内存缓存。优先 COS，降级本地文件。"""
    global _manifest_cache, _manifest_ts

    now = time.time()
    if _manifest_cache and (now - _manifest_ts) < _CACHE_TTL:
        return _manifest_cache

    if settings.cos_secret_id:
        try:
            client = _get_cos_client()
            resp = client.get_object(
                Bucket=_manifest_bucket(),
                Key="manifest.json",
            )
            body = resp["Body"].get_raw_stream().read()
            _manifest_cache = json.loads(body)
            _manifest_ts = now
            logger.info("manifest.json 已从 COS 加载")
            return _manifest_cache
        except Exception:
            logger.warning("从 COS 读取 manifest.json 失败，尝试本地文件")

    return _read_local_manifest()


def _read_local_manifest() -> dict:
    """从本地 deploy/cos-manifest.json 读取"""
    global _manifest_cache, _manifest_ts
    if _LOCAL_MANIFEST.exists():
        try:
            data = json.loads(_LOCAL_MANIFEST.read_text(encoding="utf-8"))
            _manifest_cache = data
            _manifest_ts = time.time()
            logger.info("manifest.json 已从本地文件加载: %s", _LOCAL_MANIFEST)
            return data
        except Exception:
            logger.exception("本地 manifest.json 解析失败")

    logger.warning("无可用 manifest.json（COS 和本地均不可用），返回硬编码默认值")
    return {
        "schema_version": "2.0",
        "products": [
            {
                "id": "MedComm",
                "name": "LinScio MedComm",
                "latest_version": "1.0.0",
                "platforms": ["mac-arm64", "mac-x64", "win-x64"],
                "platform_status": {},
                "download_files": {},
            }
        ],
        "specialties": [],
        "drawing_packs": [],
    }


def generate_presigned_download_url(cos_key: str, expires: int = 3600) -> str:
    """生成预签名下载 URL"""
    client = _get_cos_client()
    return client.get_presigned_download_url(
        Bucket=settings.cos_bucket_releases,
        Key=cos_key,
        Expired=expires,
    )

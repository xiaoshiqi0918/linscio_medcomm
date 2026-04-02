"""
MedComm 学科包 manifest（COS JSON），用于远端版本与更新检查
"""
import json
from typing import Any

from app.config import settings
from app.services.cos_service import is_cos_configured


def _fetch_cos_object_bytes(key: str) -> bytes | None:
    if not is_cos_configured():
        return None
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        return None
    try:
        config = CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
            Scheme="https",
        )
        client = CosS3Client(config)
        resp = client.get_object(Bucket=settings.COS_BUCKET, Key=key)
        body = resp["Body"].get_raw_stream().read()
        return body
    except Exception:
        return None


def load_specialty_manifest() -> dict[str, Any]:
    """
    返回 manifest 解析结果；失败返回空 dict。
    结构参考 v3 文档 manifest.json
    """
    key = getattr(settings, "MEDCOMM_SPECIALTY_MANIFEST_KEY", "") or "specialties/manifest.json"
    raw = _fetch_cos_object_bytes(key)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def specialty_remote_info(manifest: dict, specialty_id: str) -> dict[str, Any]:
    """从 manifest 取某学科最新版本信息"""
    for s in manifest.get("specialties") or []:
        if s.get("id") == specialty_id:
            return {
                "version": s.get("version"),
                "full_package": s.get("full_package") or {},
                "patch_from": s.get("patch_from") or {},
                "changelog": s.get("changelog") or [],
                "version_policy": s.get("version_policy") or {},
            }
    return {}


def compare_versions(a: str | None, b: str | None) -> int:
    """语义化版本比较：a < b -> -1, a == b -> 0, a > b -> 1"""
    if not a or not b:
        return 0
    pa = [int(x) if x.isdigit() else 0 for x in a.replace("v", "").split(".")[:4]]
    pb = [int(x) if x.isdigit() else 0 for x in b.replace("v", "").split(".")[:4]]
    while len(pa) < 4:
        pa.append(0)
    while len(pb) < 4:
        pb.append(0)
    for x, y in zip(pa, pb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0

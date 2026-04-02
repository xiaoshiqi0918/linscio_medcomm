"""许可配置加载"""
import json
import os
from pathlib import Path
from typing import Any

from app.core.config import settings


def load_license() -> dict[str, Any]:
    """从 config/license.json 或环境变量加载，默认 basic"""
    default: dict[str, Any] = {
        "type": "basic",
        "custom_specialties": [],
        "service_expiry": None,
        "content_version": "1.0",
        "next_content_update": None,
        "preset_docs": [],
        "specialty_stats": {},  # {"内分泌科": {"terms": 487, "examples": 68, "docs": 23}}
    }
    cfg_path = Path(settings.app_data_root) / "config" / "license.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
                default.update(data)
        except Exception:
            pass
    if os.environ.get("LINSCIO_LICENSE_TYPE") == "custom":
        default["type"] = "custom"
        default["custom_specialties"] = os.environ.get("LINSCIO_CUSTOM_SPECIALTIES", "内分泌科,心内科").split(",")
    return default

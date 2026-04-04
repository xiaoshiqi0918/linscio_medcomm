"""
角色一致性服务（B-2 多格连续叙事）。

使用 ComfyUI IP-Adapter 工作流：
1. 用户上传或选择一张参考角色图
2. 后续每格图像生成时将参考图注入 IP-Adapter LoadImage 节点
3. IP-Adapter 保持角色外观一致性
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings

_log = logging.getLogger(__name__)

IPADAPTER_WORKFLOW = "workflows/comfyui/medcomm_t2i_sdxl_ipadapter.api.json"
LOAD_IMAGE_NODE_ID = "12"
IPADAPTER_NODE_ID = "13"


def _ref_dir() -> Path:
    d = Path(settings.app_data_root) / "medpic" / "references"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_reference_image(data: bytes, filename: str = "") -> str:
    """
    保存角色参考图到本地，返回相对路径（相对于 app_data_root）。
    """
    h = hashlib.sha256(data).hexdigest()[:12]
    ext = Path(filename).suffix if filename else ".png"
    if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        ext = ".png"
    fn = f"ref_{h}{ext}"
    dest = _ref_dir() / fn
    dest.write_bytes(data)
    return str(dest.relative_to(settings.app_data_root))


def save_reference_from_generated(generated_rel_path: str) -> str:
    """
    将已生成的图片复制为参考图。
    """
    src = Path(settings.app_data_root) / generated_rel_path
    if not src.is_file():
        raise FileNotFoundError(f"源图不存在: {src}")
    data = src.read_bytes()
    return save_reference_image(data, src.name)


def list_references() -> list[dict[str, str]]:
    """
    列出所有保存的参考图。
    """
    d = _ref_dir()
    items = []
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            rel = str(f.relative_to(settings.app_data_root))
            items.append({
                "path": rel,
                "serve_url": f"/api/v1/imagegen/serve?path={rel}",
                "filename": f.name,
            })
    return items


def patch_workflow_with_reference(
    workflow: dict[str, Any],
    reference_image_filename: str,
    weight: float = 0.7,
) -> dict[str, Any]:
    """
    将参考角色图注入 IP-Adapter 工作流的 LoadImage 节点。
    ComfyUI 的 LoadImage 节点需要 ComfyUI input 目录下的文件名。
    """
    w = copy.deepcopy(workflow)
    load_node = w.get(LOAD_IMAGE_NODE_ID)
    if isinstance(load_node, dict):
        load_node.setdefault("inputs", {})["image"] = reference_image_filename

    ipa_node = w.get(IPADAPTER_NODE_ID)
    if isinstance(ipa_node, dict) and weight is not None:
        ipa_node.setdefault("inputs", {})["weight"] = float(weight)

    return w


def copy_ref_to_comfy_input(ref_rel_path: str) -> str:
    """
    将参考图复制到 ComfyUI 的 input 目录，返回 ComfyUI 可识别的文件名。
    """
    import os
    comfy_input = os.environ.get("COMFYUI_INPUT_DIR", "").strip()
    if not comfy_input:
        comfy_base = os.environ.get("COMFYUI_BASE_DIR", "").strip()
        if comfy_base:
            comfy_input = str(Path(comfy_base) / "input")
        else:
            comfy_input = str(Path.home() / "ComfyUI" / "input")

    input_dir = Path(comfy_input)
    input_dir.mkdir(parents=True, exist_ok=True)

    src = Path(settings.app_data_root) / ref_rel_path
    if not src.is_file():
        raise FileNotFoundError(f"参考图不存在: {src}")

    dest = input_dir / src.name
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)

    return src.name

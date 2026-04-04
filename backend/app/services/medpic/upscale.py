"""
高分辨率输出服务（D-2 线下印刷海报）。

两步管线：
1. 先按常规分辨率生成底图（由 MedPic 主流程完成）
2. 调用 ComfyUI 超分辨率工作流做 2-4x 放大

支持两种模式：
- ComfyUI 模式：使用 RealESRGAN / ESRGAN 超分辨率模型（需模型文件就位）
- PIL 降级模式：使用 Pillow Lanczos 放大（无需 ComfyUI upscale 模型）
"""
from __future__ import annotations

import copy
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import settings

_log = logging.getLogger(__name__)

UPSCALE_WORKFLOW = "workflows/comfyui/medcomm_upscale.api.json"
LOAD_IMAGE_NODE_ID = "1"
IMAGE_SCALE_NODE_ID = "4"

PRINT_SIZES: dict[str, tuple[int, int]] = {
    "A3": (3508, 4961),
    "A4": (2480, 3508),
}

DEFAULT_PRINT_SIZE = "A3"
DEFAULT_DPI = 300


def _output_dir() -> Path:
    now = datetime.utcnow()
    d = Path(settings.app_data_root) / f"images/{now.year}/{now.month:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_image(img: Image.Image, tag: str) -> str:
    buf = img.tobytes()
    h = hashlib.sha256(buf[:4096]).hexdigest()[:10]
    fn = f"upscale_{tag}_{h}.png"
    out = _output_dir() / fn
    img.save(out, "PNG")
    return str(out.relative_to(settings.app_data_root))


async def upscale_with_comfyui(
    source_rel_path: str,
    target_width: int,
    target_height: int,
) -> str | None:
    """
    使用 ComfyUI 超分辨率工作流放大图像。
    返回结果图相对路径，失败返回 None。
    """
    wf_path = Path(UPSCALE_WORKFLOW)
    if not wf_path.expanduser().is_file():
        _log.info("ComfyUI upscale workflow not found: %s", wf_path)
        return None

    import json
    workflow = json.loads(wf_path.read_text(encoding="utf-8"))

    src_full = Path(settings.app_data_root) / source_rel_path
    if not src_full.is_file():
        raise FileNotFoundError(f"源图不存在: {src_full}")

    comfy_input = os.environ.get("COMFYUI_INPUT_DIR", "").strip()
    if not comfy_input:
        comfy_base = os.environ.get("COMFYUI_BASE_DIR", "").strip()
        if comfy_base:
            comfy_input = str(Path(comfy_base) / "input")
        else:
            comfy_input = str(Path.home() / "ComfyUI" / "input")

    input_dir = Path(comfy_input)
    input_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    dest = input_dir / src_full.name
    shutil.copy2(src_full, dest)

    w = copy.deepcopy(workflow)
    load_node = w.get(LOAD_IMAGE_NODE_ID)
    if isinstance(load_node, dict):
        load_node.setdefault("inputs", {})["image"] = src_full.name

    scale_node = w.get(IMAGE_SCALE_NODE_ID)
    if isinstance(scale_node, dict):
        inputs = scale_node.setdefault("inputs", {})
        inputs["width"] = target_width
        inputs["height"] = target_height

    from app.services.imagegen.comfy_client import (
        _api_prefix,
    )

    mode = os.environ.get("COMFYUI_MODE", "local").strip().lower()
    base_url = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188").strip()
    prefix = _api_prefix(base_url, mode)
    api_key = os.environ.get("COMFY_CLOUD_API_KEY", "").strip() if mode == "cloud" else None

    import uuid
    import httpx
    import asyncio

    client_id = str(uuid.uuid4())
    body = {"prompt": w, "client_id": client_id}
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    timeout = httpx.Timeout(600.0, connect=30.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.post(f"{prefix}/prompt", json=body, headers=headers)
            if r.status_code >= 400:
                _log.warning("ComfyUI upscale submit failed: %s", r.text[:300])
                return None
            data = r.json()
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                return None

            from app.services.imagegen.comfy_client import _poll_history, _collect_output_images
            hist = await _poll_history(client, prefix, prompt_id, 600, 2.0)
            images = _collect_output_images(hist, prompt_id)
            if not images:
                return None

            img_info = images[0]
            params = {
                "filename": img_info["filename"],
                "subfolder": img_info.get("subfolder", ""),
                "type": img_info.get("type", "output"),
            }
            vr = await client.get(f"{prefix}/view", params=params)
            vr.raise_for_status()

            from app.services.imagegen.engine import _save_local
            rel = _save_local(vr.content, provider="comfyui_upscale", image_type="upscaled")
            return rel
    except Exception as e:
        _log.warning("ComfyUI upscale failed: %s", e)
        return None


def upscale_with_pil(
    source_rel_path: str,
    target_width: int,
    target_height: int,
) -> str:
    """
    PIL Lanczos 降级放大。无需 ComfyUI upscale 模型。
    """
    src = Path(settings.app_data_root) / source_rel_path
    if not src.is_file():
        raise FileNotFoundError(f"源图不存在: {src}")

    img = Image.open(src).convert("RGB")
    upscaled = img.resize((target_width, target_height), Image.LANCZOS)
    return _save_image(upscaled, "pil")


async def upscale_image(
    source_rel_path: str,
    print_size: str = DEFAULT_PRINT_SIZE,
    aspect: str = "3:4",
) -> dict[str, Any]:
    """
    高分辨率放大入口：优先 ComfyUI，降级 PIL。
    返回 {"path": str, "serve_url": str, "method": str, "width": int, "height": int}
    """
    tw, th = PRINT_SIZES.get(print_size, PRINT_SIZES[DEFAULT_PRINT_SIZE])

    if aspect == "16:9":
        tw, th = max(tw, th), min(tw, th)
    elif aspect in ("9:16", "3:4"):
        tw, th = min(tw, th), max(tw, th)

    result = await upscale_with_comfyui(source_rel_path, tw, th)
    method = "comfyui_esrgan"

    if result is None:
        result = upscale_with_pil(source_rel_path, tw, th)
        method = "pil_lanczos"

    return {
        "path": result,
        "serve_url": f"/api/v1/imagegen/serve?path={result}",
        "method": method,
        "width": tw,
        "height": th,
    }

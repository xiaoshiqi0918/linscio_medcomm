"""
后处理缩放服务。

将 ComfyUI 生成的 latent 尺寸图片缩放到最终输出尺寸。
- 标准/高配档：PIL Lanczos 缩放（差距小，质量足够）
- 低配档：优先 Real-ESRGAN（ComfyUI upscale），降级 PIL Lanczos
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.core.config import settings

_log = logging.getLogger(__name__)


def _output_dir() -> Path:
    now = datetime.utcnow()
    d = Path(settings.app_data_root) / f"images/{now.year}/{now.month:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resize_image(
    source_rel_path: str,
    target_width: int,
    target_height: int,
) -> str:
    """
    PIL Lanczos 缩放。用于标准/高配档的小幅放大（如 1024→1080）。
    返回输出图相对路径。
    """
    src = Path(settings.app_data_root) / source_rel_path
    if not src.is_file():
        raise FileNotFoundError(f"源图不存在: {src}")

    img = Image.open(src).convert("RGB")
    if img.size == (target_width, target_height):
        return source_rel_path

    resized = img.resize((target_width, target_height), Image.LANCZOS)

    h = hashlib.sha256(source_rel_path.encode()).hexdigest()[:10]
    fn = f"resized_{target_width}x{target_height}_{h}.png"
    out = _output_dir() / fn
    resized.save(out, "PNG", quality=95)
    return str(out.relative_to(settings.app_data_root))


async def finalize_image(
    source_rel_path: str,
    target_width: int,
    target_height: int,
    hardware_tier: str = "standard",
) -> dict:
    """
    后处理入口。

    - 标准/高配：PIL Lanczos（差距小，低延迟）
    - 低配：尝试 ComfyUI ESRGAN 超分（差距大），失败降级 PIL

    Returns
    -------
    dict
        {"path": str, "serve_url": str, "method": str, "width": int, "height": int}
    """
    src = Path(settings.app_data_root) / source_rel_path
    if not src.is_file():
        raise FileNotFoundError(f"源图不存在: {src}")

    img = Image.open(src)
    src_w, src_h = img.size
    img.close()

    if src_w == target_width and src_h == target_height:
        return {
            "path": source_rel_path,
            "serve_url": f"/api/v1/imagegen/serve?path={source_rel_path}",
            "method": "none",
            "width": target_width,
            "height": target_height,
        }

    scale_factor = max(target_width / src_w, target_height / src_h)

    if hardware_tier == "low" and scale_factor > 1.3:
        try:
            from app.services.medpic.upscale import upscale_with_comfyui
            result = await upscale_with_comfyui(source_rel_path, target_width, target_height)
            if result:
                return {
                    "path": result,
                    "serve_url": f"/api/v1/imagegen/serve?path={result}",
                    "method": "esrgan",
                    "width": target_width,
                    "height": target_height,
                }
        except Exception as e:
            _log.info("ESRGAN upscale failed for low-tier, falling back to PIL: %s", e)

    rel = resize_image(source_rel_path, target_width, target_height)
    return {
        "path": rel,
        "serve_url": f"/api/v1/imagegen/serve?path={rel}",
        "method": "lanczos",
        "width": target_width,
        "height": target_height,
    }

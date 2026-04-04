"""
竖版长图分段拼接服务（F-1 / F-2 / F-3）。

策略：
1. 根据段落数量，每段独立生成 1024×1024 图像
2. 使用 PIL 按顺序竖向拼接成长图
3. 对微信公众号场景（F-2），按 ≤600 万像素规则自动切片
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import settings

_log = logging.getLogger(__name__)

SEGMENT_SIZE = (1024, 1024)
WECHAT_MAX_PIXELS = 6_000_000
WECHAT_OUTPUT_WIDTH = 1200


def _output_dir() -> Path:
    now = datetime.utcnow()
    d = Path(settings.app_data_root) / f"images/{now.year}/{now.month:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _hash_tag(data: bytes, length: int = 10) -> str:
    return hashlib.sha256(data[:4096]).hexdigest()[:length]


def stitch_segments(segment_rel_paths: list[str], output_width: int = 1080) -> str:
    """
    将多张段落图像竖向拼接成一张长图。

    Parameters
    ----------
    segment_rel_paths : list[str]
        每段图像相对于 app_data_root 的路径
    output_width : int
        输出图的宽度，每段按比例缩放

    Returns
    -------
    str
        拼接后长图相对路径
    """
    if not segment_rel_paths:
        raise ValueError("至少需要一段图像")

    segments: list[Image.Image] = []
    total_h = 0

    for rp in segment_rel_paths:
        fp = Path(settings.app_data_root) / rp
        if not fp.is_file():
            raise FileNotFoundError(f"段落图不存在: {fp}")
        img = Image.open(fp).convert("RGB")
        ratio = output_width / img.width
        new_h = round(img.height * ratio)
        img = img.resize((output_width, new_h), Image.LANCZOS)
        segments.append(img)
        total_h += new_h

    canvas = Image.new("RGB", (output_width, total_h), (255, 255, 255))
    y = 0
    for seg in segments:
        canvas.paste(seg, (0, y))
        y += seg.height

    h = _hash_tag(canvas.tobytes()[:8192])
    fn = f"longimage_stitched_{h}.png"
    out = _output_dir() / fn
    canvas.save(out, "PNG")
    return str(out.relative_to(settings.app_data_root))


def slice_for_wechat(long_image_rel_path: str) -> list[str]:
    """
    将长图切片为微信公众号兼容的片段（每片 ≤ 600 万像素）。

    Parameters
    ----------
    long_image_rel_path : str
        长图相对路径

    Returns
    -------
    list[str]
        各切片的相对路径
    """
    fp = Path(settings.app_data_root) / long_image_rel_path
    if not fp.is_file():
        raise FileNotFoundError(f"长图不存在: {fp}")

    img = Image.open(fp).convert("RGB")
    w, h = img.size

    if w != WECHAT_OUTPUT_WIDTH:
        ratio = WECHAT_OUTPUT_WIDTH / w
        new_h = round(h * ratio)
        img = img.resize((WECHAT_OUTPUT_WIDTH, new_h), Image.LANCZOS)
        w, h = img.size

    max_slice_h = WECHAT_MAX_PIXELS // w
    if h <= max_slice_h:
        return [long_image_rel_path]

    slices: list[str] = []
    y = 0
    idx = 0
    while y < h:
        slice_h = min(max_slice_h, h - y)
        crop = img.crop((0, y, w, y + slice_h))
        hh = _hash_tag(crop.tobytes()[:4096])
        fn = f"longimage_slice_{idx}_{hh}.png"
        out = _output_dir() / fn
        crop.save(out, "PNG")
        slices.append(str(out.relative_to(settings.app_data_root)))
        y += slice_h
        idx += 1

    return slices


def generate_segment_prompts(
    base_topic: str,
    segment_count: int,
    variant_composition: str,
) -> list[str]:
    """
    为每个段落生成带段序号的提示词后缀，使各段在内容上递进。
    """
    ordinals = [
        "introduction and overview",
        "key mechanism and cause",
        "symptoms and warning signs",
        "prevention and management",
        "treatment and recovery",
        "summary and call to action",
        "additional resources",
        "FAQ and common myths",
    ]

    prompts = []
    for i in range(segment_count):
        ordinal = ordinals[i] if i < len(ordinals) else f"part {i + 1}"
        suffix = f"segment {i + 1} of {segment_count}, {ordinal}, {variant_composition}"
        prompts.append(suffix)
    return prompts


async def generate_long_image(
    segment_rel_paths: list[str],
    variant_id: str,
    output_width: int = 1080,
) -> dict[str, Any]:
    """
    长图生成入口：拼接 + 可选微信切片。

    Parameters
    ----------
    segment_rel_paths : list[str]
        已生成的各段图像路径
    variant_id : str
        工作流变体 ID（F-1/F-2/F-3）
    output_width : int
        输出宽度

    Returns
    -------
    dict
        {
            "stitched_path": str,
            "stitched_url": str,
            "slices": [{"path": str, "serve_url": str}],  # F-2 才有
            "segment_count": int,
        }
    """
    w = WECHAT_OUTPUT_WIDTH if variant_id == "F-2" else output_width
    stitched = stitch_segments(segment_rel_paths, output_width=w)

    result: dict[str, Any] = {
        "stitched_path": stitched,
        "stitched_url": f"/api/v1/imagegen/serve?path={stitched}",
        "slices": [],
        "segment_count": len(segment_rel_paths),
    }

    if variant_id == "F-2":
        slice_paths = slice_for_wechat(stitched)
        result["slices"] = [
            {"path": sp, "serve_url": f"/api/v1/imagegen/serve?path={sp}"}
            for sp in slice_paths
        ]

    return result

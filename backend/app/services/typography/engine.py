"""
排版叠字合成引擎。
接收底图 + 文字内容 + 场景模板，输出带文字的成品图。
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.services.typography.fonts import get_font
from app.services.typography.templates import SceneLayout, TextZone, get_layout

_log = logging.getLogger(__name__)


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, alpha)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
               max_width: int, max_lines: int) -> list[str]:
    """
    对中英文混排文本进行自动换行。
    CJK 字符可在任意位置断行；英文在空格处断行。
    """
    if not text:
        return []

    lines: list[str] = []
    current = ""

    for char in text:
        test = current + char
        try:
            bbox = font.getbbox(test)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(test) * 14
        if w > max_width and current:
            lines.append(current)
            current = char
            if len(lines) >= max_lines:
                break
        else:
            current = test

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines[-1]:
            lines[-1] = lines[-1][:-1] + "…"

    return lines


def _draw_zone(
    img: Image.Image,
    zone: TextZone,
    text: str,
) -> None:
    if not text or not text.strip():
        return

    w, h = img.size
    x1 = int(w * zone.left)
    y1 = int(h * zone.top)
    x2 = int(w * zone.right)
    y2 = int(h * zone.bottom)

    zone_w = x2 - x1
    zone_h = y2 - y1
    if zone_w <= 0 or zone_h <= 0:
        return

    font_size = max(12, int(h * zone.font_size_ratio))
    font = get_font(font_size, bold=zone.bold)

    padding_x = int(zone_w * 0.04)
    inner_w = zone_w - padding_x * 2
    if inner_w <= 0:
        inner_w = zone_w

    lines = _wrap_text(text.strip(), font, inner_w, zone.max_lines)
    if not lines:
        return

    try:
        sample_bbox = font.getbbox("国Ag")
        line_h = sample_bbox[3] - sample_bbox[1]
    except Exception:
        line_h = font_size
    total_text_h = int(line_h * zone.line_spacing * len(lines))

    actual_h = max(zone_h, total_text_h + padding_x * 2)
    actual_y1 = y1

    if zone.bg_opacity > 0:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_bg = ImageDraw.Draw(overlay)
        bg_rgba = _hex_to_rgba(zone.bg_color, int(255 * zone.bg_opacity))
        radius = min(8, zone_w // 30, actual_h // 6)
        draw_bg.rounded_rectangle(
            [x1, actual_y1, x2, actual_y1 + actual_h],
            radius=radius,
            fill=bg_rgba,
        )
        img.paste(Image.alpha_composite(
            img.convert("RGBA"),
            overlay,
        ), (0, 0))
        if img.mode != "RGBA":
            pass

    draw = ImageDraw.Draw(img)
    text_color = _hex_to_rgba(zone.color)[:3]
    step = int(line_h * zone.line_spacing)
    text_block_start = actual_y1 + (actual_h - total_text_h) // 2

    for i, line in enumerate(lines):
        ly = text_block_start + i * step
        try:
            bbox = font.getbbox(line)
            lw = bbox[2] - bbox[0]
        except Exception:
            lw = len(line) * font_size

        if zone.align == "center":
            lx = x1 + (zone_w - lw) // 2
        elif zone.align == "right":
            lx = x2 - padding_x - lw
        else:
            lx = x1 + padding_x

        draw.text((lx, ly), line, fill=text_color, font=font)


def compose_image(
    base_image_path: str,
    scene_id: str,
    texts: dict[str, str],
    overrides: dict[str, Any] | None = None,
) -> str:
    """
    在底图上叠加文字，返回合成图的 medcomm-image:// 相对路径。

    Parameters
    ----------
    base_image_path : str
        底图相对路径（相对于 app_data_root），即 medcomm-image:// 去掉协议头
    scene_id : str
        场景 ID，对应 templates.py 中的布局
    texts : dict
        文字内容，key 对应 zone name（title / subtitle / body / footer）
    overrides : dict, optional
        覆盖参数（预留）
    """
    layout = get_layout(scene_id)
    if not layout:
        raise ValueError(f"未知场景: {scene_id}")

    base_full = Path(settings.app_data_root) / base_image_path
    if not base_full.is_file():
        raise FileNotFoundError(f"底图不存在: {base_full}")

    img = Image.open(base_full).convert("RGBA")

    for zone in layout.zones:
        text = texts.get(zone.name, "")
        if text:
            _draw_zone(img, zone, text)

    output = img.convert("RGB")

    now = datetime.utcnow()
    subdir = f"images/{now.year}/{now.month:02d}"
    out_dir = Path(settings.app_data_root) / subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    h = hashlib.sha256(base_image_path.encode() + str(texts).encode()).hexdigest()[:10]
    fn = f"composed_{scene_id}_{h}.png"
    out_path = out_dir / fn
    output.save(out_path, "PNG", quality=95)

    return str(out_path.relative_to(settings.app_data_root))

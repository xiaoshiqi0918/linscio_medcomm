"""
字体发现与管理。
优先级：MEDPIC_FONT_PATH 环境变量 → 常见系统中文字体 → Pillow 默认。
"""
from __future__ import annotations

import os
import platform
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

_SYSTEM_FONT_CANDIDATES: list[str] = []

_sys = platform.system()
if _sys == "Darwin":
    _SYSTEM_FONT_CANDIDATES = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
elif _sys == "Windows":
    _win = os.environ.get("WINDIR", r"C:\Windows")
    _SYSTEM_FONT_CANDIDATES = [
        _win + r"\Fonts\msyh.ttc",
        _win + r"\Fonts\msyhbd.ttc",
        _win + r"\Fonts\simhei.ttf",
        _win + r"\Fonts\simsun.ttc",
    ]
else:
    _SYSTEM_FONT_CANDIDATES = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    ]

_BOLD_CANDIDATES_DARWIN = [
    "/System/Library/Fonts/PingFang.ttc",
]
_win_dir = os.environ.get("WINDIR", r"C:\Windows")
_BOLD_CANDIDATES_WINDOWS = [
    _win_dir + r"\Fonts\msyhbd.ttc",
    _win_dir + r"\Fonts\simhei.ttf",
]


@lru_cache(maxsize=1)
def _find_system_font() -> str | None:
    env_path = os.environ.get("MEDPIC_FONT_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path
    for p in _SYSTEM_FONT_CANDIDATES:
        if Path(p).is_file():
            return p
    return None


@lru_cache(maxsize=1)
def _find_bold_font() -> str | None:
    env_path = os.environ.get("MEDPIC_BOLD_FONT_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path
    candidates = _BOLD_CANDIDATES_DARWIN if _sys == "Darwin" else _BOLD_CANDIDATES_WINDOWS
    for p in candidates:
        if Path(p).is_file():
            return p
    return _find_system_font()


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _find_bold_font() if bold else _find_system_font()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def has_cjk_font() -> bool:
    return _find_system_font() is not None

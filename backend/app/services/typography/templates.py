"""
场景排版模板定义。

每个模板定义若干文字区域(Zone)，使用相对坐标（0-1 比例于图片宽高），
引擎根据这些区域完成文字渲染。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextZone:
    """一个文字放置区域"""
    name: str
    left: float
    top: float
    right: float
    bottom: float
    font_size_ratio: float  # 相对于图片高度
    bold: bool = False
    color: str = "#FFFFFF"
    align: str = "center"  # left / center / right
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    max_lines: int = 3
    line_spacing: float = 1.4


@dataclass
class SceneLayout:
    """一个场景的完整排版定义"""
    scene_id: str
    zones: list[TextZone] = field(default_factory=list)


SCENE_LAYOUTS: dict[str, SceneLayout] = {
    "article": SceneLayout(
        scene_id="article",
        zones=[
            TextZone(
                name="title",
                left=0.05, top=0.78, right=0.95, bottom=0.92,
                font_size_ratio=0.04, bold=True,
                color="#FFFFFF", align="center",
                bg_color="#000000", bg_opacity=0.55,
                max_lines=2,
            ),
            TextZone(
                name="subtitle",
                left=0.08, top=0.92, right=0.92, bottom=0.98,
                font_size_ratio=0.022,
                color="#E0E0E0", align="center",
                bg_color="#000000", bg_opacity=0.40,
                max_lines=1,
            ),
        ],
    ),

    "comic": SceneLayout(
        scene_id="comic",
        zones=[
            TextZone(
                name="title",
                left=0.03, top=0.02, right=0.97, bottom=0.12,
                font_size_ratio=0.05, bold=True,
                color="#333333", align="center",
                bg_color="#FFFFFF", bg_opacity=0.85,
                max_lines=2,
            ),
            TextZone(
                name="subtitle",
                left=0.05, top=0.88, right=0.95, bottom=0.97,
                font_size_ratio=0.025,
                color="#555555", align="center",
                bg_color="#FFFFFF", bg_opacity=0.75,
                max_lines=2,
            ),
        ],
    ),

    "card": SceneLayout(
        scene_id="card",
        zones=[
            TextZone(
                name="title",
                left=0.06, top=0.04, right=0.94, bottom=0.16,
                font_size_ratio=0.05, bold=True,
                color="#FFFFFF", align="center",
                bg_color="#1A73E8", bg_opacity=0.80,
                max_lines=2,
            ),
            TextZone(
                name="body",
                left=0.06, top=0.76, right=0.94, bottom=0.94,
                font_size_ratio=0.026,
                color="#FFFFFF", align="left",
                bg_color="#000000", bg_opacity=0.50,
                max_lines=4, line_spacing=1.5,
            ),
            TextZone(
                name="footer",
                left=0.06, top=0.95, right=0.94, bottom=0.99,
                font_size_ratio=0.018,
                color="#CCCCCC", align="right",
                bg_color="#000000", bg_opacity=0.30,
                max_lines=1,
            ),
        ],
    ),

    "poster": SceneLayout(
        scene_id="poster",
        zones=[
            TextZone(
                name="title",
                left=0.06, top=0.04, right=0.94, bottom=0.14,
                font_size_ratio=0.045, bold=True,
                color="#FFFFFF", align="center",
                bg_color="#000000", bg_opacity=0.50,
                max_lines=2,
            ),
            TextZone(
                name="subtitle",
                left=0.08, top=0.14, right=0.92, bottom=0.20,
                font_size_ratio=0.025,
                color="#E8E8E8", align="center",
                bg_color="#000000", bg_opacity=0.35,
                max_lines=2,
            ),
            TextZone(
                name="footer",
                left=0.06, top=0.93, right=0.94, bottom=0.98,
                font_size_ratio=0.018,
                color="#FFFFFF", align="center",
                bg_color="#000000", bg_opacity=0.45,
                max_lines=1,
            ),
        ],
    ),

    "picturebook": SceneLayout(
        scene_id="picturebook",
        zones=[
            TextZone(
                name="title",
                left=0.08, top=0.82, right=0.92, bottom=0.93,
                font_size_ratio=0.04, bold=True,
                color="#4A3728", align="center",
                bg_color="#FFFBF0", bg_opacity=0.80,
                max_lines=2,
            ),
            TextZone(
                name="subtitle",
                left=0.10, top=0.93, right=0.90, bottom=0.98,
                font_size_ratio=0.022,
                color="#7A6650", align="center",
                bg_color="#FFFBF0", bg_opacity=0.65,
                max_lines=1,
            ),
        ],
    ),

    "longimage": SceneLayout(
        scene_id="longimage",
        zones=[
            TextZone(
                name="title",
                left=0.05, top=0.03, right=0.95, bottom=0.13,
                font_size_ratio=0.045, bold=True,
                color="#FFFFFF", align="center",
                bg_color="#2563EB", bg_opacity=0.85,
                max_lines=2,
            ),
            TextZone(
                name="body",
                left=0.06, top=0.80, right=0.94, bottom=0.95,
                font_size_ratio=0.024,
                color="#FFFFFF", align="left",
                bg_color="#000000", bg_opacity=0.50,
                max_lines=4, line_spacing=1.5,
            ),
        ],
    ),

    "ppt": SceneLayout(
        scene_id="ppt",
        zones=[
            TextZone(
                name="title",
                left=0.03, top=0.06, right=0.50, bottom=0.22,
                font_size_ratio=0.055, bold=True,
                color="#FFFFFF", align="left",
                bg_color="#000000", bg_opacity=0.55,
                max_lines=2,
            ),
            TextZone(
                name="subtitle",
                left=0.03, top=0.22, right=0.50, bottom=0.34,
                font_size_ratio=0.028,
                color="#E0E0E0", align="left",
                bg_color="#000000", bg_opacity=0.40,
                max_lines=2,
            ),
            TextZone(
                name="footer",
                left=0.03, top=0.88, right=0.97, bottom=0.96,
                font_size_ratio=0.022,
                color="#CCCCCC", align="right",
                bg_color="#000000", bg_opacity=0.30,
                max_lines=1,
            ),
        ],
    ),
}


def get_layout(scene_id: str) -> SceneLayout | None:
    return SCENE_LAYOUTS.get(scene_id)


def list_layouts() -> list[dict]:
    out = []
    for sid, layout in SCENE_LAYOUTS.items():
        out.append({
            "scene_id": sid,
            "zones": [z.name for z in layout.zones],
        })
    return out

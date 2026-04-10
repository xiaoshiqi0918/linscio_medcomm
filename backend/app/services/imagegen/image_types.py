"""
图像类型与风格体系（v5.0）
"""
# 图像类型 × 适用形式
IMAGE_TYPES = [
    ("anatomy", "解剖示意图", "article,patient_handbook"),
    ("pathology", "病理过程图", "article,research_read"),
    ("flowchart", "治疗流程图", "article,patient_handbook"),
    ("infographic", "信息图", "card_series,long_image"),
    ("comparison", "对比图", "article,debunk"),
    ("symptom", "症状示意图", "patient_handbook,article"),
    ("prevention", "预防指导图", "article,card_series"),
    ("poster", "科普海报", "poster"),
    ("comic_panel", "漫画格", "comic_strip"),
    ("card_illustration", "卡片配图", "card_series"),
    ("picture_book_page", "绘本插图", "picture_book"),
    ("storyboard_frame", "分镜画面", "storyboard"),
]

# 形式 → 默认图像类型
FORMAT_DEFAULT_IMAGE_TYPE = {
    "article": "anatomy",
    "story": "anatomy",
    "debunk": "comparison",
    "qa_article": "anatomy",
    "research_read": "pathology",
    "comic_strip": "comic_panel",
    "card_series": "card_illustration",
    "poster": "poster",
    "picture_book": "picture_book_page",
    "long_image": "infographic",
    "patient_handbook": "anatomy",
    "quiz_article": "anatomy",
    "storyboard": "storyboard_frame",
}

# 图像风格 × 适用
IMAGE_STYLES = {
    "medical_illustration": "医学插画",
    "flat_design": "简洁扁平",
    "realistic": "写实风格",
    "cartoon": "卡通友好",
    "data_viz": "数据可视化",
    "comic": "漫画风",
    "picture_book": "儿童绘本风",
}

# 形式 → 默认风格（与 format_router FORMAT_CONFIG.image_style 对齐）
FORMAT_DEFAULT_STYLE = {
    "comic_strip": "comic",
    "card_series": "flat_design",
    "poster": "medical_illustration",
    "picture_book": "picture_book",
}


# 需要结构化布局 / 文字标注 / 数据可视化的图像类型 → SD/ComfyUI 效果差，应优先路由到 DALL·E 3 等 API
STRUCTURED_IMAGE_TYPES = {"comparison", "infographic", "flowchart", "data_viz"}

# SD/ComfyUI 擅长的艺术化图像类型
ARTISTIC_IMAGE_TYPES = {
    "anatomy", "pathology", "symptom", "prevention",
    "comic_panel", "picture_book_page", "storyboard_frame",
    "card_illustration", "poster",
}


def is_structured_type(image_type: str) -> bool:
    """该图像类型是否需要结构化布局（图表/标注/对比），SD 效果差"""
    return image_type in STRUCTURED_IMAGE_TYPES


_STRUCTURED_KEYWORDS_ZH = (
    "对比图", "对比", "流程图", "信息图", "数据图", "图表", "柱状图", "饼图",
    "折线图", "曲线图", "统计", "数据可视化", "表格", "坐标", "时间轴",
)
_STRUCTURED_KEYWORDS_EN = (
    "comparison", "infographic", "flowchart", "chart", "graph", "diagram",
    "data viz", "statistics", "bar chart", "pie chart", "timeline",
    "labeled axes", "versus", "vs.", "side-by-side",
)


def _description_looks_structured(description: str | None, en_description: str | None = None) -> bool:
    """基于描述文本判断是否为结构化/图表类内容"""
    if description:
        dl = description.lower()
        if any(kw in dl for kw in _STRUCTURED_KEYWORDS_ZH):
            return True
    if en_description:
        el = en_description.lower()
        if any(kw in el for kw in _STRUCTURED_KEYWORDS_EN):
            return True
    return False


def recommend_tool(
    image_type: str,
    style: str | None = None,
    description: str | None = None,
    en_description: str | None = None,
) -> dict:
    """根据图像类型、风格、描述文本综合推荐绘图工具。
    返回 {"tool": "medpic"|"artgen"|"api", "tool_label": "...", "reason": "..."}
    - medpic:  ComfyUI / MedPic 模块（擅长插画、漫画、解剖图等艺术类）
    - artgen:  创意绘图（Midjourney 驱动，擅长高品质视觉对比/信息图/概念图）
    - api:     通用图像生成（DALL·E 3 等 API，通用全能型）
    """
    is_struct = (
        image_type in STRUCTURED_IMAGE_TYPES
        or style == "data_viz"
        or _description_looks_structured(description, en_description)
    )
    if is_struct:
        return {
            "tool": "artgen",
            "tool_label": "创意绘图",
            "reason": "该类型含视觉对比/图表/信息图，创意绘图效果更佳",
        }
    return {
        "tool": "medpic",
        "tool_label": "MedPic 绘图",
        "reason": "该类型为艺术类插图，ComfyUI/MedPic 效果更佳",
    }


def get_image_type_for_format(content_format: str, image_type: str | None = None) -> str:
    """根据形式与可选 image_type 返回最终类型"""
    if image_type:
        return image_type
    return FORMAT_DEFAULT_IMAGE_TYPE.get(content_format, "anatomy")


def get_style_for_format(content_format: str, style: str | None = None) -> str:
    """根据形式与可选 style 返回最终风格"""
    if style:
        return style
    return FORMAT_DEFAULT_STYLE.get(content_format, "medical_illustration")

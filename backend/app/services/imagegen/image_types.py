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

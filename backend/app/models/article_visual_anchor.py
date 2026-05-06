"""文章视觉锚点模型 — 全文角色卡 + 风格锁 + Seed 锁 + 锚点参考图

用于保证一篇文章中所有 AI 生成配图的人物外貌、画风、配色一致性。
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, func

from app.models import Base


class ArticleVisualAnchor(Base):
    """每篇文章一份视觉锚点配置（一对一）。"""
    __tablename__ = "article_visual_anchors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(
        Integer, ForeignKey("articles.id"), nullable=False, unique=True, index=True
    )

    # 角色卡：[{id, role, description, importance}]
    # importance 用于 prompt 长度受限时决定先注入谁
    characters = Column(JSON, nullable=True)

    # 风格锁：{color_palette, lighting, art_style_extra, style_preset_id}
    style_lock = Column(JSON, nullable=True)

    # Seed Lock：即梦/Flux/SD/MJ 支持
    base_seed = Column(Integer, nullable=True)

    # 锚点参考图（i2i 类 provider 自动启用）
    anchor_image_path = Column(String(500), nullable=True)
    # auto_first / manual_upload / manual_pick / disabled
    anchor_source = Column(String(20), nullable=True, default="auto_first")

    auto_extracted_at = Column(DateTime, nullable=True)
    last_modified_by = Column(String(20), nullable=True)  # ai / user

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

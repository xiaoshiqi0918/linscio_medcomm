"""文章配图槽位模型 — 每章节的画意、提示词与图片管理"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func

from app.models import Base


class ArticleImageSlot(Base):
    """配图槽位 — 承载画意、双语 prompt、风格预设与上传图片"""
    __tablename__ = "article_image_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("article_sections.id"), nullable=True, index=True)
    order_num = Column(Integer, default=1)

    intent_text = Column(Text, nullable=True)
    aspect_ratio = Column(String(10), nullable=True)  # 16:9 / 1:1 / 3:4
    style_preset_id = Column(Integer, nullable=True)

    prompt_zh = Column(Text, nullable=True)
    prompt_en = Column(Text, nullable=True)
    negative_words = Column(Text, nullable=True)

    image_path = Column(String(500), nullable=True)
    image_status = Column(String(20), default="empty")  # empty / prompt_ready / uploaded / ai_generated
    image_provider = Column(String(30), nullable=True)  # dalle3 / midjourney / comfyui / wanx / siliconflow / wenxin / pollinations

    user_adjustments = Column(JSON, nullable=True)
    prompt_version = Column(Integer, default=0)
    style_preset_version = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

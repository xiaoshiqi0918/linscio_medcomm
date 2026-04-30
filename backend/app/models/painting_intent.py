"""画意范例、风格预设与负向词库模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, func

from app.models import Base


class StylePreset(Base):
    """风格预设 — 每档绑定固定的 prompt 结构模板与配套负向词"""
    __tablename__ = "style_presets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    prompt_template_zh = Column(JSON, nullable=True)
    prompt_template_en = Column(JSON, nullable=True)
    negative_words = Column(JSON, nullable=True)
    quality_tags_zh = Column(Text, nullable=True)
    quality_tags_en = Column(Text, nullable=True)
    medium_zh = Column(String(100), nullable=True)
    medium_en = Column(String(100), nullable=True)

    default_composition = Column(String(100), nullable=True)
    default_lighting = Column(String(100), nullable=True)
    default_color = Column(String(100), nullable=True)

    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PaintingIntentExample(Base):
    """画意范例 — 按科普选题×风格预置供用户一键套用"""
    __tablename__ = "painting_intent_examples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_category = Column(String(50), nullable=False, index=True)
    style_preset_id = Column(Integer, nullable=True, index=True)
    preset_version = Column(Integer, nullable=True)
    intent_text = Column(Text, nullable=False)
    scene_description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())


class NegativeWordSet(Base):
    """负向词库 — 按类别和作用域分层挂载"""
    __tablename__ = "negative_word_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(30), nullable=False)  # compliance / aesthetic / scientific / brand
    scope = Column(String(20), nullable=False, default="global")  # global / topic
    topic_category = Column(String(50), nullable=True)
    words_zh = Column(JSON, nullable=True)
    words_en = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

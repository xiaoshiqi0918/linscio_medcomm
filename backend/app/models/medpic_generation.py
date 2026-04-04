"""MedPic 生成记录模型 — 追踪绘图生成历史"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON, func

from app.models import Base


class MedPicGeneration(Base):
    __tablename__ = "medpic_generations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, default=1)

    variant_id = Column(String(30), nullable=True)
    scene = Column(String(30))
    style = Column(String(50))
    hardware_tier = Column(String(20))

    topic = Column(Text)
    specialty = Column(String(50), nullable=True)
    positive_prompt = Column(Text)
    negative_prompt = Column(Text, nullable=True)

    seed = Column(Integer, nullable=True)
    seed_mode = Column(String(20), nullable=True)
    model_id = Column(String(50), nullable=True)
    loras = Column(JSON, nullable=True)

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    output_width = Column(Integer, nullable=True)
    output_height = Column(Integer, nullable=True)

    base_image_path = Column(String(500))
    composed_image_path = Column(String(500), nullable=True)
    upscaled_image_path = Column(String(500), nullable=True)

    ipadapter_weight = Column(Float, nullable=True)
    character_preset = Column(String(50), nullable=True)
    reference_image_path = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=func.now())

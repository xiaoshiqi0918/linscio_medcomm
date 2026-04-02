"""生成图像模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
from app.models import Base


class GeneratedImage(Base):
    __tablename__ = "generated_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    section_id = Column(Integer, ForeignKey("article_sections.id"), nullable=True)
    content_format = Column(String(30), nullable=True)
    panel_index = Column(Integer, nullable=True)
    file_path = Column(String(500))
    prompt = Column(Text)
    provider = Column(String(30))
    style = Column(String(30))
    image_type = Column(String(30))
    created_at = Column(DateTime, default=func.now())

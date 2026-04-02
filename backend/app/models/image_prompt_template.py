"""图像提示词模板 - 按形式/风格提供 prompt 模板"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.models import Base


class ImagePromptTemplate(Base):
    __tablename__ = "image_prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200))
    content_format = Column(String(30))
    style = Column(String(30))
    prompt_template = Column(Text)
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

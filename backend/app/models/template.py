"""内容模板模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, func
from app.models import Base


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200))
    specialty = Column(String(50))
    platform = Column(String(30))
    content_format = Column(String(30))
    article_type = Column(String(30))
    structure = Column(JSON)
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

"""Few-shot 示例模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
from app.models import Base


class WritingExample(Base):
    __tablename__ = "writing_examples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_format = Column(String(30))
    section_type = Column(String(50))
    target_audience = Column(String(30))
    platform = Column(String(30))
    specialty = Column(String(50))
    content_json = Column(Text)
    content_text = Column(Text)
    analysis_text = Column(Text)  # 【分析】段落，供 prompt 注入
    source_doc = Column(String(200))  # 来源文档标识（内部归档，不对外展示）
    source = Column(String(20), default='user')  # user=用户自建, package=学科包导入
    medical_reviewed = Column(Integer, default=0)  # 医学内容是否经医生审核 0=否 1=是
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

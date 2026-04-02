"""发布记录模型"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from app.models import Base


class PublishRecord(Base):
    __tablename__ = "publish_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    article_content_id = Column(Integer, ForeignKey("article_contents.id"), nullable=True)
    platform = Column(String(30))
    publish_url = Column(String(500))
    read_count = Column(Integer, nullable=True)  # 手动录入
    created_at = Column(DateTime, default=func.now())

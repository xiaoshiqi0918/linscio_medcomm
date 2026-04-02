"""文章级本地快照（整篇多章节一点备份，与章节滚动版本互补）"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func

from app.models import Base


class ArticleSnapshot(Base):
    __tablename__ = "article_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    label = Column(String(200), default="")
    note = Column(Text, default="")
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

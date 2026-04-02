"""个人语料：写作偏好、禁用词、_capture 积累，注入生成提示词"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func

from app.models import Base


class PersonalCorpusEntry(Base):
    __tablename__ = "personal_corpus_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1, index=True)
    # avoid=避免使用 | prefer=倾向表达（anchor→content）| note=自由备忘
    kind = Column(String(20), nullable=False, default="note")
    anchor = Column(String(500), default="")
    content = Column(Text, default="")
    # manual=手输 | capture=从编辑/对比中收录
    source = Column(String(20), default="manual")
    enabled = Column(Boolean, default=True)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

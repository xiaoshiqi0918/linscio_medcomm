"""润色会话模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, func
from app.models import Base


class PolishSession(Base):
    __tablename__ = "polish_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("article_sections.id"))
    polish_type = Column(String(30))  # language / platform / level
    status = Column(String(20), default="active")  # active / cancelled / done
    created_at = Column(DateTime, default=func.now())


class PolishChange(Base):
    __tablename__ = "polish_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("polish_sessions.id"))
    original_text = Column(Text)
    suggested_text = Column(Text)
    status = Column(String(20), default="pending")  # pending / accepted / rejected

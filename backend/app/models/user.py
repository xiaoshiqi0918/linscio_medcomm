"""用户模型 - 单用户桌面工具"""
from sqlalchemy import Column, Integer, String, DateTime, func
from app.models import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255))
    display_name = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

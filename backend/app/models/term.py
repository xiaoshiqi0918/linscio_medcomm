"""医学术语模型"""
from sqlalchemy import Column, Integer, String, Text
from app.models import Base


class MedicalTerm(Base):
    __tablename__ = "medical_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(100))
    abbreviation = Column(String(30))  # 缩写，student/professional 用
    layman_explain = Column(Text)
    analogy = Column(Text)
    specialty = Column(String(50))  # 专科，可选过滤
    audience_level = Column(String(20))  # public / patient / student / professional
    source = Column(String(20), default='user')  # user=用户自建, package=学科包导入

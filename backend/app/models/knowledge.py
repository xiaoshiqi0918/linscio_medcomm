"""知识库模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, func
from app.models import Base


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1)
    name = Column(String(255))
    file_path = Column(String(500))
    status = Column(String(20), default="pending")  # pending / indexing / done / failed
    is_system = Column(Boolean, default=False)
    specialty = Column(String(50), nullable=True, index=True)  # 学科包来源标记
    source = Column(String(20), default="user")  # user / system / package
    created_at = Column(DateTime, default=func.now())


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("knowledge_docs.id"))
    chunk_index = Column(Integer)
    content = Column(Text)
    specialty = Column(String(50), nullable=True, index=True)  # 冗余字段，加速检索过滤
    created_at = Column(DateTime, default=func.now())

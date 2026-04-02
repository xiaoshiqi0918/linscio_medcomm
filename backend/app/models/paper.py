"""文献分块模型（关联 literature_papers，供 RAG 检索）
主表为 LiteraturePaper，见 app.models.literature
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, LargeBinary
from app.models import Base


class PaperChunk(Base):
    """文献分块（向量化 chunk，供 RAG 使用）"""
    __tablename__ = "paper_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("literature_papers.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(String(30))  # background / methods / results / conclusion 等
    chunk_text = Column(Text, nullable=False)
    page_start = Column(Integer)
    page_end = Column(Integer)
    section = Column(String(100), default="")
    embedding = Column(LargeBinary)
    created_at = Column(DateTime, default=func.now())

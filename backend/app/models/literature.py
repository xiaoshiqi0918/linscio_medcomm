"""文献支撑库 v2.0 模型
literature_papers / literature_tags / literature_collections / literature_annotations 等
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean,
)
from sqlalchemy.orm import relationship

from app.models import Base


class LiteratureCollection(Base):
    """集合/文件夹（支持嵌套，最多3层）"""
    __tablename__ = "literature_collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey("literature_collections.id", ondelete="CASCADE"))
    color = Column(String(20), default="#185FA5")
    icon = Column(String(30), default="folder")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())


class LiteratureTag(Base):
    """标签"""
    __tablename__ = "literature_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    color = Column(String(20), default="#1D9E75")
    created_at = Column(DateTime, default=func.now())


class LiteraturePaper(Base):
    """文献主表"""
    __tablename__ = "literature_papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1)

    # 核心元数据
    title = Column(Text, nullable=False)
    authors = Column(Text, nullable=False, default="[]")  # JSON [{"name":"","affil":""}]
    journal = Column(Text, default="")
    year = Column(Integer)
    volume = Column(String(50), default="")
    issue = Column(String(50), default="")
    pages = Column(String(50), default="")
    publisher = Column(Text, default="")

    # 唯一标识
    doi = Column(String(200), unique=True)
    pmid = Column(String(50), unique=True)
    arxiv_id = Column(String(50))
    url = Column(Text, default="")

    # 内容摘要
    abstract = Column(Text, default="")
    keywords = Column(Text, default="[]")  # JSON array
    language = Column(String(10), default="zh")

    # 用户数据
    user_notes = Column(Text, default="")
    user_abstract = Column(Text, default="")
    read_status = Column(String(20), default="unread")  # unread/reading/read
    rating = Column(Integer, default=0)
    cite_count = Column(Integer, default=0)

    # 分类
    collection_id = Column(Integer, ForeignKey("literature_collections.id", ondelete="SET NULL"))

    # 文件
    pdf_path = Column(Text)
    pdf_size = Column(Integer, default=0)
    pdf_indexed = Column(Integer, default=0)  # 是否已向量化
    # 全文可用性：full=正文已入 paper_chunks；pending=待 PDF 解析或 OA 拉取；no_fulltext=需用户补 PDF
    fulltext_status = Column(String(32), default="pending", server_default="pending")

    # 来源追踪
    import_source = Column(String(30), default="manual")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime)

    # 软删除
    deleted_at = Column(DateTime)
    deleted_at_ts = Column(Integer)


class LiteraturePaperTag(Base):
    """文献-标签多对多"""
    __tablename__ = "literature_paper_tags"

    paper_id = Column(Integer, ForeignKey("literature_papers.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("literature_tags.id", ondelete="CASCADE"), primary_key=True)


class LiteratureAttachment(Base):
    """附件（PDF 之外的补充材料）"""
    __tablename__ = "literature_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("literature_papers.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(20), default="pdf")
    file_size = Column(Integer, default=0)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=func.now())


class LiteratureAnnotation(Base):
    """PDF 标注（高亮/批注等）"""
    __tablename__ = "literature_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("literature_papers.id", ondelete="CASCADE"), nullable=False)
    annotation_type = Column(String(30), nullable=False)  # highlight/note/underline/strikethrough
    page_number = Column(Integer, nullable=False)
    rect = Column(Text, nullable=False)  # JSON {x1,y1,x2,y2}
    color = Column(String(20), default="#FFD700")
    content = Column(Text, default="")
    selected_text = Column(Text, default="")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime)

"""文章与章节模型 - 支持 content_format × platform 双维度"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, func
from app.models import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1)
    title = Column(String(500))
    topic = Column(String(200))
    specialty = Column(String(50))
    target_audience = Column(String(30))
    reading_level = Column(String(20))
    platform = Column(String(30))
    content_format = Column(String(30))
    status = Column(String(20), default="draft")
    current_stage = Column(String(20))
    image_stage = Column(String(20), default="pending")
    default_model = Column(String(50))
    target_word_count = Column(Integer, nullable=True)
    word_count = Column(Integer, default=0)
    visual_continuity_prompt = Column(Text, nullable=True)
    image_series_seed_base = Column(Integer, nullable=True)
    skip_sections = Column(JSON, nullable=True)
    analysis_report = Column(JSON, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # 软删除
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ArticleSection(Base):
    __tablename__ = "article_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    section_type = Column(String(50))
    title = Column(String(200))
    order_num = Column(Integer, default=0)
    status = Column(String(20), default="pending")
    format_meta = Column(JSON)
    image_suggestions = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ArticleContent(Base):
    __tablename__ = "article_contents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), index=True)
    section_id = Column(Integer, ForeignKey("article_sections.id"), index=True, nullable=True)
    content_json = Column(Text)
    content_html = Column(Text)
    content_text = Column(Text)
    version = Column(Integer, default=1)
    version_type = Column(String(20))
    platform = Column(String(30))
    is_current = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    word_count = Column(Integer)
    examples_used = Column(JSON)
    verify_report = Column(JSON)
    created_at = Column(DateTime, default=func.now())


class ArticleLiteratureBinding(Base):
    """文章/章节与文献绑定，用于 RAG 优先检索与导出参考文献"""
    __tablename__ = "article_literature_bindings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("article_sections.id"), nullable=True, index=True)
    paper_id = Column(Integer, ForeignKey("literature_papers.id"), nullable=False, index=True)
    priority = Column(Integer, default=100)
    created_at = Column(DateTime, default=func.now())


class ArticleExternalReference(Base):
    """文章/章节外部引用（无需先入库）"""
    __tablename__ = "article_external_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("article_sections.id"), nullable=True, index=True)

    source = Column(String(30), nullable=False)       # pubmed/crossref/semantic_scholar/...
    source_id = Column(String(200), default="")       # pmid/doi/paperId 等
    doi = Column(String(200))
    pmid = Column(String(50))
    title = Column(Text, nullable=False)
    authors = Column(Text, default="[]")              # JSON [{"name","affil"}]
    journal = Column(Text, default="")
    year = Column(Integer)
    url = Column(Text, default="")
    abstract = Column(Text, default="")
    created_at = Column(DateTime, default=func.now())

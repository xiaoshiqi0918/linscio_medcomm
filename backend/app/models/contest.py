"""赛制包与赛事规则模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, func

from app.models import Base


class ContestPack(Base):
    """赛制包 — 运营维护的已知赛事配置"""
    __tablename__ = "contest_packs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    organizer = Column(String(200), nullable=True)
    level = Column(String(30), nullable=True)  # national / provincial / association
    source_url = Column(Text, nullable=True)
    source_note = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    word_limit = Column(Integer, nullable=True)
    word_count_includes = Column(JSON, nullable=True)  # e.g. {"title": false, "captions": false, "references": false}
    font = Column(String(100), nullable=True)
    file_format = Column(String(50), nullable=True)  # docx / pdf / docx+pdf
    naming_template = Column(String(500), nullable=True)
    deadline = Column(DateTime, nullable=True)
    ai_disclosure = Column(String(20), nullable=True)  # required / recommended / none
    image_format = Column(String(50), nullable=True)  # jpg / png
    layout_preference = Column(String(30), nullable=True)  # crop_fill / letterbox / auto_fit
    extra_rules = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class UserContestRule(Base):
    """用户保存的个人赛制配置（公告解析/手工填写后可复用）"""
    __tablename__ = "user_contest_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    rules = Column(JSON, nullable=False)
    source = Column(String(20), nullable=False, default="manual")  # parsed / manual
    is_active = Column(Boolean, default=True)
    submitted_as_public = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ContestRule(Base):
    """赛制规则明细 — 支持逐字段来源追踪"""
    __tablename__ = "contest_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_pack_id = Column(Integer, nullable=True, index=True)
    article_id = Column(Integer, nullable=True, index=True)
    rule_key = Column(String(100), nullable=False)
    rule_value = Column(Text, nullable=True)
    source = Column(String(20), nullable=False, default="manual")  # pack / parsed / manual
    confidence = Column(String(20), nullable=True)  # auto_detected / user_confirmed

    created_at = Column(DateTime, default=func.now())

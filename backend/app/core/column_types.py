"""
跨数据库 JSON 列类型
  PostgreSQL -> JSONB
  SQLite     -> JSON (存储为 TEXT，SQLAlchemy 自动序列化)
"""
from sqlalchemy import JSON
from app.core.config import is_desktop


def CompatJSON():
    if is_desktop():
        return JSON
    from sqlalchemy.dialects.postgresql import JSONB
    return JSONB


FlexJSON = CompatJSON()

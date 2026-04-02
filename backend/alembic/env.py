"""Alembic 环境配置 - 使用应用 config 与 ORM"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import _ensure_data_dir, settings
from app.models import Base
from app.models.user import User
from app.models.article import Article, ArticleSection, ArticleContent
from app.models.image import GeneratedImage
from app.models.image_prompt_template import ImagePromptTemplate
from app.models.template import ContentTemplate
from app.models.knowledge import KnowledgeDoc, KnowledgeChunk
from app.models.example import WritingExample
from app.models.term import MedicalTerm
from app.models.polish import PolishSession, PolishChange
from app.models.publish import PublishRecord
from app.models.paper import PaperChunk
from app.models.literature import LiteraturePaper
from app.models.specialty_package import SpecialtyPackage

# Alembic Config
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 使用应用数据库路径（同步 URL，Alembic 标准用法）
_ensure_data_dir()
db_url = f"sqlite:///{settings.db_path}"
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

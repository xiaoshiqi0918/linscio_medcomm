"""
数据库连接与分域写锁
SQLite WAL 模式 + 分域 asyncio.Lock
"""
import shutil
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text

from app.core.config import settings, _ensure_data_dir
from app.core.locks import get_domain_lock

# 初始化时确保目录存在
_ensure_data_dir()

# SQLite 异步连接 URL
DATABASE_URL = f"sqlite+aiosqlite:///{settings.db_path}"

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def backup_db_before_migration() -> str | None:
    """
    迁移前备份数据库，返回备份路径或 None
    若 db 不存在则不备份
    """
    db_path = Path(settings.db_path)
    if not db_path.exists():
        return None
    stamp = int(time.time())
    backup_path = f"{settings.db_path}.{stamp}.linscio-backup"
    shutil.copy2(settings.db_path, backup_path)
    return backup_path


async def init_db():
    """初始化数据库：备份（若存在）→ 启用 WAL → 创建表 → 种子用户"""
    from app.models import Base, User  # noqa: F401

    backup_db_before_migration()

    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)

        # 增量迁移：article_sections 增加 image_suggestions 列
        cols = (await conn.execute(text("PRAGMA table_info(article_sections)"))).fetchall()
        if not any(c[1] == "image_suggestions" for c in cols):
            await conn.execute(text("ALTER TABLE article_sections ADD COLUMN image_suggestions TEXT"))

    # 单用户：确保 user id=1 存在
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        r = await session.execute(select(User).where(User.id == 1))
        if r.scalar_one_or_none() is None:
            session.add(User(id=1, display_name="医生", email="user@local"))
            await session.commit()


def get_db_path() -> str:
    return settings.db_path


async def get_session():
    """获取异步会话（供路由依赖注入使用）"""
    async with AsyncSessionLocal() as session:
        yield session


def get_domain_session(domain: str):
    """
    获取带分域写锁的会话工厂
    写操作前需 acquire 对应 domain 的 lock
    """
    lock = get_domain_lock(domain)
    return AsyncSessionLocal, lock

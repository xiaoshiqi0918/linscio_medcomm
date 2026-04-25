"""
数据库引擎 — 双模式支持
  desktop: SQLite + aiosqlite（单文件，WAL 模式）
  saas:    PostgreSQL + asyncpg（连接池）
"""
import shutil
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.core.config import settings, is_desktop, _ensure_data_dir

_engine_kwargs: dict = {"echo": settings.debug}

if is_desktop():
    _ensure_data_dir()
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def backup_db_before_migration() -> str | None:
    """迁移前备份数据库（仅桌面端 SQLite）"""
    if not is_desktop():
        return None
    db_path = Path(settings.db_path)
    if not db_path.exists():
        return None
    stamp = int(time.time())
    backup_path = f"{settings.db_path}.{stamp}.linscio-backup"
    shutil.copy2(settings.db_path, backup_path)
    return backup_path


async def _sqlite_migrate_users(conn):
    """SQLite 增量迁移：给已有 users 表添加新列（不报错忽略已存在的列）"""
    new_columns = [
        ("phone", "VARCHAR(20)"),
        ("password_hash", "VARCHAR(255)"),
        ("is_banned", "BOOLEAN DEFAULT false"),
        ("last_login_at", "DATETIME"),
        ("credits", "NUMERIC(10,4) DEFAULT 0"),
        ("gift_credits", "NUMERIC(10,4) DEFAULT 30"),
        ("gift_credits_expire_at", "DATETIME"),
        ("promo_credits", "NUMERIC(10,4) DEFAULT 0"),
        ("promo_credits_expire_at", "DATETIME"),
        ("frozen_credits", "NUMERIC(10,4) DEFAULT 0"),
        ("free_generation_used", "BOOLEAN DEFAULT false"),
        ("referral_code", "VARCHAR(8)"),
        ("referred_by", "INTEGER"),
        ("total_recharged", "NUMERIC(10,4) DEFAULT 0"),
        ("total_consumed", "NUMERIC(10,4) DEFAULT 0"),
    ]
    for col_name, col_type in new_columns:
        try:
            await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass


async def init_db():
    """初始化数据库：备份 → WAL(SQLite) → 创建表 → 增量迁移 → 种子用户"""
    from app.models import Base, User  # noqa: F401

    backup_db_before_migration()

    async with engine.begin() as conn:
        if is_desktop():
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)

        if is_desktop():
            await _sqlite_migrate_users(conn)

    if is_desktop():
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


# 兼容 saas-backend 风格的别名
get_db = get_session


# 重新导出 get_domain_lock 保持向后兼容
def get_domain_lock(domain: str):
    from app.core.locks import get_domain_lock as _get_lock
    return _get_lock(domain)


def get_domain_session(domain: str):
    """获取带分域写锁的会话工厂"""
    lock = get_domain_lock(domain)
    return AsyncSessionLocal, lock

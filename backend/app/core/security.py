"""
安全工具 — JWT 签发/验证 + 密码哈希
两种部署模式统一使用（桌面端通过内存 stub 替代 Redis）。
"""
import logging
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.redis import redis_jwt

logger = logging.getLogger(__name__)

# ── 密码 ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── JWT 签名/验证密钥 ──────────────────────────────────

def _get_signing_key() -> str | bytes:
    if settings.jwt_algorithm == "RS256" and settings.jwt_private_key:
        return settings.jwt_private_key.replace("\\n", "\n").encode()
    return settings.jwt_secret


def _get_verify_key() -> str | bytes:
    if settings.jwt_algorithm == "RS256" and settings.jwt_public_key:
        return settings.jwt_public_key.replace("\\n", "\n").encode()
    return settings.jwt_secret


# ── JWT ─────────────────────────────────────────────────

def create_access_token(user_id: int, extra: dict[str, Any] | None = None) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_access_expire_seconds),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _get_signing_key(), algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_refresh_expire_seconds),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_signing_key(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        _get_verify_key(),
        algorithms=[settings.jwt_algorithm],
    )


# ── JWT 黑名单 ──────────────────────────────────────────

async def blacklist_token(token: str, expire_seconds: int | None = None) -> None:
    ttl = expire_seconds or settings.jwt_access_expire_seconds
    await redis_jwt.set(f"blacklist:{token}", "1", ex=ttl)


async def is_token_blacklisted(token: str) -> bool:
    return await redis_jwt.exists(f"blacklist:{token}") > 0

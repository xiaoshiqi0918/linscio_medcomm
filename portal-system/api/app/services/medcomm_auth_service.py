"""
LinScio MedComm v3 认证服务
- 支持 email/phone 双渠道（credential 统一字段）
- access_token：64 位 hex 随机串（软件用）
- session_token：JWT（门户 Web 用）
"""
import re
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from app.config import settings
from app.models.medcomm_models import (
    MedcommUser,
    MedcommUserLicense,
    MedcommSecurityEvent,
)
from app.services.auth_service import hash_password, verify_password


def generate_access_token() -> str:
    """生成 64 位 hex 随机字符串"""
    return secrets.token_hex(32)


def create_session_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    """创建门户 JWT session_token"""
    if expires_delta is None:
        expires_delta = timedelta(days=7)
    expire = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "aud": "medcomm_portal"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_session_token(token: str) -> int | None:
    """解析 session_token，返回 user_id"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("aud") != "medcomm_portal":
            return None
        return int(payload.get("sub", 0))
    except (JWTError, ValueError):
        return None


def is_valid_email(s: str) -> bool:
    """简单邮箱格式校验"""
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", s or ""))


def is_valid_phone(s: str) -> bool:
    """简单手机号格式（大陆 11 位）"""
    return bool(re.match(r"^1[3-9]\d{9}$", re.sub(r"\D", "", s or "")))


def is_valid_username(s: str) -> bool:
    """用户名：3-32 位字母数字下划线"""
    return bool(re.match(r"^[a-zA-Z0-9_]{3,32}$", (s or "").strip()))


def normalize_credential(credential: str, credential_type: str) -> str | None:
    """规范化 credential"""
    s = (credential or "").strip()
    if not s:
        return None
    if credential_type == "phone":
        return re.sub(r"\D", "", s) or None
    if credential_type == "username":
        return s.lower() if len(s) <= 32 else s[:32].lower()
    return s.lower() if credential_type == "email" else s


async def get_user_by_credential(
    db: AsyncSession, credential: str
) -> MedcommUser | None:
    """通过 email、phone 或 username 查询用户"""
    s = (credential or "").strip()
    if not s:
        return None
    # 推断类型
    if "@" in s:
        c = s.lower()
        cond = MedcommUser.email == c
    elif re.match(r"^1[3-9]\d{9}$", re.sub(r"\D", "", s)):
        c = re.sub(r"\D", "", s)
        cond = MedcommUser.phone == c
    else:
        c = s.lower()
        cond = MedcommUser.username == c
    r = await db.execute(select(MedcommUser).where(cond))
    return r.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> MedcommUser | None:
    r = await db.execute(select(MedcommUser).where(MedcommUser.id == user_id))
    return r.scalar_one_or_none()


async def get_user_license(db: AsyncSession, user_id: int) -> MedcommUserLicense | None:
    r = await db.execute(
        select(MedcommUserLicense).where(MedcommUserLicense.user_id == user_id)
    )
    return r.scalar_one_or_none()


async def log_security_event(
    db: AsyncSession,
    event_type: str,
    user_id: int | None = None,
    reason: str | None = None,
    client_ip: str | None = None,
) -> None:
    """记录安全事件"""
    evt = MedcommSecurityEvent(
        event_type=event_type,
        user_id=user_id,
        reason=reason,
        client_ip=client_ip[:45] if client_ip else None,
    )
    db.add(evt)
    await db.flush()


async def revoke_access_token(
    db: AsyncSession,
    user_id: int,
    reason: str,
    client_ip: str | None = None,
) -> None:
    """撤销用户 access_token 并记录安全事件"""
    await db.execute(
        update(MedcommUserLicense)
        .where(MedcommUserLicense.user_id == user_id)
        .values(access_token=None, updated_at=datetime.now(timezone.utc))
    )
    await log_security_event(
        db,
        event_type="access_token_revoked",
        user_id=user_id,
        reason=reason,
        client_ip=client_ip,
    )
    await db.flush()


async def get_user_by_access_token(
    db: AsyncSession, access_token: str
) -> MedcommUser | None:
    """通过 access_token 查询用户（软件端）"""
    r = await db.execute(
        select(MedcommUserLicense, MedcommUser)
        .join(MedcommUser, MedcommUserLicense.user_id == MedcommUser.id)
        .where(
            MedcommUserLicense.access_token == access_token,
            MedcommUser.is_active == 1,
        )
    )
    row = r.one_or_none()
    return row[1] if row else None

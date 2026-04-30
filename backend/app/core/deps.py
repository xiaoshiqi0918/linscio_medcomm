"""
FastAPI 依赖注入 — 当前用户（统一 JWT 认证）

两种部署模式共用同一套 JWT 认证流程：
  desktop: JWT + 内存 stub 黑名单
  saas:    JWT + Redis 黑名单
"""
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def _extract_token(cred_or_request) -> str | None:
    """从 HTTPAuthorizationCredentials 或 Request 对象中提取 Bearer token"""
    if isinstance(cred_or_request, HTTPAuthorizationCredentials):
        return cred_or_request.credentials
    if isinstance(cred_or_request, Request):
        auth = cred_or_request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
    return None


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    from app.core.security import decode_token, is_token_blacklisted

    token = _extract_token(cred) if cred is not None else None
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证 Token"
        )

    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已失效"
        )

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期"
        )

    user_id = int(payload.get("sub", 0))
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 载荷异常"
        )

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在"
        )
    if getattr(user, "is_banned", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被封禁"
        )
    return user


async def get_current_user_or_default(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """SaaS: 要求 JWT 认证；Desktop: 有 token 就解析，否则返回 user_id=1。"""
    from app.core.config import is_saas

    token = _extract_token(cred) if cred is not None else None

    if token:
        return await get_current_user(cred, db)

    if is_saas():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证 Token"
        )

    user = await db.get(User, 1)
    if user is None:
        raise HTTPException(status_code=500, detail="默认用户不存在")
    return user


def _extract_user_id_from_token(request: Request) -> int | None:
    """从 Request 中提取 user_id（仅解码 JWT，不查 DB），供中间件等轻量场景使用。"""
    from app.core.security import decode_token
    token = _extract_token(request)
    if not token:
        return None
    try:
        payload = decode_token(token)
        uid = int(payload.get("sub", 0))
        return uid if uid else None
    except Exception:
        return None


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not getattr(user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return user

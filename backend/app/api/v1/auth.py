"""认证 API - 轻量 token 会话"""
import base64
import hmac
import hashlib
import json
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.license import load_license
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User

router = APIRouter()

TOKEN_TTL_SECONDS = 86400


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _sign(msg: bytes) -> str:
    sig = hmac.new(settings.auth_secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url(sig)


def issue_token(user_id: int, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    payload = {"uid": user_id, "exp": int(time.time()) + int(ttl_seconds)}
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign(body.encode("utf-8"))
    return f"{body}.{sig}"


def verify_token(token: str) -> dict:
    if token == "local-single-user":
        if not getattr(settings, "debug", False):
            raise HTTPException(status_code=401, detail="token 已失效")
        return {"uid": 1, "exp": int(time.time()) + 3600}
    parts = (token or "").split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="无效 token")
    body, sig = parts
    if not hmac.compare_digest(_sign(body.encode("utf-8")), sig):
        raise HTTPException(status_code=401, detail="token 校验失败")
    payload = json.loads(_b64url_decode(body).decode("utf-8"))
    if int(payload.get("exp") or 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="token 已过期")
    return payload


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "") or ""
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    uid = int(verify_token(token).get("uid") or 0)
    r = await db.execute(select(User).where(User.id == uid))
    user = r.scalar_one_or_none()
    if user is None:
        # 容错：token 里 uid 不存在则回退到 1
        r = await db.execute(select(User).where(User.id == 1))
        user = r.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


class LoginRequest(BaseModel):
    """轻量登录：username 用于区分用户"""
    username: str | None = None
    password: str | None = None


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """登录：按 username 取/建用户并签发 token（无 username 回退到 id=1）"""
    name = (req.username or "").strip()
    if not name:
        r = await db.execute(select(User).where(User.id == 1))
        user = r.scalar_one_or_none()
        if user is None:
            user = User(id=1, display_name="医生", email="user@local")
            db.add(user)
            await db.commit()
        token = issue_token(user.id)
        return {"user": {"id": user.id, "display_name": user.display_name, "email": user.email}, "token": token, "expires_in": TOKEN_TTL_SECONDS}

    r = await db.execute(select(User).where(User.display_name == name))
    user = r.scalar_one_or_none()
    if user is None:
        user = User(display_name=name, email=f"{name}@local")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    token = issue_token(user.id)
    return {
        "user": {"id": user.id, "display_name": user.display_name, "email": user.email},
        "token": token,
        "expires_in": TOKEN_TTL_SECONDS,
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """获取当前用户"""
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
    }


@router.get("/license")
async def get_license():
    """获取当前许可信息（基础版/定制版）"""
    data = load_license()
    preset = data.get("preset_docs", [])
    return {
        "type": data.get("type", "basic"),
        "custom_specialties": data.get("custom_specialties", []),
        "service_expiry": data.get("service_expiry"),
        "content_version": data.get("content_version", "1.0"),
        "next_content_update": data.get("next_content_update"),
        "preset_docs": preset,
        "specialty_stats": data.get("specialty_stats", {}),
    }

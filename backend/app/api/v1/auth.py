"""
认证接口 — 统一手机号 + 密码 + JWT
桌面端登录时先远程调用 SaaS API 验证，成功后同步用户到本地 SQLite；
网络不可达时回退到本地缓存验证（需要至少成功登录过一次）。
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings, is_desktop, is_saas
from app.core.deps import get_current_user
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, blacklist_token,
)
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

_REMOTE_TIMEOUT = 10


# ══════════════════════════════════════════════════════════════
#  共用 schema
# ══════════════════════════════════════════════════════════════

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    user_id: int
    display_name: str | None = None
    credits: float = 0
    gift_credits: float = 0


class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str | None = None
    referral_code: str | None = Field(None, max_length=8)
    agreed_terms: bool = Field(..., description="用户必须显式勾选同意协议")


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


# ══════════════════════════════════════════════════════════════
#  注册
# ══════════════════════════════════════════════════════════════

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if is_desktop():
        return await _desktop_register(req, db)
    return await _saas_register(req, request, db)


async def _saas_register(
    req: RegisterRequest, request: Request, db: AsyncSession
) -> TokenResponse:
    """SaaS 模式：直接在 PostgreSQL 中注册"""
    from app.core.rate_limit import check_register_rate
    await check_register_rate(request)

    if not req.agreed_terms:
        raise HTTPException(
            status_code=400,
            detail="请阅读并同意《用户服务协议》《免责声明》和《隐私政策》",
        )

    existing = await db.execute(select(User).where(User.phone == req.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该手机号已注册")

    referred_by = None
    if req.referral_code:
        referrer = await db.execute(
            select(User).where(User.referral_code == req.referral_code)
        )
        referrer_user = referrer.scalar_one_or_none()
        if referrer_user:
            referred_by = referrer_user.id

    user = User(
        phone=req.phone,
        password_hash=hash_password(req.password),
        display_name=req.display_name or f"用户{req.phone[-4:]}",
        referred_by=referred_by,
        gift_credits=Decimal(str(settings.new_user_gift_credits)),
        gift_credits_expire_at=datetime.utcnow() + timedelta(days=settings.gift_credits_validity_days),
        free_generation_used=False,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    if referred_by:
        try:
            from app.models.referral import ReferralLog
            from app.services.credit.service import add_credits
            from dateutil.relativedelta import relativedelta
            REGISTER_REWARD = Decimal("5")
            referral_log = ReferralLog(
                referrer_id=referred_by,
                referred_id=user.id,
                trigger_type="register",
                reward_credits=REGISTER_REWARD,
            )
            db.add(referral_log)
            await add_credits(referred_by, REGISTER_REWARD, db, credit_type="promo_credits")
            referrer_user = await db.get(User, referred_by)
            if referrer_user:
                referrer_user.promo_credits_expire_at = (
                    datetime.utcnow() + relativedelta(months=settings.promo_credits_validity_months)
                )
            await db.commit()
            logger.info("推广奖励: 推荐人 %d 因新用户 %d 注册获得 %s 积分", referred_by, user.id, REGISTER_REWARD)
        except Exception as e:
            logger.warning("推广奖励发放失败: %s", e)

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        display_name=user.display_name,
        credits=float(user.credits or 0),
        gift_credits=float(user.gift_credits or 0),
    )


async def _desktop_register(req: RegisterRequest, db: AsyncSession) -> TokenResponse:
    """桌面端：转发到 SaaS API 注册，成功后同步到本地"""
    saas_url = f"{settings.saas_api_url.rstrip('/')}/api/v1/auth/register"
    try:
        async with httpx.AsyncClient(timeout=_REMOTE_TIMEOUT) as client:
            resp = await client.post(saas_url, json={
                "phone": req.phone,
                "password": req.password,
                "display_name": req.display_name,
                "referral_code": req.referral_code,
                "agreed_terms": req.agreed_terms,
            })
        if resp.status_code == 200:
            saas_data = resp.json()
            user = await _sync_user_to_local(req.phone, req.password, saas_data, db)
            logger.info("桌面端远程注册成功: phone=%s", req.phone)
            return _issue_local_token(user)
        detail = "注册失败"
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)
    except httpx.HTTPError as exc:
        logger.warning("桌面端注册失败（SaaS 不可达）: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="注册需要联网，请连接网络后重试",
        )


# ══════════════════════════════════════════════════════════════
#  登录
# ══════════════════════════════════════════════════════════════

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    if is_desktop():
        return await _desktop_login(req, db)
    return await _saas_login(req, db)


async def _saas_login(req: LoginRequest, db: AsyncSession) -> TokenResponse:
    """SaaS 模式：直接查 PostgreSQL 验证"""
    from app.core.rate_limit import check_login_rate
    await check_login_rate(req.phone)

    result = await db.execute(select(User).where(User.phone == req.phone))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if getattr(user, "is_banned", False):
        raise HTTPException(status_code=403, detail="账号已被封禁")
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")

    user.last_login_at = datetime.utcnow()
    await db.commit()

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        display_name=user.display_name,
        credits=float(user.credits or 0),
        gift_credits=float(user.gift_credits or 0),
    )


async def _desktop_login(req: LoginRequest, db: AsyncSession) -> TokenResponse:
    """桌面端：远程 SaaS 验证优先，离线时回退到本地缓存"""
    saas_url = f"{settings.saas_api_url.rstrip('/')}/api/v1/auth/login"
    try:
        async with httpx.AsyncClient(timeout=_REMOTE_TIMEOUT) as client:
            resp = await client.post(
                saas_url,
                json={"phone": req.phone, "password": req.password},
            )
        if resp.status_code == 200:
            saas_data = resp.json()
            user = await _sync_user_to_local(req.phone, req.password, saas_data, db)
            logger.info("桌面端远程登录成功: phone=%s user_id=%d", req.phone, user.id)
            return _issue_local_token(user)
        detail = "登录失败"
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)
    except httpx.HTTPError as exc:
        logger.info("SaaS 不可达，回退到本地验证: %s", exc)
        return await _local_fallback_login(req, db)


async def _sync_user_to_local(
    phone: str, raw_password: str, saas_data: dict, db: AsyncSession
) -> User:
    """将 SaaS 返回的用户信息同步到本地 SQLite"""
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user:
        user.display_name = saas_data.get("display_name") or user.display_name
        user.password_hash = hash_password(raw_password)
        user.last_login_at = datetime.utcnow()
    else:
        user = User(
            phone=phone,
            password_hash=hash_password(raw_password),
            display_name=saas_data.get("display_name", f"用户{phone[-4:]}"),
            last_login_at=datetime.utcnow(),
        )
        db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _local_fallback_login(req: LoginRequest, db: AsyncSession) -> TokenResponse:
    """离线兜底：仅在用户之前至少成功登录过一次时可用"""
    result = await db.execute(select(User).where(User.phone == req.phone))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="首次登录需要联网验证，请连接网络后重试",
        )
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    user.last_login_at = datetime.utcnow()
    await db.commit()
    logger.info("桌面端离线登录成功: phone=%s user_id=%d", req.phone, user.id)
    return _issue_local_token(user)


def _issue_local_token(user: User) -> TokenResponse:
    """签发本地 JWT"""
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user_id=user.id,
        display_name=user.display_name,
        credits=float(user.credits or 0),
        gift_credits=float(user.gift_credits or 0),
    )


# ══════════════════════════════════════════════════════════════
#  刷新 Token
# ══════════════════════════════════════════════════════════════

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh Token 无效或已过期")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token 类型错误")

    user_id = int(payload.get("sub", 0))
    user = await db.get(User, user_id)
    if not user or getattr(user, "is_banned", False):
        raise HTTPException(status_code=401, detail="用户不存在或已封禁")

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        display_name=user.display_name,
        credits=float(user.credits or 0),
        gift_credits=float(user.gift_credits or 0),
    )


# ══════════════════════════════════════════════════════════════
#  登出
# ══════════════════════════════════════════════════════════════

@router.post("/logout")
async def logout(request: Request, user: User = Depends(get_current_user)):
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        await blacklist_token(token)
    return {"message": "已登出"}


# ══════════════════════════════════════════════════════════════
#  当前用户信息
# ══════════════════════════════════════════════════════════════

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "phone": user.phone,
        "display_name": user.display_name,
        "credits": float(user.credits or 0),
        "gift_credits": float(user.gift_credits or 0),
        "gift_credits_expire_at": user.gift_credits_expire_at.isoformat() if user.gift_credits_expire_at else None,
        "promo_credits": float(user.promo_credits or 0),
        "frozen_credits": float(user.frozen_credits or 0),
        "referral_code": user.referral_code,
        "free_generation_used": user.free_generation_used,
        "total_recharged": float(user.total_recharged or 0),
        "total_consumed": float(user.total_consumed or 0),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ══════════════════════════════════════════════════════════════
#  授权信息（桌面端 / SaaS 兼容）
# ══════════════════════════════════════════════════════════════

@router.get("/license")
async def get_license():
    if is_desktop():
        try:
            from app.core.license import load_license
            data = load_license()
        except ImportError:
            data = {"type": "basic"}
        return {
            "type": data.get("type", "basic"),
            "custom_specialties": data.get("custom_specialties", []),
            "service_expiry": data.get("service_expiry"),
            "content_version": data.get("content_version", "1.0"),
            "next_content_update": data.get("next_content_update"),
            "preset_docs": data.get("preset_docs", []),
            "specialty_stats": data.get("specialty_stats", {}),
        }
    return {
        "type": "saas",
        "custom_specialties": [],
        "service_expiry": None,
        "content_version": "1.0",
        "next_content_update": None,
        "preset_docs": [],
        "specialty_stats": {},
    }

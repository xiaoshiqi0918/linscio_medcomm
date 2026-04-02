from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import PortalUser
from app.schemas.auth import UserRegister, UserLogin, TokenResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortalUser).where(PortalUser.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = PortalUser(
        username=data.username,
        password_hash=hash_password(data.password),
        email=data.email,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortalUser).where(PortalUser.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")
    user.last_login = datetime.utcnow()
    await db.flush()
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout():
    return {"message": "ok"}

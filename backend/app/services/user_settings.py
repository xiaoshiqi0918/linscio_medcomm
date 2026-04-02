from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_setting import UserSetting
from app.services.security.user_setting_crypto import ENC_PREFIX, encrypt_value, decrypt_value


class UserSettingService:
    """统一用户设置读写：封装敏感字段加解密与兼容迁移。"""

    SENSITIVE_KEYS = {
        "ncbi_api_key",
    }

    @classmethod
    async def get(cls, db: AsyncSession, user_id: int, key: str, default: str = "") -> str:
        r = await db.execute(
            select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        row = r.scalar_one_or_none()
        if row is None:
            return default
        raw = (row.value or "")
        if key in cls.SENSITIVE_KEYS:
            val = decrypt_value(raw)
            # 自动迁移：旧明文转密文
            if raw and not raw.startswith(ENC_PREFIX):
                row.value = encrypt_value(val)
                await db.commit()
            return val or default
        return raw or default

    @classmethod
    async def set(cls, db: AsyncSession, user_id: int, key: str, value: str) -> None:
        stored = (value or "").strip()
        if key in cls.SENSITIVE_KEYS:
            stored = encrypt_value(stored)
        r = await db.execute(
            select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        row = r.scalar_one_or_none()
        if row is None:
            row = UserSetting(user_id=user_id, key=key, value=stored)
            db.add(row)
        else:
            row.value = stored
        await db.commit()

    @classmethod
    async def delete(cls, db: AsyncSession, user_id: int, key: str) -> None:
        r = await db.execute(
            select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        row = r.scalar_one_or_none()
        if row is not None:
            await db.delete(row)
            await db.commit()


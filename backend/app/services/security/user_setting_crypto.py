from __future__ import annotations

import base64
import hashlib
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


ENC_PREFIX: Final[str] = "enc:v1:"


def _fernet() -> Fernet:
    # 用服务端 secret 派生固定长度 key（32 urlsafe base64）
    raw = hashlib.sha256(settings.auth_secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_value(plain: str) -> str:
    if plain is None:
        return ""
    s = str(plain)
    if not s:
        return ""
    if s.startswith(ENC_PREFIX):
        return s
    token = _fernet().encrypt(s.encode("utf-8")).decode("utf-8")
    return f"{ENC_PREFIX}{token}"


def decrypt_value(stored: str) -> str:
    if stored is None:
        return ""
    s = str(stored)
    if not s:
        return ""
    if not s.startswith(ENC_PREFIX):
        # 兼容旧明文
        return s
    token = s[len(ENC_PREFIX):]
    try:
        plain = _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
        return plain
    except InvalidToken:
        # key 变化或数据损坏
        return ""


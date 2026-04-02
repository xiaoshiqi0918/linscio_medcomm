# 授权管理优化：公钥签名方案（Ed25519）
# 门户持私钥签发 payload，客户端仅用公钥验签，私钥不随镜像分发
import base64
import json
import logging
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

logger = logging.getLogger(__name__)

# base64url 无 padding
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def get_signing_key(private_key_b64: str) -> Optional[Ed25519PrivateKey]:
    """从 base64 编码的私钥（PEM 或 raw 32 bytes）加载 Ed25519 私钥"""
    if not private_key_b64 or not private_key_b64.strip():
        return None
    try:
        raw = base64.b64decode(private_key_b64.strip())
        if len(raw) == 32:
            return Ed25519PrivateKey.from_private_bytes(raw)
        pem = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if "PRIVATE" in pem:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            key = load_pem_private_key(raw if isinstance(raw, bytes) else raw.encode(), password=None)
            if isinstance(key, Ed25519PrivateKey):
                return key
        return None
    except Exception as e:
        logger.warning("加载授权签发私钥失败: %s", e)
        return None


def sign_license_payload(
    license_id: str,
    expires_ts: int,
    machine_id: Optional[str] = None,
    private_key: Optional[Ed25519PrivateKey] = None,
) -> Optional[str]:
    """
    签发授权 payload，返回 base64url(payload_json).base64url(signature)。
    若未配置私钥则返回 None，客户端将仅依赖在线校验。
    """
    if not private_key:
        return None
    payload = {
        "license_id": license_id,
        "expires_ts": expires_ts,
        "machine_id": machine_id or "",
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = private_key.sign(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"

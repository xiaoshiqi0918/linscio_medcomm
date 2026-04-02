import os
import subprocess
import secrets
import string
import fcntl
import signal
from uuid import uuid4
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

from app.config import settings
from app.models import RegistryCredential


def _get_cipher():
    key = settings.AES_SECRET_KEY.encode("utf-8")[:32].ljust(32, b"\0")
    iv = settings.AES_IV.encode("utf-8")[:16].ljust(16, b"\0")
    return Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())


def encrypt_password(plain: str) -> str:
    cipher = _get_cipher()
    encryptor = cipher.encryptor()
    pad = 16 - (len(plain.encode("utf-8")) % 16)
    data = plain.encode("utf-8") + bytes([pad] * pad)
    ct = encryptor.update(data) + encryptor.finalize()
    return base64.b64encode(ct).decode("ascii")


def decrypt_password(enc: str) -> str:
    cipher = _get_cipher()
    decryptor = cipher.decryptor()
    ct = base64.b64decode(enc.encode("ascii"))
    data = decryptor.update(ct) + decryptor.finalize()
    pad = data[-1]
    return data[:-pad].decode("utf-8")


def generate_registry_username(plan_prefix: str | None = None) -> str:
    suffix = uuid4().hex[:8]
    if plan_prefix:
        return f"{plan_prefix}_user_{suffix}"
    return "user_" + suffix


def get_plan_prefix(plan_code: str) -> str:
    m = {"basic": "basic", "professional": "pro", "team": "team", "enterprise": "enterprise", "beta": "beta"}
    return m.get(plan_code, "user")


def get_allowed_image_tags(plan_code: str) -> list[str]:
    base = ["linscio-db:*", "linscio-ai:basic*"]
    if plan_code == "basic":
        return base
    if plan_code == "professional":
        return base + ["linscio-ai:pro*"]
    if plan_code == "team":
        return base + ["linscio-ai:pro*", "linscio-ai:team*"]
    if plan_code in ("enterprise", "beta"):
        return ["linscio-db:*", "linscio-ai:*"]
    return base


def generate_registry_password(length: int = 24) -> str:
    """生成 Registry 密码，默认 24 位十六进制（与 8.1 规范 token_hex(12) 一致）。"""
    return secrets.token_hex(12)


def write_htpasswd(username: str, password: str) -> bool:
    path = settings.REGISTRY_AUTH_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            subprocess.run(
                ["htpasswd", "-Bb", path, username, password],
                check=True,
                capture_output=True,
            )
            trigger_registry_reload()
            return True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    except (OSError, AttributeError):
        try:
            subprocess.run(
                ["htpasswd", "-Bb", path, username, password],
                check=True,
                capture_output=True,
            )
            trigger_registry_reload()
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


def remove_from_htpasswd(username: str) -> bool:
    """从 htpasswd 文件中删除指定用户（作废授权时使 Registry 立即拒绝该凭证）。"""
    path = settings.REGISTRY_AUTH_FILE
    if not os.path.isfile(path):
        return True
    try:
        fd = os.open(path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            subprocess.run(
                ["htpasswd", "-D", path, username],
                check=True,
                capture_output=True,
            )
            trigger_registry_reload()
            return True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except subprocess.CalledProcessError:
        return True
    except FileNotFoundError:
        return False
    except (OSError, AttributeError):
        try:
            subprocess.run(
                ["htpasswd", "-D", path, username],
                check=True,
                capture_output=True,
            )
            trigger_registry_reload()
            return True
        except subprocess.CalledProcessError:
            return True


def trigger_registry_reload() -> None:
    """若配置了 REGISTRY_PID_FILE，向该进程发送 SIGHUP 使 Registry 重载 htpasswd（8.3）。"""
    pid_file = getattr(settings, "REGISTRY_PID_FILE", None)
    if not pid_file or not os.path.isfile(pid_file):
        return
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
    except (ValueError, OSError, ProcessLookupError):
        pass

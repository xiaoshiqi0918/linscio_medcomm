from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt 最多 72 字节，超长密码截断避免 ValueError
def _truncate_password_for_bcrypt(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        return pwd_bytes[:72].decode("utf-8", errors="ignore") or password[:72]
    return password


def hash_password(password: str) -> str:
    return pwd_context.hash(_truncate_password_for_bcrypt(password))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate_password_for_bcrypt(plain), hashed)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

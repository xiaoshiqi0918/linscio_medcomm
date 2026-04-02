"""
仓库接口：与架构图 /api/v1/registry 对应，收口凭证查询；可选提供 Token 签发（Registry v2 Token Auth）。
"""
import base64
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt

from app.config import settings
from app.database import get_db
from app.models import PortalUser, RegistryCredential, LicenseKey
from app.schemas.user import RegistryCredentialResponse
from app.services.registry_service import decrypt_password

from app.routers.user import get_current_user

router = APIRouter(prefix="/registry", tags=["registry"])


def _start_of_current_month_utc() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/credential", response_model=RegistryCredentialResponse)
async def get_registry_credential(
    db: AsyncSession = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    """
    获取当前登录用户的镜像仓库凭证（与 GET /user/registry-credential 等价，收口至仓库接口）。
    """
    result = await db.execute(
        select(RegistryCredential).where(RegistryCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="尚未激活授权，无法获取凭证")
    r = await db.execute(select(LicenseKey).where(LicenseKey.id == cred.license_id))
    lic = r.scalar_one_or_none()
    if lic and lic.is_revoked:
        raise HTTPException(status_code=403, detail="授权已作废")
    if cred.expires_at and cred.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="授权已过期")
    password = decrypt_password(cred.registry_password_enc)
    return RegistryCredentialResponse(
        registry_url=settings.REGISTRY_URL,
        username=cred.registry_username,
        password=password,
        allowed_image_tags=cred.allowed_image_tags,
    )


def _repos_from_allowed(allowed: list[str] | None) -> set[str]:
    """从 allowed_image_tags 提取允许的仓库名集合，如 linscio-ai:basic* -> linscio-ai。"""
    if not allowed:
        return set()
    repos = set()
    for p in allowed:
        if not p or ":" not in p:
            continue
        repos.add(p.split(":", 1)[0].strip())
    return repos


def _parse_scope(scope: str) -> tuple[str, list[str]] | None:
    """解析 scope 字符串 repository:name:action1,action2 -> (name, [action1, action2])。"""
    if not scope or scope.count(":") < 2:
        return None
    parts = scope.split(":", 2)
    if parts[0].lower() != "repository":
        return None
    return parts[1], [a.strip() for a in parts[2].split(",") if a.strip()]


@router.get("/token")
async def get_registry_token(
    request: Request,
    service: str = Query(..., description="Registry service name"),
    scope: list[str] | None = Query(None, description="repository:name:push,pull"),
    account: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Registry v2 Token Auth：docker login 时 Registry 返回 401 指向本 URL，
    客户端携带 Basic 凭证请求，本接口校验后签发 JWT，客户端凭此 Token 访问 Registry。
    使用 HS256 签发；若需 Registry 直接验签，需配置 Registry auth.token.rootcertbundle（RS256 公钥）。
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.strip().lower().startswith("basic "):
        return JSONResponse(status_code=401, content={"errors": [{"code": "UNAUTHORIZED", "message": "需要 Basic 认证"}]})
    try:
        b = base64.b64decode(auth.strip()[6:].strip())
        user_pass = b.decode("utf-8")
        if ":" not in user_pass:
            return JSONResponse(status_code=401, content={"errors": [{"code": "UNAUTHORIZED", "message": "凭证格式错误"}]})
        username, password = user_pass.split(":", 1)
        username, password = username.strip(), password
    except Exception:
        return JSONResponse(status_code=401, content={"errors": [{"code": "UNAUTHORIZED", "message": "凭证解析失败"}]})
    r = await db.execute(select(RegistryCredential).where(RegistryCredential.registry_username == username))
    cred = r.scalar_one_or_none()
    if not cred:
        return JSONResponse(status_code=401, content={"errors": [{"code": "UNAUTHORIZED", "message": "用户不存在或未激活"}]})
    r2 = await db.execute(select(LicenseKey).where(LicenseKey.id == cred.license_id))
    lic = r2.scalar_one_or_none()
    if lic and lic.is_revoked:
        return JSONResponse(status_code=401, content={"errors": [{"code": "UNAUTHORIZED", "message": "授权已作废"}]})
    if cred.expires_at and cred.expires_at < datetime.now(timezone.utc):
        return JSONResponse(status_code=401, content={"errors": [{"code": "UNAUTHORIZED", "message": "授权已过期"}]})
    plain = decrypt_password(cred.registry_password_enc)
    if plain != password:
        return JSONResponse(status_code=401, content={"errors": [{"code": "UNAUTHORIZED", "message": "密码错误"}]})
    # 拉取次数校验：按自然月重置后检查是否超限，超限拒绝签发 Token（5.5）
    if lic:
        pull_limit = lic.pull_limit_monthly if lic.pull_limit_monthly is not None else 0
        start_of_month = _start_of_current_month_utc()
        reset_at = cred.pull_count_reset_at
        if reset_at is not None and getattr(reset_at, "tzinfo", None) is None:
            try:
                reset_at = reset_at.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        if reset_at is None or start_of_month > reset_at:
            cred.pull_count_this_month = 0
            cred.pull_count_reset_at = start_of_month
            await db.flush()
        if pull_limit > 0 and (cred.pull_count_this_month or 0) >= pull_limit:
            return JSONResponse(
                status_code=429,
                content={"errors": [{"code": "TOOMANYREQUESTS", "message": "本月拉取次数已达上限"}]},
            )
    allowed_repos = _repos_from_allowed(cred.allowed_image_tags or [])
    scopes = scope or []
    access = []
    for sc in scopes:
        parsed = _parse_scope(sc)
        if not parsed:
            continue
        repo_name, actions = parsed
        if repo_name not in allowed_repos:
            continue
        granted = [a for a in actions if a in ("pull", "push")]
        if granted:
            access.append({"type": "repository", "name": repo_name, "actions": granted})
    now = datetime.now(timezone.utc)
    exp_sec = 3600
    payload = {
        "iss": settings.REGISTRY_TOKEN_ISSUER,
        "sub": username,
        "aud": service,
        "exp": now.timestamp() + exp_sec,
        "nbf": int(now.timestamp()),
        "iat": int(now.timestamp()),
        "jti": secrets.token_hex(16),
        "access": access,
    }
    token = jwt.encode(
        payload,
        (settings.REGISTRY_JWT_SECRET or settings.JWT_SECRET_KEY),
        algorithm="HS256",
    )
    return {
        "token": token,
        "expires_in": exp_sec,
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

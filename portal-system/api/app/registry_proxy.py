"""
Registry 拉取代理：在转发到 Docker Registry 前按 allowed_image_tags 校验拉取范围（按 Tag 管控）；
拉取 manifest 成功后统一计数（pull_count_this_month + pull_records），并按自然月重置。
"""
import os
os.environ.setdefault("APP_ENTRY", "registry_proxy")

import base64
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import RegistryCredential, LicenseKey, PullRecord


def _decode_basic_username(auth_header: str | None) -> str | None:
    if not auth_header or not auth_header.strip().lower().startswith("basic "):
        return None
    try:
        b = base64.b64decode(auth_header.strip()[6:].strip())
        return b.decode("utf-8").split(":", 1)[0].strip() or None
    except Exception:
        return None


def _ref_is_digest(ref: str) -> bool:
    return ref.startswith("sha256:") and len(ref) > 7


def _match_allowed(repo: str, tag: str, allowed: list[str]) -> bool:
    if not allowed:
        return True
    image_key = f"{repo}:{tag}"
    for p in allowed:
        if not p or ":" not in p:
            continue
        p_repo, p_tag = p.split(":", 1)
        if p_repo != repo:
            continue
        if p_tag == "*":
            return True
        if p_tag.endswith("*"):
            prefix = p_tag[:-1]
            if tag.startswith(prefix):
                return True
        elif tag == p_tag:
            return True
    return False


async def _get_allowed_tags(username: str) -> list[str] | None:
    """
    返回该用户的 allowed_image_tags；若用户不在 DB 返回 None 表示不限制。
    若凭证对应授权已作废，返回 [] 以拒绝所有拉取。
    """
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(RegistryCredential.allowed_image_tags, LicenseKey.is_revoked)
            .outerjoin(LicenseKey, RegistryCredential.license_id == LicenseKey.id)
            .where(RegistryCredential.registry_username == username)
        )
        row = r.one_or_none()
    if row is None:
        return None
    allowed, is_revoked = row[0], row[1]
    if is_revoked:
        return []
    return list(allowed) if allowed else []


async def _is_license_revoked(username: str) -> bool:
    """若该用户名对应凭证的授权已作废则返回 True。"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(LicenseKey.is_revoked)
            .select_from(RegistryCredential)
            .join(LicenseKey, RegistryCredential.license_id == LicenseKey.id)
            .where(RegistryCredential.registry_username == username)
        )
        row = r.one_or_none()
    return row is not None and row[0] is True


def _start_of_current_month_utc() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _ensure_pull_quota_and_check_limit(username: str) -> tuple[bool, str | None]:
    """
    若凭证存在则：按自然月重置 pull_count_this_month；再检查是否超过 pull_limit_monthly。
    若授权已作废，返回 (False, "授权已作废")。
    返回 (True, None) 表示可拉取；(False, message) 表示已达上限或错误。
    """
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(RegistryCredential, LicenseKey.pull_limit_monthly, LicenseKey.is_revoked)
            .outerjoin(LicenseKey, RegistryCredential.license_id == LicenseKey.id)
            .where(RegistryCredential.registry_username == username)
        )
        row = r.one_or_none()
        if row is None:
            return True, None
        cred, pull_limit, is_revoked = row[0], row[1], row[2]
        if is_revoked:
            return False, "授权已作废"
        start_of_month = _start_of_current_month_utc()
        reset_at = cred.pull_count_reset_at
        if reset_at is not None and hasattr(reset_at, "replace"):
            try:
                reset_at = reset_at.replace(tzinfo=timezone.utc) if getattr(reset_at, "tzinfo", None) is None else reset_at
            except Exception:
                pass
        if reset_at is None or (start_of_month > reset_at):
            cred.pull_count_this_month = 0
            cred.pull_count_reset_at = start_of_month
        await db.flush()
        limit = pull_limit if pull_limit is not None else 0
        if limit > 0 and (cred.pull_count_this_month or 0) >= limit:
            return False, f"本月拉取次数已达上限（{cred.pull_count_this_month}/{limit}），下月自动恢复"
        await db.commit()
    return True, None


async def _record_pull_success(username: str, image_name: str) -> None:
    """拉取成功后：pull_count_this_month +1，并写入 pull_records。"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(RegistryCredential).where(RegistryCredential.registry_username == username)
        )
        cred = r.scalar_one_or_none()
        if not cred:
            return
        cred.pull_count_this_month = (cred.pull_count_this_month or 0) + 1
        db.add(PullRecord(
            user_id=cred.user_id,
            license_id=cred.license_id,
            image_name=image_name,
            is_update=True,
        ))
        await db.commit()


app = FastAPI(title="LinScio AI Registry Proxy", version="0.1.0")


@app.get("/")
def root():
    """根路径：避免 Nginx/客户端探活或直接访问域名时返回 404。"""
    return {"message": "LinScio Registry Proxy", "v2": "/v2/"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "registry-proxy"}


@app.api_route("/v2/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_v2(path: str, request: Request):
    path = path.strip("/")
    # Docker Distribution 规范：blob upload 使用带尾斜杠 /v2/<name>/blobs/uploads/
    # 统一转成带尾斜杠再转发，避免后端对 .../blobs/uploads 返回 301 → .../blobs/uploads/ 后
    # 对已带尾斜杠的请求再 301 形成循环
    if path.endswith("blobs/uploads") and not path.endswith("blobs/uploads/"):
        path = path + "/"
    parts = path.split("/")
    count_pull_username = None
    count_pull_image = None
    # GET /v2/<name>/manifests/<reference> 时按 Tag 校验并做拉取配额检查/计数
    if (
        request.method in ("GET", "HEAD")
        and len(parts) >= 3
        and parts[-2] == "manifests"
    ):
        name = "/".join(parts[:-2])
        ref = parts[-1]
        if not _ref_is_digest(ref):
            username = _decode_basic_username(request.headers.get("Authorization"))
            if username:
                if await _is_license_revoked(username):
                    return JSONResponse(
                        status_code=403,
                        content={"errors": [{"code": "DENIED", "message": "授权已作废"}]},
                    )
                allowed = await _get_allowed_tags(username)
                if allowed is not None and not _match_allowed(name, ref, allowed):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "errors": [
                                {
                                    "code": "DENIED",
                                    "message": f"当前套餐不允许拉取镜像 {name}:{ref}，请使用您套餐允许的 Tag。",
                                }
                                ]
                            },
                    )
                ok, msg = await _ensure_pull_quota_and_check_limit(username)
                if not ok:
                    return JSONResponse(
                        status_code=403,
                        content={"errors": [{"code": "DENIED", "message": msg or "本月拉取次数已达上限"}]},
                    )
                count_pull_username = username
                count_pull_image = f"{name}:{ref}"
    upstream = settings.REGISTRY_UPSTREAM_URL.rstrip("/")
    url = f"{upstream}/v2/{path}"
    if request.url.query:
        url += "?" + request.url.query
    headers = dict(request.headers)
    headers.pop("host", None)
    # 推送（POST/PUT）可能很大，需要更长超时，避免 "server closed idle connection"
    is_push = request.method in ("POST", "PUT", "PATCH", "DELETE")
    timeout = 1800.0 if is_push else 60.0
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if request.method in ("GET", "HEAD"):
                r = await client.request(request.method, url, headers=headers)
            else:
                # 流式转发请求体，避免大 layer（如 400MB）整块读入内存导致超时/EOF
                async def body_stream():
                    async for chunk in request.stream():
                        yield chunk
                r = await client.request(request.method, url, headers=headers, content=body_stream())
    except httpx.RequestError as e:
        return JSONResponse(status_code=502, content={"errors": [{"code": "UNAVAILABLE", "message": str(e)}]})
    # 避免 301 循环：后端对 .../blobs/uploads/ 返回 301 到同一路径时不透传
    if r.status_code == 301 and path.endswith("blobs/uploads/"):
        location = (r.headers.get("location") or "").rstrip("/")
        req_path_normalized = path.rstrip("/")
        if location.endswith("blobs/uploads") and req_path_normalized.endswith("blobs/uploads"):
            loc_path = location.split("/v2/")[-1].rstrip("/") if "/v2/" in location else location
            if loc_path == req_path_normalized:
                return JSONResponse(
                    status_code=502,
                    content={"errors": [{"code": "UNAVAILABLE", "message": "Registry 重定向循环，请确认 registry-proxy 已更新"}]},
                )
    if count_pull_username and count_pull_image and 200 <= r.status_code < 300:
        await _record_pull_success(count_pull_username, count_pull_image)
    response_headers = dict(r.headers)
    response_headers.pop("transfer-encoding", None)
    response_headers.pop("connection", None)
    # 重写 Location：后端返回的内网地址（如 http://linscio-registry:5000）客户端无法解析，
    # 改为客户端当前请求的 host，避免 "lookup linscio-registry: no such host"
    location = response_headers.get("location")
    if location and upstream and location.startswith(upstream):
        public_base = f"{request.url.scheme}://{request.url.netloc}"
        response_headers["location"] = public_base + location[len(upstream):]
    return Response(
        content=r.content,
        status_code=r.status_code,
        headers=response_headers,
        media_type=r.headers.get("content-type"),
    )

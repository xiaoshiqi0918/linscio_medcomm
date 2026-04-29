"""
LinScio MedComm FastAPI 主入口 — 双模式支持
通过 DEPLOYMENT_MODE 切换运行模式：desktop / saas
"""
import os
import logging
from contextlib import asynccontextmanager

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings, is_desktop, is_saas
from app.core.database import init_db, get_db_path, engine

LOCAL_API_KEY = os.environ.get("LINSCIO_LOCAL_API_KEY")
LOCAL_KEY_EXEMPT_EXACT = {"/health", "/openapi.json", "/api/v1/imagegen/serve"}
LOCAL_KEY_EXEMPT_PREFIX = ("/docs", "/redoc")

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _client_is_loopback(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    host = (client.host or "").lower()
    return host in ("127.0.0.1", "::1", "localhost")


class LocalApiKeyMiddleware(BaseHTTPMiddleware):
    """本机隔离：仅桌面模式 + LINSCIO_LOCAL_API_KEY 存在时校验请求头"""

    async def dispatch(self, request: Request, call_next):
        if not LOCAL_API_KEY or is_saas():
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.scope.get("path", "")
        if path in LOCAL_KEY_EXEMPT_EXACT or any(path.startswith(p) for p in LOCAL_KEY_EXEMPT_PREFIX):
            return await call_next(request)
        header_key = request.headers.get("X-Local-Api-Key") or request.headers.get("x-local-api-key")
        if header_key == LOCAL_API_KEY:
            return await call_next(request)
        if settings.debug and _client_is_loopback(request):
            return await call_next(request)
        return JSONResponse(status_code=403, content={"detail": "Local API key required"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    mode = settings.deployment_mode
    logger.info("MedComm Backend 启动中... (mode=%s)", mode)

    await init_db()

    try:
        from app.services.vector.fts5 import ensure_fts_tables
        await ensure_fts_tables()
    except Exception:
        pass

    from pathlib import Path
    Path(settings.app_data_root).mkdir(parents=True, exist_ok=True)
    for sub in ("images", "uploads", "backups", "config"):
        Path(settings.app_data_root, sub).mkdir(parents=True, exist_ok=True)

    try:
        from app.services.imagegen.engine import detect_providers
        await detect_providers()
    except Exception:
        pass

    try:
        from app.services.knowledge.system_knowledge import index_system_knowledge
        await index_system_knowledge()
    except Exception:
        pass

    try:
        from app.services.llm.manager import load_user_default_model_from_db
        await load_user_default_model_from_db()
    except Exception:
        pass

    if is_saas():
        from app.tasks.periodic import start_periodic_tasks
        start_periodic_tasks()

        # Sentry 异常追踪
        if settings.sentry_dsn:
            try:
                import sentry_sdk
                from sentry_sdk.integrations.fastapi import FastApiIntegration
                from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
                sentry_sdk.init(
                    dsn=settings.sentry_dsn,
                    traces_sample_rate=0.1,
                    integrations=[FastApiIntegration(), SqlalchemyIntegration()],
                    environment="production",
                )
                logger.info("Sentry 已初始化")
            except ImportError:
                logger.warning("sentry-sdk 未安装，跳过 Sentry 集成")
            except Exception as e:
                logger.warning("Sentry 初始化失败: %s", e)

    logger.info("MedComm Backend 启动完成 (mode=%s)", mode)

    yield

    logger.info("MedComm Backend 关闭中...")
    if is_saas():
        from app.tasks.periodic import stop_periodic_tasks
        await stop_periodic_tasks()
    await engine.dispose()
    if is_saas():
        from app.core.redis import close_all_redis
        await close_all_redis()
    logger.info("MedComm Backend 已关闭")


app = FastAPI(
    title=f"LinScio MedComm API ({settings.deployment_mode})",
    description="科普内容创作助手后端 API",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

if is_desktop():
    app.add_middleware(LocalApiKeyMiddleware)

# CORS
if is_desktop() and LOCAL_API_KEY:
    _cors_origins = ["*"]
elif is_saas() and not settings.debug:
    _cors_origins = ["https://www.linscio.com", "https://linscio.com"]
else:
    _cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://www.linscio.com",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if is_saas() else False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── SaaS: HTTP 指标中间件 ──────────────────────────────────
if is_saas():
    import time as _time

    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            t0 = _time.monotonic()
            response = await call_next(request)
            latency = _time.monotonic() - t0
            path = request.scope.get("path", "")
            if not path.startswith(("/docs", "/redoc", "/openapi", "/metrics")):
                try:
                    from app.services.observability import record_http_request
                    record_http_request(request.method, path, response.status_code, latency)
                except Exception:
                    pass
            return response

    app.add_middleware(PrometheusMiddleware)

# ══════════════════════════════════════════════════════════════
#  路由注册 — 核心路由（两端共有）
# ══════════════════════════════════════════════════════════════
from app.api.v1 import (
    medcomm, formats, literature, knowledge, templates,
    examples, terms, polish, imagegen, auth, tasks, data,
    translate, article_snapshots, personal_corpus, medpic,
)
from app.api import internal

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(formats.router, prefix="/api/v1/formats", tags=["formats"])
app.include_router(medcomm.router, prefix="/api/v1/medcomm", tags=["medcomm"])
app.include_router(literature.router, prefix="/api/v1/literature", tags=["literature"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(examples.router, prefix="/api/v1/examples", tags=["examples"])
app.include_router(terms.router, prefix="/api/v1/terms", tags=["terms"])
app.include_router(polish.router, prefix="/api/v1/polish", tags=["polish"])
app.include_router(imagegen.router, prefix="/api/v1/imagegen", tags=["imagegen"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(translate.router, prefix="/api/v1/translate", tags=["translate"])
app.include_router(article_snapshots.router, prefix="/api/v1/medcomm", tags=["snapshots"])
app.include_router(personal_corpus.router, prefix="/api/v1/personal-corpus", tags=["personal-corpus"])
app.include_router(medpic.router, prefix="/api/v1/medpic", tags=["medpic"])
app.include_router(internal.router, prefix="/internal", tags=["internal"])

# ── SaaS 独有路由 ─────────────────────────────────────────
if is_saas():
    from app.api.v1.credits import router as credits_router
    from app.api.v1.referral import router as referral_router
    from app.api.v1.payment import router as payment_router
    from app.api.v1.admin import router as admin_router
    from app.api.v1.download import router as download_router
    app.include_router(credits_router, prefix="/api/v1", tags=["credits"])
    app.include_router(referral_router, prefix="/api/v1", tags=["referral"])
    app.include_router(payment_router, prefix="/api/v1", tags=["payment"])
    app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
    app.include_router(download_router, prefix="/api/v1/download", tags=["download"])

# ── 双模式共享路由 ─────────────────────────────────────────
from app.api.v1 import system
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])

# ── 桌面独有路由 ──────────────────────────────────────────
if is_desktop():
    from app.api.v1 import specialty
    app.include_router(specialty.router, prefix="/api/v1/specialty", tags=["specialty"])


@app.get("/health")
async def health():
    return {"status": "ok", "mode": settings.deployment_mode, "version": "0.2.0"}


if is_saas():
    from starlette.responses import Response

    @app.get("/metrics")
    async def metrics():
        try:
            from prometheus_client import generate_latest
            from app.services.observability import get_prometheus_registry
            registry = get_prometheus_registry()
            if registry is None:
                return Response("prometheus_client not installed", status_code=503)
            return Response(generate_latest(registry), media_type="text/plain; charset=utf-8")
        except ImportError:
            return Response("prometheus_client not installed", status_code=503)

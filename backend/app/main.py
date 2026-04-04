"""
LinScio MedComm FastAPI 主入口
"""
import os
from contextlib import asynccontextmanager

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import medcomm, formats, system, literature, knowledge, templates, examples, terms, polish, publish, imagegen, auth, tasks, data, specialty, translate, article_snapshots, personal_corpus, medpic
from app.api import internal
from app.core.database import init_db, get_db_path
from app.core.config import settings

LOCAL_API_KEY = os.environ.get("LINSCIO_LOCAL_API_KEY")
# imagegen/serve：供 <img src> 等无法带 X-Local-Api-Key 的请求（路径在路由内已防 .. 穿越）
LOCAL_KEY_EXEMPT_EXACT = {"/health", "/openapi.json", "/api/v1/imagegen/serve"}
LOCAL_KEY_EXEMPT_PREFIX = ("/docs", "/redoc")


def _client_is_loopback(request: Request) -> bool:
    """开发时允许本机浏览器直连 8765（无 Electron 时无法拿到随机 Local API Key）"""
    client = request.client
    if client is None:
        return False
    host = (client.host or "").lower()
    return host in ("127.0.0.1", "::1", "localhost")


class LocalApiKeyMiddleware(BaseHTTPMiddleware):
    """本机隔离：仅当 LINSCIO_LOCAL_API_KEY 存在时校验请求头"""

    async def dispatch(self, request: Request, call_next):
        if not LOCAL_API_KEY:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.scope.get("path", "")
        if path in LOCAL_KEY_EXEMPT_EXACT or any(path.startswith(p) for p in LOCAL_KEY_EXEMPT_PREFIX):
            return await call_next(request)
        header_key = request.headers.get("X-Local-Api-Key") or request.headers.get("x-local-api-key")
        if header_key == LOCAL_API_KEY:
            return await call_next(request)
        # DEBUG=1 且来自本机回环：放行（Vite 浏览器调试 + Electron 已起后端 的场景）
        if settings.debug and _client_is_loopback(request):
            return await call_next(request)
        return JSONResponse(status_code=403, content={"detail": "Local API key required"})


async def _initialize_auth():
    """认证初始化（单用户模式可空实现）"""
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：auth → init_db → ensure_fts → 目录/检测 → yield"""
    await _initialize_auth()
    await init_db()
    from app.services.vector.fts5 import ensure_fts_tables
    await ensure_fts_tables()

    from pathlib import Path
    from app.core.config import settings
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

    yield


app = FastAPI(
    title="LinScio MedComm API",
    description="医学科普写作智能体后端 API",
    version="0.1.1",
    lifespan=lifespan,
)

app.add_middleware(LocalApiKeyMiddleware)
# Electron 加载 file:// 时 Origin 非 5173；已启用本机 API Key 时放宽来源
_cors_origins = (
    ["*"]
    if LOCAL_API_KEY
    else [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
app.include_router(formats.router, prefix="/api/v1/formats", tags=["formats"])
app.include_router(medcomm.router, prefix="/api/v1/medcomm", tags=["medcomm"])
app.include_router(literature.router, prefix="/api/v1/literature", tags=["literature"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(examples.router, prefix="/api/v1/examples", tags=["examples"])
app.include_router(terms.router, prefix="/api/v1/terms", tags=["terms"])
app.include_router(polish.router, prefix="/api/v1/polish", tags=["polish"])
app.include_router(publish.router, prefix="/api/v1/publish", tags=["publish"])
app.include_router(imagegen.router, prefix="/api/v1/imagegen", tags=["imagegen"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(specialty.router, prefix="/api/v1/specialty", tags=["specialty"])
app.include_router(translate.router, prefix="/api/v1/translate", tags=["translate"])
app.include_router(article_snapshots.router, prefix="/api/v1/medcomm", tags=["snapshots"])
app.include_router(personal_corpus.router, prefix="/api/v1/personal-corpus", tags=["personal-corpus"])
app.include_router(medpic.router, prefix="/api/v1/medpic", tags=["medpic"])
app.include_router(internal.router, prefix="/internal", tags=["internal"])


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "0.1.1"}

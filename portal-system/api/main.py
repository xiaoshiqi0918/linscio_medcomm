from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.services.license_service import ensure_controlled_modules
from app.routers import auth, user, admin, public, quota, license, registry
from app.routers.container_token import router as container_token_router
from app.routers.medcomm_auth import router as medcomm_auth_router
from app.routers.medcomm_license import router as medcomm_license_router
from app.routers.medcomm_device import router as medcomm_device_router
from app.routers.medcomm_update_download import router as medcomm_update_download_router
from app.routers.medcomm_account import router as medcomm_account_router
from app.routers.medcomm_admin import router as medcomm_admin_router
from app.routers.download import router as download_router
from app.routers.client import router as client_router
from app.tasks.htpasswd_cleanup import htpasswd_cleanup_loop
from app.tasks.medcomm_device_cleanup import medcomm_device_cleanup_loop
from app.middleware.global_ip_rate_limit import GlobalIPRateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（开发用；生产建议用 Alembic 迁移）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 确保 6 个受控模块存在（新库或未跑 seed 时自动补齐，无需手动添加）
    async with AsyncSessionLocal() as db:
        await ensure_controlled_modules(db)
        await db.commit()
    # 8.3 ③ 到期定时清理：后台任务按间隔从 htpasswd 删除已过期凭证
    cleanup_task = asyncio.create_task(htpasswd_cleanup_loop())
    # MedComm 换机码表：每天清理 1 天前的记录
    medcomm_cleanup_task = asyncio.create_task(medcomm_device_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        medcomm_cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        try:
            await medcomm_cleanup_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()


app = FastAPI(
    title="LinScio Portal API",
    version="0.1.0",
    lifespan=lifespan,
)


def _get_cors_origins():
    """确保 CORS allow_origins 为 list，避免传入 method 导致 TypeError"""
    o = getattr(settings, "cors_origins_list", None)
    if callable(o):
        return o()
    if isinstance(o, list):
        return o
    return ["http://localhost:3000", "http://localhost:3001"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GlobalIPRateLimitMiddleware)


@app.get("/")
def root():
    """直接访问 API 根路径时返回说明，避免 404"""
    return {
        "service": "LinScio Portal API",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "api": "/api/v1",
    }


@app.get("/health")
def health():
    """健康检查，供负载均衡或监控使用"""
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(container_token_router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(public.router, prefix="/api/v1")
app.include_router(download_router, prefix="/api/v1")
app.include_router(client_router, prefix="/api/v1")
app.include_router(quota.router, prefix="/api/v1")
app.include_router(license.router, prefix="/api/v1")
app.include_router(registry.router, prefix="/api/v1")
app.include_router(medcomm_auth_router, prefix="/api/v1")
app.include_router(medcomm_license_router, prefix="/api/v1")
app.include_router(medcomm_device_router, prefix="/api/v1")
app.include_router(medcomm_update_download_router, prefix="/api/v1")
app.include_router(medcomm_account_router, prefix="/api/v1")
app.include_router(medcomm_admin_router, prefix="/api/v1")

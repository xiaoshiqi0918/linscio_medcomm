"""
Registry-proxy 独立运行时的最小配置（不依赖 JWT/AES 等主应用密钥）。
单独启动 uvicorn app.registry_proxy:app 时使用本配置，避免缺少 JWT_SECRET_KEY 等导致校验失败。
"""
from pydantic_settings import BaseSettings


class ProxySettings(BaseSettings):
    DATABASE_URL: str
    REGISTRY_UPSTREAM_URL: str = "http://localhost:5000"

    class Config:
        env_file = ".env"
        extra = "ignore"


proxy_settings = ProxySettings()

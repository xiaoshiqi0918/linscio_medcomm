from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days（门户用户）
    JWT_EXPIRE_MINUTES_ADMIN: int = 480  # 8 hours（管理员，8.1）
    REGISTRY_JWT_SECRET: str | None = None  # 独立 Secret 签发 Registry Token，未设则回退 JWT_SECRET_KEY（8.1）
    AES_SECRET_KEY: str
    AES_IV: str
    REGISTRY_AUTH_FILE: str = "/registry/auth/htpasswd"
    # 可选：Registry 进程 PID 文件路径，写入 htpasswd 后发 SIGHUP 使 Registry 重载认证（8.3）
    REGISTRY_PID_FILE: str | None = None
    # 到期凭证从 htpasswd 清理的定时任务间隔（秒），0 表示不运行（8.3 ③）
    HTPASSWD_CLEANUP_INTERVAL_SECONDS: int = 3600
    REGISTRY_URL: str = "registry.linscio.com.cn"
    # 代理模式：代理请求转发到的 Registry 内网地址（仅 registry-proxy 使用）
    REGISTRY_UPSTREAM_URL: str = "http://localhost:5000"
    # Registry v2 Token Auth 签发时的 iss 声明（GET /api/v1/registry/token）
    REGISTRY_TOKEN_ISSUER: str = "LinScio Registry"
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:3001"]'
    ENVIRONMENT: str = "development"
    # 腾讯云 COS（F2：安装包/备份），桶名与地域与合并方案一致
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_BUCKET: str = "linscio-registry-1363203425"
    COS_REGION: str = "ap-hongkong"
    # 授权管理优化：公钥签名授权码签发私钥（Ed25519，base64 编码的 32 字节或 PEM），不设则心跳不返回 signed_token
    LINSCIO_LICENSE_PRIVATE_KEY: str = ""
    # MedComm v3：学科包 manifest 在 COS 中的 key（可选，未配置则更新检查不返回学科包远端版本）
    MEDCOMM_SPECIALTY_MANIFEST_KEY: str = "specialties/manifest.json"
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception:
            return ["http://localhost:3000", "http://localhost:3001"]

    class Config:
        env_file = ".env"
        extra = "ignore"


import os
if os.environ.get("APP_ENTRY") == "registry_proxy":
    from app.config_proxy import proxy_settings
    settings = proxy_settings
else:
    settings = Settings()

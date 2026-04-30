"""
应用配置 — 双模式支持
通过 DEPLOYMENT_MODE 环境变量切换运行模式：
  - desktop: 本地单用户、SQLite、HMAC token、无积分
  - saas:    云端多租户、PostgreSQL、JWT、积分计费
"""
import os
import secrets
from pathlib import Path

try:
    from dotenv import load_dotenv
    _backend_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_backend_root / ".env")
except ImportError:
    pass

# 数据目录：Electron 打包后由环境变量注入；开发时默认用项目内 .data
_dev_data = Path(__file__).resolve().parent.parent.parent / ".data"
APP_DATA_ROOT = os.environ.get("LINSCIO_APP_DATA", str(_dev_data))
DB_PATH = os.path.join(APP_DATA_ROOT, "medcomm.db")


def _ensure_data_dir():
    Path(APP_DATA_ROOT).mkdir(parents=True, exist_ok=True)


def _load_or_create_auth_secret() -> str:
    """优先环境变量；否则在数据目录持久化生成一次。"""
    env = os.environ.get("LINSCIO_AUTH_SECRET")
    if env:
        return env
    try:
        _ensure_data_dir()
        p = Path(APP_DATA_ROOT) / ".auth_secret"
        if p.exists():
            val = p.read_text(encoding="utf-8").strip()
            if val:
                return val
        val = secrets.token_urlsafe(48)
        p.write_text(val, encoding="utf-8")
        try:
            p.chmod(0o600)
        except OSError:
            pass
        return val
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "无法读写 .auth_secret，使用临时随机密钥（本次进程有效）"
        )
        return secrets.token_urlsafe(48)


class Settings:
    """全局设置"""
    # ── 运行模式 ──────────────────────────────────────────
    deployment_mode: str = os.environ.get("DEPLOYMENT_MODE", "desktop")
    debug: bool = os.environ.get("DEBUG", "0") == "1"

    # ── 桌面端数据目录 ──────────────────────────────────────
    app_data_root: str = APP_DATA_ROOT
    db_path: str = DB_PATH

    # ── 数据库（按模式自动选择）──────────────────────────────
    @property
    def database_url(self) -> str:
        if self.deployment_mode == "desktop":
            return f"sqlite+aiosqlite:///{self.db_path}"
        return os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://medcomm:changeme@127.0.0.1:5432/medcomm",
        )

    db_pool_size: int = int(os.environ.get("DB_POOL_SIZE", "10"))
    db_max_overflow: int = int(os.environ.get("DB_MAX_OVERFLOW", "10"))

    # ── Redis（SaaS 必需，桌面端自动用内存 stub）───────────────
    redis_url: str = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_lock_db: int = 1
    redis_sse_db: int = 2
    redis_jwt_blacklist_db: int = 3
    redis_rate_limit_db: int = 4

    # ── 认证 ─────────────────────────────────────────────────
    # 桌面端 HMAC
    auth_secret: str = _load_or_create_auth_secret()
    # JWT（桌面端未配置时复用 auth_secret）
    jwt_secret: str = os.environ.get("JWT_SECRET", "") or _load_or_create_auth_secret()
    jwt_private_key: str = os.environ.get("JWT_PRIVATE_KEY", "")
    jwt_public_key: str = os.environ.get("JWT_PUBLIC_KEY", "")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    jwt_access_expire_seconds: int = 7 * 86400
    jwt_refresh_expire_seconds: int = 30 * 86400

    # ── NCBI ─────────────────────────────────────────────────
    ncbi_api_key: str | None = os.environ.get("LINSCIO_NCBI_API_KEY") or None

    # ── LLM API Keys ─────────────────────────────────────────
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    openai_base_url: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # ── GPT Image（独立于文本 LLM，可用不同 API 代理）────────
    gpt_image_api_key: str = os.environ.get("GPT_IMAGE_API_KEY", "")
    gpt_image_base_url: str = os.environ.get("GPT_IMAGE_BASE_URL", "")
    gpt_image_model: str = os.environ.get("GPT_IMAGE_MODEL", "gpt-image-2-plus")

    # ── 积分业务 ─────────────────────────────────────────────
    new_user_gift_credits: int = 3
    gift_credits_validity_days: int = 30
    promo_credits_validity_months: int = 6
    promo_cash_rate: float = 0.10
    promo_min_withdraw: int = 100

    # ── 易支付 ─────────────────────────────────────────────────
    yipay_pid: str = os.environ.get("YIPAY_PID", "")
    yipay_key: str = os.environ.get("YIPAY_KEY", "")
    yipay_gateway: str = os.environ.get("YIPAY_GATEWAY", "https://zpayz.cn")
    yipay_notify_url: str = os.environ.get("YIPAY_NOTIFY_URL", "")
    yipay_return_url: str = os.environ.get("YIPAY_RETURN_URL", "")

    # ── 支付宝直连（预留）───────────────────────────────────────
    alipay_app_id: str = os.environ.get("ALIPAY_APP_ID", "")
    alipay_private_key: str = os.environ.get("ALIPAY_PRIVATE_KEY", "")
    alipay_public_key: str = os.environ.get("ALIPAY_PUBLIC_KEY", "")
    alipay_notify_url: str = os.environ.get("ALIPAY_NOTIFY_URL", "")
    alipay_return_url: str = os.environ.get("ALIPAY_RETURN_URL", "")

    # ── 微信支付直连（预留）───────────────────────────────────────
    wechat_mch_id: str = os.environ.get("WECHAT_MCH_ID", "")
    wechat_api_key: str = os.environ.get("WECHAT_API_KEY", "")
    wechat_cert_path: str = os.environ.get("WECHAT_CERT_PATH", "")
    wechat_key_path: str = os.environ.get("WECHAT_KEY_PATH", "")
    wechat_notify_url: str = os.environ.get("WECHAT_NOTIFY_URL", "")

    # ── 订单超时（分钟）───────────────────────────────────────
    order_expire_minutes: int = int(os.environ.get("ORDER_EXPIRE_MINUTES", "30"))

    # ── 腾讯云 COS（客户端下载）──────────────────────────────
    cos_region: str = os.environ.get("COS_REGION", "ap-guangzhou")
    cos_secret_id: str = os.environ.get("COS_SECRET_ID", "")
    cos_secret_key: str = os.environ.get("COS_SECRET_KEY", "")
    cos_bucket_releases: str = os.environ.get("COS_BUCKET_RELEASES", "linscio-releases-1234567890")
    cos_bucket_manifest: str = os.environ.get("COS_BUCKET_MANIFEST", "")  # 留空则与 releases 同桶

    # ── 可观测性 ──────────────────────────────────────────────
    alert_wechat_webhook: str = os.environ.get("ALERT_WECHAT_WEBHOOK", "")
    sentry_dsn: str = os.environ.get("SENTRY_DSN", "")

    # ── SaaS 远程 API（桌面端登录验证用）──────────────────────
    saas_api_url: str = os.environ.get("SAAS_API_URL", "https://www.linscio.com")

    # ── 前端站点 URL（推广链接等，开发时可指向 Vite 端口）─────
    @property
    def site_url(self) -> str:
        return os.environ.get("SITE_URL", self.saas_api_url)

    # ── 门户 ─────────────────────────────────────────────────
    @property
    def portal_api_url(self) -> str:
        return os.environ.get("LINSCIO_PORTAL_API_URL", "http://127.0.0.1:8001")

    def get_default_model(self) -> str | None:
        return os.environ.get("MEDCOMM_DEFAULT_MODEL") or None


settings = Settings()


# ── 模式判断辅助函数 ─────────────────────────────────────────
def is_desktop() -> bool:
    return settings.deployment_mode == "desktop"

def is_saas() -> bool:
    return settings.deployment_mode != "desktop"

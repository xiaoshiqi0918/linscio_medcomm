"""应用配置"""
import os
import secrets
from pathlib import Path

# 数据目录：Electron 打包后由环境变量注入；开发时默认用项目内 .data
_dev_data = Path(__file__).resolve().parent.parent.parent / ".data"
APP_DATA_ROOT = os.environ.get(
    "LINSCIO_APP_DATA",
    str(_dev_data),
)

# 数据库路径
DB_PATH = os.path.join(APP_DATA_ROOT, "medcomm.db")

# 确保数据目录存在（延迟创建，避免 import 时权限问题）
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
        return val
    except Exception:
        # 兜底：开发环境默认值（不推荐生产使用）
        return "linscio-dev-secret"


class Settings:
    """全局设置"""
    app_data_root: str = APP_DATA_ROOT
    db_path: str = DB_PATH
    debug: bool = os.environ.get("DEBUG", "0") == "1"
    ncbi_api_key: str | None = os.environ.get("LINSCIO_NCBI_API_KEY") or None
    auth_secret: str = _load_or_create_auth_secret()

    def get_default_model(self) -> str | None:
        """全局默认模型（可被 DB 覆盖）"""
        return os.environ.get("MEDCOMM_DEFAULT_MODEL") or None

    @property
    def portal_api_url(self) -> str:
        """门户 API 根地址（授权校验、心跳等），本地/云端通过环境变量切换"""
        return os.environ.get(
            "LINSCIO_PORTAL_API_URL",
            "http://127.0.0.1:8001",
        )


settings = Settings()

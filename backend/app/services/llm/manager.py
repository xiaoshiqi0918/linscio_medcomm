"""
LLM 管理器
模型优先级：用户 DB 设置 > 环境变量 > 文章级 > model_hint 系统推荐 > 第一个有 Key 的模型
支持国内主流大模型：智谱 GLM、通义千问、月之暗面 Kimi、深度求索、硅基流动等
"""
import logging
import os
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# 系统推荐模型（OpenAI / Anthropic / 国内）
MODEL_HINTS = {
    # OpenAI
    "default": "gpt-4o-mini",
    "quality": "gpt-4o",
    "fast": "gpt-4o-mini",
    "claude": "claude-3-5-sonnet-20241022",
    # 国内大模型
    "zhipu": "glm-4-flash",
    "qwen": "qwen-turbo",
    "moonshot": "moonshot-v1-8k",
    "deepseek": "deepseek-chat",
    "siliconflow": "Qwen/Qwen2.5-7B-Instruct",
}

# 国内大模型 → (base_url, api_key_env)
# 使用 OpenAI 兼容接口，仅需 base_url + api_key 即可调用
DOMESTIC_PROVIDERS = {
    # 智谱 GLM
    "glm-4": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "glm-4-flash": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "glm-4-plus": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "glm-4-air": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "glm-3-turbo": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    # 通义千问（阿里云百炼）
    "qwen-turbo": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "qwen-plus": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "qwen-max": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "qwen-long": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    # 月之暗面 Kimi
    "moonshot-v1-8k": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "moonshot-v1-32k": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "moonshot-v1-128k": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    # 深度求索
    "deepseek-chat": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "deepseek-coder": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "deepseek-reasoner": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    # 硅基流动（聚合多模型）
    "Qwen/Qwen2.5-7B-Instruct": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen2.5-72B-Instruct": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen2.5-32B-Instruct": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "deepseek-ai/DeepSeek-V2.5": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "deepseek-ai/DeepSeek-V3": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "deepseek-ai/DeepSeek-R1": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "THUDM/glm-4-9b-chat": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "THUDM/glm-4-plus": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    # OpenRouter（聚合）
    "openrouter/openai/gpt-4o-mini": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/openai/gpt-4o": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/anthropic/claude-3.5-sonnet": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/anthropic/claude-3.7-sonnet": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/anthropic/claude-3.7-sonnet:thinking": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/anthropic/claude-3.5-haiku": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/google/gemini-2.0-flash-001": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/google/gemini-2.5-flash": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/google/gemini-2.5-pro": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/google/gemini-1.5-pro": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/google/gemini-1.5-flash": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/meta-llama/llama-3.1-70b-instruct": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/meta-llama/llama-3.1-405b-instruct": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/deepseek/deepseek-r1": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/deepseek/deepseek-v3": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    # 七牛 MaaS（OpenAI 兼容，base_url 可通过环境变量覆盖）
    "qiniu/deepseek-v3": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/deepseek-r1": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/qwen2.5-72b-instruct": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/qwen2.5-32b-instruct": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/glm-4-plus": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
}

DEFAULT_MODEL = "gpt-4o-mini"

# ── 用户全局默认模型（内存缓存，由 API 层写入） ──────────────────────────
_user_default_model: str = ""


def set_user_default_model(model: str) -> None:
    """由 system API 调用，将用户选择的模型写入内存缓存。"""
    global _user_default_model
    _user_default_model = (model or "").strip()


def get_user_default_model() -> str:
    return _user_default_model


async def load_user_default_model_from_db(user_id: int = 1) -> None:
    """从 DB 加载指定用户配置的默认模型到内存缓存。"""
    global _user_default_model
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.user_settings import UserSettingService
        async with AsyncSessionLocal() as db:
            val = await UserSettingService.get(db, user_id, "default_model", default="")
            if val:
                _user_default_model = val
    except Exception:
        pass


def _model_has_key(model: str) -> bool:
    """检查模型是否有可用的 API Key（不实际创建客户端）。"""
    if model in DOMESTIC_PROVIDERS:
        _, env_key = DOMESTIC_PROVIDERS[model]
        return bool(os.environ.get(env_key, "").strip())
    if "/" in model and os.environ.get("SILICONFLOW_API_KEY", "").strip():
        return True
    if model.startswith("claude-"):
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _find_any_available_model() -> str | None:
    """扫描 DOMESTIC_PROVIDERS，返回第一个配置了 API Key 的模型 id；无则返回 None。"""
    preferred_order = [
        "deepseek-chat", "glm-4-flash", "qwen-turbo", "moonshot-v1-8k",
    ]
    for m in preferred_order:
        if m in DOMESTIC_PROVIDERS:
            _, env_key = DOMESTIC_PROVIDERS[m]
            if os.environ.get(env_key, "").strip():
                return m
    for m, (_, env_key) in DOMESTIC_PROVIDERS.items():
        if os.environ.get(env_key, "").strip():
            return m
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return "claude-3-5-sonnet-20241022"
    return None


def get_domestic_base_url(model: str) -> tuple[str | None, str | None]:
    """
    若 model 为国内大模型，返回 (base_url, api_key)；否则返回 (None, None)
    """
    if model in DOMESTIC_PROVIDERS:
        base_url, env_key = DOMESTIC_PROVIDERS[model]
        if base_url == "QINIU_MAAS":
            base_url = os.environ.get("QINIU_MAAS_BASE_URL", "https://api.qnaigc.com/v1")
        key = os.environ.get(env_key, "")
        if key:
            return base_url, key
    # 硅基流动：Provider/Model 格式的模型名
    if "/" in model and os.environ.get("SILICONFLOW_API_KEY"):
        return "https://api.siliconflow.cn/v1", os.environ.get("SILICONFLOW_API_KEY")
    return None, None


async def resolve_model(
    article_id: Optional[int] = None,
    article_default_model: Optional[str] = None,
    model_hint: str = "default",
) -> str:
    """
    解析最终使用的模型（优先级从高到低）：
    1. 用户 DB 设置（Settings 页面选择，内存缓存 → DB 兜底）
    2. 环境变量 MEDCOMM_DEFAULT_MODEL
    3. 文章级 default_model（创建时保存的快照）
    4. model_hint 系统推荐（仅在有对应 API Key 时使用）
    5. 扫描所有 provider，返回第一个有 Key 的模型
    """
    global _user_default_model
    if _user_default_model:
        return _user_default_model
    if not _user_default_model:
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import select, desc
            from app.models.user_setting import UserSetting
            async with AsyncSessionLocal() as db:
                r = await db.execute(
                    select(UserSetting.value)
                    .where(UserSetting.key == "default_model", UserSetting.value != "")
                    .order_by(desc(UserSetting.id))
                    .limit(1)
                )
                val = r.scalar_one_or_none()
                if val:
                    _user_default_model = val
                    return _user_default_model
        except Exception:
            pass
    env_model = settings.get_default_model()
    if env_model:
        return env_model
    if article_id and article_default_model:
        return article_default_model

    hint_model = MODEL_HINTS.get(model_hint, DEFAULT_MODEL)
    if _model_has_key(hint_model):
        return hint_model

    fallback = _find_any_available_model()
    if fallback:
        logger.info("默认模型 '%s' 无可用 API Key，自动切换到 '%s'", hint_model, fallback)
        return fallback

    raise RuntimeError(
        f"无法找到可用的 LLM 模型：默认模型 '{hint_model}' 无 API Key，"
        f"且未找到任何已配置 Key 的模型。请在设置中配置默认模型及对应的 API Key。"
    )

"""
LLM 管理器
模型优先级：用户 DB 设置 > 环境变量 > 文章级 > model_hint 系统推荐 > 第一个有 Key 的模型
支持国内主流大模型：智谱 GLM、通义千问、月之暗面 Kimi、深度求索、硅基流动等
支持基于任务类型的智能路由：QUALITY / BALANCED / FAST / REASONING
"""
import logging
import os
from enum import Enum
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


# ── 任务分层：调用方声明所需的模型能力等级 ────────────────────────────
class TaskTier(str, Enum):
    QUALITY = "quality"
    BALANCED = "balanced"
    FAST = "fast"
    REASONING = "reasoning"


# ── Provider 内模型分层表 ─────────────────────────────────────────
# 每个 tier 列表按优先级排列，取第一个可用的即可
PROVIDER_MODEL_TIERS: dict[str, dict] = {
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "quality": ["deepseek-chat"],
        "balanced": ["deepseek-chat"],
        "fast": ["deepseek-chat"],
        "reasoning": ["deepseek-reasoner", "deepseek-chat"],
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "quality": ["gpt-4o", "gpt-4o-mini"],
        "balanced": ["gpt-4o-mini"],
        "fast": ["gpt-4o-mini"],
        "reasoning": ["gpt-4o", "gpt-4o-mini"],
    },
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "quality": ["claude-3-5-sonnet-20241022"],
        "balanced": ["claude-3-5-sonnet-20241022"],
        "fast": ["claude-3-5-sonnet-20241022"],
        "reasoning": ["claude-3-5-sonnet-20241022"],
    },
    "gemini": {
        "env_key": "GOOGLE_API_KEY",
        "quality": ["gemini-2.5-pro", "gemini-2.5-flash"],
        "balanced": ["gemini-2.5-flash", "gemini-2.0-flash"],
        "fast": ["gemini-2.0-flash", "gemini-2.5-flash"],
        "reasoning": ["gemini-2.5-pro", "gemini-2.5-flash"],
    },
    "zhipu": {
        "env_key": "ZHIPU_API_KEY",
        "quality": ["glm-4-plus", "glm-4", "glm-4-flash"],
        "balanced": ["glm-4-flash", "glm-4-air"],
        "fast": ["glm-4-flash", "glm-4-air", "glm-3-turbo"],
        "reasoning": ["glm-4-plus", "glm-4"],
    },
    "qwen": {
        "env_key": "DASHSCOPE_API_KEY",
        "quality": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "balanced": ["qwen-plus", "qwen-turbo"],
        "fast": ["qwen-turbo", "qwen-turbo-latest"],
        "reasoning": ["qwen3-235b-a22b", "qwen-max"],
    },
    "moonshot": {
        "env_key": "MOONSHOT_API_KEY",
        "quality": ["kimi-latest", "moonshot-v1-128k"],
        "balanced": ["kimi-latest", "moonshot-v1-32k"],
        "fast": ["moonshot-v1-8k", "kimi-latest"],
        "reasoning": ["kimi-latest"],
    },
    "siliconflow": {
        "env_key": "SILICONFLOW_API_KEY",
        "quality": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"],
        "balanced": ["Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-7B-Instruct"],
        "fast": ["Qwen/Qwen2.5-7B-Instruct", "THUDM/glm-4-9b-chat"],
        "reasoning": ["deepseek-ai/DeepSeek-R1", "deepseek-ai/DeepSeek-V3"],
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "quality": ["openrouter/anthropic/claude-3.7-sonnet", "openrouter/openai/gpt-4o"],
        "balanced": ["openrouter/openai/gpt-4o-mini", "openrouter/google/gemini-2.5-flash"],
        "fast": ["openrouter/openai/gpt-4o-mini", "openrouter/google/gemini-2.0-flash-001"],
        "reasoning": ["openrouter/anthropic/claude-3.7-sonnet:thinking", "openrouter/deepseek/deepseek-r1"],
    },
    "qiniu": {
        "env_key": "QINIU_MAAS_API_KEY",
        "quality": ["qiniu/deepseek-v3", "qiniu/qwen2.5-72b-instruct"],
        "balanced": ["qiniu/deepseek-v3", "qiniu/qwen2.5-32b-instruct"],
        "fast": ["qiniu/qwen2.5-32b-instruct", "qiniu/deepseek-v3"],
        "reasoning": ["qiniu/deepseek-r1", "qiniu/deepseek-v3"],
    },
}

# 跨 Provider 优先级（多 Key 可用时的选择顺序）
PROVIDER_PRIORITY = [
    "deepseek", "openai", "anthropic", "gemini",
    "zhipu", "qwen", "moonshot", "siliconflow", "qiniu", "openrouter",
]

# env_key → provider 名反查表
_ENV_KEY_TO_PROVIDER: dict[str, str] = {
    v["env_key"]: k for k, v in PROVIDER_MODEL_TIERS.items()
}

# 系统推荐模型（OpenAI / Anthropic / 国内）
MODEL_HINTS = {
    # OpenAI
    "default": "gpt-4o-mini",
    "quality": "gpt-4o",
    "fast": "gpt-4o-mini",
    "claude": "claude-3-5-sonnet-20241022",
    # Google
    "gemini": "gemini-2.5-flash",
    # 国内大模型
    "zhipu": "glm-4-flash",
    "qwen": "qwen-turbo",
    "moonshot": "moonshot-v1-8k",
    "kimi": "kimi-latest",
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
    "qwen3-235b-a22b": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "qwen-turbo-latest": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "qwen-plus-latest": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "qwen-max-latest": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    # Google AI Studio（Gemini，OpenAI 兼容端点）
    "gemini-2.5-flash": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GOOGLE_API_KEY"),
    "gemini-2.5-pro": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GOOGLE_API_KEY"),
    "gemini-2.0-flash": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GOOGLE_API_KEY"),
    # 月之暗面 Kimi
    "moonshot-v1-8k": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "moonshot-v1-32k": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "moonshot-v1-128k": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "kimi-latest": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
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
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
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
    "openrouter/meta-llama/llama-4-scout": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    # 七牛 MaaS（OpenAI 兼容，base_url 可通过环境变量覆盖）
    "qiniu/deepseek-v3": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/deepseek-r1": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/qwen2.5-72b-instruct": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/qwen2.5-32b-instruct": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
    "qiniu/glm-4-plus": ("QINIU_MAAS", "QINIU_MAAS_API_KEY"),
}

# 各模型上下文窗口大小（tokens），供前端展示 & 预算分配参考
MODEL_MAX_TOKENS: dict[str, int] = {
    # OpenAI
    "gpt-4o-mini": 128_000,
    "gpt-4o": 128_000,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1": 1_047_576,
    # Anthropic
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    # Google AI Studio
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    # DeepSeek
    "deepseek-chat": 64_000,
    "deepseek-coder": 16_000,
    "deepseek-reasoner": 64_000,
    # Moonshot / Kimi
    "kimi-latest": 131_072,
    "moonshot-v1-8k": 8_192,
    "moonshot-v1-32k": 32_768,
    "moonshot-v1-128k": 131_072,
    # DashScope / Qwen
    "qwen3-235b-a22b": 131_072,
    "qwen-turbo": 131_072,
    "qwen-turbo-latest": 1_000_000,
    "qwen-plus": 131_072,
    "qwen-plus-latest": 131_072,
    "qwen-max": 32_768,
    "qwen-max-latest": 32_768,
    "qwen-long": 10_000_000,
    # 智谱 GLM
    "glm-4": 128_000,
    "glm-4-flash": 128_000,
    "glm-4-plus": 128_000,
    "glm-4-air": 128_000,
    "glm-3-turbo": 128_000,
    # 硅基流动
    "Qwen/Qwen2.5-7B-Instruct": 32_768,
    "Qwen/Qwen2.5-32B-Instruct": 32_768,
    "Qwen/Qwen2.5-72B-Instruct": 32_768,
    "deepseek-ai/DeepSeek-V2.5": 32_768,
    "deepseek-ai/DeepSeek-V3": 64_000,
    "deepseek-ai/DeepSeek-R1": 64_000,
    "THUDM/glm-4-9b-chat": 128_000,
    "THUDM/glm-4-plus": 128_000,
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": 131_072,
    # OpenRouter
    "openrouter/openai/gpt-4o-mini": 128_000,
    "openrouter/openai/gpt-4o": 128_000,
    "openrouter/anthropic/claude-3.5-sonnet": 200_000,
    "openrouter/anthropic/claude-3.7-sonnet": 200_000,
    "openrouter/anthropic/claude-3.7-sonnet:thinking": 200_000,
    "openrouter/anthropic/claude-3.5-haiku": 200_000,
    "openrouter/google/gemini-2.0-flash-001": 1_048_576,
    "openrouter/google/gemini-2.5-flash": 1_048_576,
    "openrouter/google/gemini-2.5-pro": 1_048_576,
    "openrouter/google/gemini-1.5-pro": 2_097_152,
    "openrouter/google/gemini-1.5-flash": 1_048_576,
    "openrouter/meta-llama/llama-3.1-70b-instruct": 131_072,
    "openrouter/meta-llama/llama-3.1-405b-instruct": 131_072,
    "openrouter/deepseek/deepseek-r1": 64_000,
    "openrouter/deepseek/deepseek-v3": 64_000,
    "openrouter/meta-llama/llama-4-scout": 131_072,
    # 七牛 MaaS
    "qiniu/deepseek-v3": 64_000,
    "qiniu/deepseek-r1": 64_000,
    "qiniu/qwen2.5-72b-instruct": 32_768,
    "qiniu/qwen2.5-32b-instruct": 32_768,
    "qiniu/glm-4-plus": 128_000,
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
    """检查模型是否有可用的 API Key（不实际创建客户端）。

    优先精确匹配 DOMESTIC_PROVIDERS，失败后按前缀推断 Provider。
    """
    if model in DOMESTIC_PROVIDERS:
        _, env_key = DOMESTIC_PROVIDERS[model]
        return bool(os.environ.get(env_key, "").strip())
    env_key = _infer_env_key(model)
    return bool(os.environ.get(env_key, "").strip())


def _infer_env_key(model: str) -> str:
    """按前缀推断模型所需的 API Key 环境变量名（用于 DOMESTIC_PROVIDERS 中未列出的新模型）。"""
    if model.startswith("openrouter/"):
        return "OPENROUTER_API_KEY"
    if model.startswith("qiniu/"):
        return "QINIU_MAAS_API_KEY"
    if model.startswith("claude-"):
        return "ANTHROPIC_API_KEY"
    if model.startswith("deepseek-"):
        return "DEEPSEEK_API_KEY"
    if model.startswith("gemini-"):
        return "GOOGLE_API_KEY"
    if model.startswith(("glm-", "GLM-")):
        return "ZHIPU_API_KEY"
    if model.startswith(("qwen-", "qwen")):
        return "DASHSCOPE_API_KEY"
    if model.startswith(("moonshot-", "kimi-")):
        return "MOONSHOT_API_KEY"
    if "/" in model:
        return "SILICONFLOW_API_KEY"
    return "OPENAI_API_KEY"


def _find_any_available_model() -> str | None:
    """扫描所有 Provider，返回第一个配置了 API Key 的模型 id；无则返回 None。"""
    preferred_order = [
        "deepseek-chat", "gemini-2.5-flash", "kimi-latest",
        "glm-4-flash", "qwen-turbo", "moonshot-v1-8k",
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
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "gpt-4o-mini"
    return None


def get_domestic_base_url(model: str) -> tuple[str | None, str | None]:
    """
    若 model 为国内大模型 / 聚合平台，返回 (base_url, api_key)；否则返回 (None, None)。
    优先精确匹配 DOMESTIC_PROVIDERS，失败后按前缀推断。
    """
    if model in DOMESTIC_PROVIDERS:
        base_url, env_key = DOMESTIC_PROVIDERS[model]
        if base_url == "QINIU_MAAS":
            base_url = os.environ.get("QINIU_MAAS_BASE_URL", "https://api.qnaigc.com/v1")
        key = os.environ.get(env_key, "")
        if key:
            return base_url, key
    # 按前缀推断：处理 DOMESTIC_PROVIDERS 中未列出的新模型
    if model.startswith("openrouter/"):
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if key:
            return "https://openrouter.ai/api/v1", key
    elif model.startswith("qiniu/"):
        key = os.environ.get("QINIU_MAAS_API_KEY", "")
        if key:
            base_url = os.environ.get("QINIU_MAAS_BASE_URL", "https://api.qnaigc.com/v1")
            return base_url, key
    elif model.startswith("deepseek-"):
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if key:
            return "https://api.deepseek.com/v1", key
    elif model.startswith("gemini-"):
        key = os.environ.get("GOOGLE_API_KEY", "")
        if key:
            return "https://generativelanguage.googleapis.com/v1beta/openai/", key
    elif model.startswith(("glm-", "GLM-")):
        key = os.environ.get("ZHIPU_API_KEY", "")
        if key:
            return "https://open.bigmodel.cn/api/paas/v4/", key
    elif model.startswith(("qwen-", "qwen")):
        key = os.environ.get("DASHSCOPE_API_KEY", "")
        if key:
            return "https://dashscope.aliyuncs.com/compatible-mode/v1", key
    elif model.startswith(("moonshot-", "kimi-")):
        key = os.environ.get("MOONSHOT_API_KEY", "")
        if key:
            return "https://api.moonshot.cn/v1", key
    elif "/" in model:
        key = os.environ.get("SILICONFLOW_API_KEY", "")
        if key:
            return "https://api.siliconflow.cn/v1", key
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

    # 1) 内存缓存的用户默认模型（需校验 Key 可用性）
    if _user_default_model and _model_has_key(_user_default_model):
        return _user_default_model

    # 2) DB 兜底读取用户设置
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
                    if _model_has_key(val):
                        return val
        except Exception:
            pass

    # 若用户已选模型但 Key 不可用，记录警告
    if _user_default_model and not _model_has_key(_user_default_model):
        logger.warning(
            "用户默认模型 '%s' 的 API Key 不可用，尝试自动回退",
            _user_default_model,
        )

    # 3) 环境变量
    env_model = settings.get_default_model()
    if env_model and _model_has_key(env_model):
        return env_model

    # 4) 文章级默认
    if article_id and article_default_model and _model_has_key(article_default_model):
        return article_default_model

    # 5) model_hint 系统推荐
    hint_model = MODEL_HINTS.get(model_hint, DEFAULT_MODEL)
    if _model_has_key(hint_model):
        return hint_model

    # 6) 扫描所有 provider
    fallback = _find_any_available_model()
    if fallback:
        logger.info("默认模型 '%s' 无可用 API Key，自动切换到 '%s'", hint_model, fallback)
        return fallback

    raise RuntimeError(
        f"无法找到可用的 LLM 模型：默认模型 '{hint_model}' 无 API Key，"
        f"且未找到任何已配置 Key 的模型。请在设置中配置默认模型及对应的 API Key。"
    )


# ── 基于任务类型的智能路由 ─────────────────────────────────────────

def _model_to_provider(model: str) -> str | None:
    """根据模型 ID 反查所属 Provider 名称。

    优先精确匹配 DOMESTIC_PROVIDERS，失败后按前缀推断。
    """
    if model in DOMESTIC_PROVIDERS:
        _, env_key = DOMESTIC_PROVIDERS[model]
        return _ENV_KEY_TO_PROVIDER.get(env_key)
    if model.startswith("openrouter/"):
        return "openrouter"
    if model.startswith("qiniu/"):
        return "qiniu"
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("deepseek-"):
        return "deepseek"
    if model.startswith("gemini-"):
        return "gemini"
    if model.startswith(("glm-", "GLM-")):
        return "zhipu"
    if model.startswith(("qwen-", "qwen")):
        return "qwen"
    if model.startswith(("moonshot-", "kimi-")):
        return "moonshot"
    _OPENAI_PREFIXES = ("gpt-", "o1-", "o3-", "chatgpt-")
    if any(model.startswith(p) for p in _OPENAI_PREFIXES) or model in ("o1", "o3"):
        return "openai"
    if "/" in model:
        return "siliconflow"
    return None


def _adapt_model_for_task(model: str, task: TaskTier) -> str:
    """若模型不适合当前任务层级，返回同 Provider 内更合适的模型。

    仅对 PROVIDER_MODEL_TIERS 中已注册的模型做适配；
    未注册的模型（如用户选了更新的 gpt-4.1）原样返回，不做降级。
    """
    provider = _model_to_provider(model)
    if not provider or provider not in PROVIDER_MODEL_TIERS:
        return model
    info = PROVIDER_MODEL_TIERS[provider]
    tier_models = info.get(task.value, [])
    if model in tier_models:
        return model
    # 仅当模型在该 Provider 的某个已知 tier 中时才做替换
    all_known = set()
    for t in TaskTier:
        all_known.update(info.get(t.value, []))
    if model not in all_known:
        return model
    if tier_models:
        return tier_models[0]
    return model


def _pick_model_from_available_providers(task: TaskTier) -> str | None:
    """按 PROVIDER_PRIORITY 扫描已配置 Key 的 Provider，为指定任务选最佳模型。"""
    for provider in PROVIDER_PRIORITY:
        info = PROVIDER_MODEL_TIERS.get(provider)
        if not info:
            continue
        if not os.environ.get(info["env_key"], "").strip():
            continue
        for model in info.get(task.value, []):
            return model
    return None


async def _get_user_model_from_cache_or_db() -> str:
    """获取用户默认模型（内存缓存 → DB 兜底），不校验 Key。"""
    global _user_default_model
    if _user_default_model:
        return _user_default_model
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
    except Exception:
        pass
    return _user_default_model


async def resolve_model_for_task(
    task: TaskTier = TaskTier.BALANCED,
    article_id: Optional[int] = None,
    article_default_model: Optional[str] = None,
) -> str:
    """
    基于任务类型的智能模型路由（优先级从高到低）：
    1. 用户默认模型 → 同 Provider 内按 task 适配（推理模型自动降级）
    2. 环境变量 MEDCOMM_DEFAULT_MODEL → 同上适配
    3. 文章级 default_model → 同上适配
    4. 按 PROVIDER_PRIORITY 扫描，在最优 Provider 中按 task tier 选模型
    """
    # 1) 用户默认模型
    user_model = await _get_user_model_from_cache_or_db()
    if user_model and _model_has_key(user_model):
        adapted = _adapt_model_for_task(user_model, task)
        if adapted != user_model:
            logger.info(
                "[task-router] %s: '%s' -> '%s' (同 Provider 适配)",
                task.value, user_model, adapted,
            )
        return adapted

    if user_model and not _model_has_key(user_model):
        logger.warning(
            "[task-router] 用户默认模型 '%s' 的 API Key 不可用，尝试自动回退",
            user_model,
        )

    # 2) 环境变量
    env_model = settings.get_default_model()
    if env_model and _model_has_key(env_model):
        return _adapt_model_for_task(env_model, task)

    # 3) 文章级默认
    if article_id and article_default_model and _model_has_key(article_default_model):
        return _adapt_model_for_task(article_default_model, task)

    # 4) 按优先级扫描所有 Provider
    best = _pick_model_from_available_providers(task)
    if best:
        logger.info("[task-router] %s: 自动选择 '%s'", task.value, best)
        return best

    # 兜底：任意有 Key 的模型
    fallback = _find_any_available_model()
    if fallback:
        logger.info("[task-router] %s: 无匹配 tier，回退到 '%s'", task.value, fallback)
        return fallback

    raise RuntimeError(
        "无法找到可用的 LLM 模型：未找到任何已配置 Key 的模型。"
        "请在设置中配置默认模型及对应的 API Key。"
    )

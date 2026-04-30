"""
LLM 管理器
模型优先级：用户 DB 设置 > 环境变量 > 文章级 > model_hint 系统推荐 > 第一个有 Key 的模型
支持国内主流大模型：智谱 GLM、通义千问、月之暗面 Kimi、深度求索、硅基流动等
支持基于任务类型的智能路由：QUALITY / BALANCED / FAST / REASONING
SaaS 专用：按具体任务类型精确路由 + primary/fallback/degraded 三级降级
"""
import logging
import os
import time
from enum import Enum
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


class AllModelsFailedError(RuntimeError):
    """所有候选模型均调用失败"""
    pass


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
        "quality": ["claude-sonnet-4-6", "claude-opus-4-6"],
        "balanced": ["claude-sonnet-4-6", "claude-haiku-4-5"],
        "fast": ["claude-haiku-4-5", "claude-sonnet-4-6"],
        "reasoning": ["claude-opus-4-6", "claude-sonnet-4-6"],
    },
    "gemini": {
        "env_key": "GOOGLE_API_KEY",
        "quality": ["gemini-3.1-pro-preview", "gemini-2.5-flash"],
        "balanced": ["gemini-2.5-flash"],
        "fast": ["gemini-2.5-flash"],
        "reasoning": ["gemini-3.1-pro-preview", "gemini-2.5-flash"],
    },
    "zhipu": {
        "env_key": "ZHIPU_API_KEY",
        "quality": ["glm-4.7", "glm-4-plus", "glm-4-flash"],
        "balanced": ["glm-4-flash", "glm-4.7-flash"],
        "fast": ["glm-4.7-flash", "glm-4-flash"],
        "reasoning": ["glm-4.7", "glm-4-plus"],
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
        "quality": ["kimi-k2.5", "kimi-k2-0905-preview"],
        "balanced": ["kimi-k2.5", "kimi-k2-turbo-preview"],
        "fast": ["kimi-k2-turbo-preview", "kimi-k2.5"],
        "reasoning": ["kimi-k2-thinking", "kimi-k2-thinking-turbo", "kimi-k2.5"],
    },
    "siliconflow": {
        "env_key": "SILICONFLOW_API_KEY",
        "quality": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen3-32B"],
        "balanced": ["Qwen/Qwen3-32B", "Qwen/Qwen2.5-7B-Instruct"],
        "fast": ["Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen3-32B"],
        "reasoning": ["deepseek-ai/DeepSeek-R1", "deepseek-ai/DeepSeek-V3"],
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "quality": ["openrouter/anthropic/claude-sonnet-4.6", "openrouter/openai/gpt-4o"],
        "balanced": ["openrouter/openai/gpt-4o-mini", "openrouter/google/gemini-2.5-flash"],
        "fast": ["openrouter/openai/gpt-4o-mini", "openrouter/google/gemini-2.5-flash"],
        "reasoning": ["openrouter/anthropic/claude-opus-4.6", "openrouter/deepseek/deepseek-r1"],
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

# SaaS 模式下排除 Anthropic/Claude（方案 8.2：仅保留 GPT 和 Gemini + 国内模型）
SAAS_PROVIDER_PRIORITY = [
    "deepseek", "openai", "gemini",
    "zhipu", "qwen", "moonshot", "siliconflow", "qiniu", "openrouter",
]

# ── SaaS 任务精确路由表（8.3）──────────────────────────────────────
# primary → fallback → degraded 三级降级，按具体业务任务类型
SAAS_TASK_ROUTES: dict[str, dict] = {
    # ── 核心生成（高质量）───────────────────────────────
    "generation_round1": {
        "primary":   "gpt-4o",
        "fallback":  "gemini-3.1-pro-preview",
        "degraded":  "deepseek-chat",
        "task_tier": TaskTier.QUALITY,
    },
    "deai_rewrite_round2": {
        "primary":   "gpt-4o",
        "fallback":  "gemini-3.1-pro-preview",
        "degraded":  "deepseek-chat",
        "task_tier": TaskTier.QUALITY,
    },
    "optimization_round3": {
        "primary":   "gpt-4o",
        "fallback":  "gemini-3.1-pro-preview",
        "degraded":  "deepseek-chat",
        "task_tier": TaskTier.QUALITY,
    },
    "polish": {
        "primary":   "gpt-4o",
        "fallback":  "deepseek-chat",
        "degraded":  "kimi-k2.5",
        "task_tier": TaskTier.QUALITY,
    },
    # ── 文献分析 ────────────────────────────────────────
    "literature_analysis_abstract": {
        "primary":   "kimi-k2.5",
        "fallback":  "deepseek-chat",
        "degraded":  "gpt-4o-mini",
        "task_tier": TaskTier.BALANCED,
    },
    "literature_analysis_fulltext": {
        "primary":   "gemini-3.1-pro-preview",
        "fallback":  "kimi-k2.5",
        "degraded":  "deepseek-chat",
        "task_tier": TaskTier.QUALITY,
    },
    "literature_filter": {
        "primary":   "deepseek-chat",
        "fallback":  "kimi-k2-turbo-preview",
        "degraded":  "gpt-4o-mini",
        "task_tier": TaskTier.FAST,
    },
    # ── 辅助任务（快速/经济）────────────────────────────
    "keyword_generation": {
        "primary":   "deepseek-chat",
        "fallback":  "kimi-k2-turbo-preview",
        "degraded":  "gpt-4o-mini",
        "task_tier": TaskTier.FAST,
    },
    "quality_check": {
        "primary":   "deepseek-chat",
        "fallback":  "kimi-k2-turbo-preview",
        "degraded":  "gpt-4o-mini",
        "task_tier": TaskTier.BALANCED,
    },
    "translation": {
        "primary":   "deepseek-chat",
        "fallback":  "kimi-k2-turbo-preview",
        "degraded":  "gpt-4o-mini",
        "task_tier": TaskTier.FAST,
    },
    "verification": {
        "primary":   "deepseek-chat",
        "fallback":  "kimi-k2-turbo-preview",
        "degraded":  "gpt-4o-mini",
        "task_tier": TaskTier.BALANCED,
    },
    "aigc_detection": {
        "primary":   "deepseek-chat",
        "fallback":  "kimi-k2-turbo-preview",
        "degraded":  "gpt-4o-mini",
        "task_tier": TaskTier.FAST,
    },
}

# ── 工作流分组（SaaS 用户选择 provider 的粒度）─────────────────────
TASK_TYPE_TO_WORKFLOW: dict[str, str] = {
    "generation_round1": "writing",
    "deai_rewrite_round2": "writing",
    "optimization_round3": "writing",
    "verification": "writing",
    "polish": "polish",
    "literature_analysis_abstract": "literature",
    "literature_analysis_fulltext": "literature",
    "literature_filter": "literature",
    "keyword_generation": "auxiliary",
    "translation": "translation",
    "quality_check": "auxiliary",
    "aigc_detection": "auxiliary",
}

WORKFLOW_DEFAULTS: dict[str, str] = {
    "writing": "deepseek",
    "polish": "deepseek",
    "literature": "deepseek",
    "translation": "deepseek",
    "auxiliary": "deepseek",
}

WORKFLOW_LABELS: dict[str, str] = {
    "writing": "文章写作",
    "polish": "内容润色 / AI 助手",
    "literature": "文献研究",
    "translation": "翻译",
    "auxiliary": "辅助功能",
}

PROVIDER_LABELS: dict[str, str] = {
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "qwen": "通义千问",
    "moonshot": "Moonshot / Kimi",
    "zhipu": "智谱 GLM",
    "siliconflow": "硅基流动",
    "qiniu": "七牛 MaaS",
    "openrouter": "OpenRouter",
    "anthropic": "Anthropic / Claude",
}


def _get_provider_models_for_tier(provider: str, tier: TaskTier) -> list[str]:
    """从 PROVIDER_MODEL_TIERS 中按 provider + tier 返回有 key 的模型列表。"""
    info = PROVIDER_MODEL_TIERS.get(provider)
    if not info:
        return []
    env_key = info.get("env_key", "")
    if not os.environ.get(env_key, "").strip():
        return []
    models = info.get(tier.value, [])
    return [m for m in models if _model_has_key(m)]


def get_available_providers() -> list[dict]:
    """返回 SaaS 可选项内全部服务商（含中文名），无论是否已配置 API Key。"""
    out: list[dict] = []
    for p in SAAS_PROVIDER_PRIORITY:
        info = PROVIDER_MODEL_TIERS.get(p)
        if not info:
            continue
        env_key = info.get("env_key", "")
        configured = bool(os.environ.get(env_key, "").strip())
        out.append({
            "id": p,
            "label": PROVIDER_LABELS.get(p, p),
            "configured": configured,
        })
    return out


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
    "claude": "claude-sonnet-4-6",
    # Google
    "gemini": "gemini-2.5-flash",
    # 国内大模型
    "zhipu": "glm-4-flash",
    "qwen": "qwen-turbo",
    "moonshot": "kimi-k2-turbo-preview",
    "kimi": "kimi-k2.5",
    "deepseek": "deepseek-chat",
    "siliconflow": "Qwen/Qwen2.5-7B-Instruct",
}

# 国内大模型 → (base_url, api_key_env)
# 使用 OpenAI 兼容接口，仅需 base_url + api_key 即可调用
DOMESTIC_PROVIDERS = {
    # 智谱 GLM
    "glm-4.7": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "glm-4.7-flash": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "glm-4-flash": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "glm-4-plus": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
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
    "gemini-3.1-pro-preview": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GOOGLE_API_KEY"),
    # 月之暗面 Kimi
    "kimi-k2.5": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "kimi-k2-0905-preview": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "kimi-k2-turbo-preview": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "kimi-k2-thinking": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "kimi-k2-thinking-turbo": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "kimi-k2-0711-preview": ("https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    # 深度求索
    "deepseek-chat": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "deepseek-coder": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "deepseek-reasoner": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    # 硅基流动（聚合多模型）
    "Qwen/Qwen3-32B": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen2.5-7B-Instruct": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "deepseek-ai/DeepSeek-V3": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "deepseek-ai/DeepSeek-R1": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    # OpenRouter（聚合）
    "openrouter/openai/gpt-4o-mini": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/openai/gpt-4o": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/anthropic/claude-sonnet-4.6": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/anthropic/claude-opus-4.6": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/anthropic/claude-haiku-4.5": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/google/gemini-2.5-flash": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openrouter/google/gemini-3.1-pro-preview": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
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
    "claude-sonnet-4-6": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
    # Google AI Studio
    "gemini-2.5-flash": 1_048_576,
    "gemini-3.1-pro-preview": 1_048_576,
    # DeepSeek
    "deepseek-chat": 64_000,
    "deepseek-coder": 16_000,
    "deepseek-reasoner": 64_000,
    # Moonshot / Kimi
    "kimi-k2.5": 262_144,
    "kimi-k2-0905-preview": 262_144,
    "kimi-k2-turbo-preview": 262_144,
    "kimi-k2-thinking": 131_072,
    "kimi-k2-thinking-turbo": 262_144,
    "kimi-k2-0711-preview": 131_072,
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
    "glm-4.7": 205_000,
    "glm-4.7-flash": 205_000,
    "glm-4-flash": 128_000,
    "glm-4-plus": 128_000,
    # 硅基流动
    "Qwen/Qwen3-32B": 131_072,
    "Qwen/Qwen2.5-7B-Instruct": 32_768,
    "deepseek-ai/DeepSeek-V3": 164_000,
    "deepseek-ai/DeepSeek-R1": 164_000,
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": 131_072,
    # OpenRouter
    "openrouter/openai/gpt-4o-mini": 128_000,
    "openrouter/openai/gpt-4o": 128_000,
    "openrouter/anthropic/claude-sonnet-4.6": 1_000_000,
    "openrouter/anthropic/claude-opus-4.6": 1_000_000,
    "openrouter/anthropic/claude-haiku-4.5": 200_000,
    "openrouter/google/gemini-2.5-flash": 1_048_576,
    "openrouter/google/gemini-3.1-pro-preview": 1_048_576,
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

# 已废弃模型 → 新模型的自动迁移映射
_DEPRECATED_MODEL_MAP: dict[str, str] = {
    # Moonshot (2025 → 2026)
    "kimi-latest": "kimi-k2.5",
    "moonshot-v1-8k": "kimi-k2-turbo-preview",
    "moonshot-v1-32k": "kimi-k2.5",
    "moonshot-v1-128k": "kimi-k2-0905-preview",
    # Anthropic (retired Oct 2025)
    "claude-3-5-sonnet-20241022": "claude-sonnet-4-6",
    "claude-3-5-haiku-20241022": "claude-haiku-4-5",
    # Gemini (deprecated Feb 2026)
    "gemini-2.0-flash": "gemini-2.5-flash",
    # Zhipu GLM (legacy)
    "glm-4": "glm-4.7",
    "glm-4-air": "glm-4.7-flash",
    "glm-3-turbo": "glm-4.7-flash",
    # SiliconFlow (deprecated March 2026)
    "Qwen/Qwen2.5-32B-Instruct": "Qwen/Qwen3-32B",
    "Qwen/Qwen2.5-72B-Instruct": "Qwen/Qwen3-32B",
    "deepseek-ai/DeepSeek-V2.5": "deepseek-ai/DeepSeek-V3",
    "THUDM/glm-4-9b-chat": "Qwen/Qwen2.5-7B-Instruct",
    "THUDM/glm-4-plus": "Qwen/Qwen3-32B",
    # OpenRouter Claude (retired/expiring)
    "openrouter/anthropic/claude-3.5-sonnet": "openrouter/anthropic/claude-sonnet-4.6",
    "openrouter/anthropic/claude-3.7-sonnet": "openrouter/anthropic/claude-sonnet-4.6",
    "openrouter/anthropic/claude-3.7-sonnet:thinking": "openrouter/anthropic/claude-opus-4.6",
    "openrouter/anthropic/claude-3.5-haiku": "openrouter/anthropic/claude-haiku-4.5",
    # OpenRouter Gemini (deprecated)
    "openrouter/google/gemini-2.0-flash-001": "openrouter/google/gemini-2.5-flash",
    "openrouter/google/gemini-1.5-pro": "openrouter/google/gemini-3.1-pro-preview",
    "openrouter/google/gemini-1.5-flash": "openrouter/google/gemini-2.5-flash",
}


def _migrate_model(model: str) -> str:
    """将废弃模型名映射到新模型名；未命中则原样返回。"""
    return _DEPRECATED_MODEL_MAP.get(model, model)


# ── 用户全局默认模型（内存缓存，由 API 层写入） ──────────────────────────
_user_default_model: str = ""


def set_user_default_model(model: str) -> None:
    """由 system API 调用，将用户选择的模型写入内存缓存。"""
    global _user_default_model
    _user_default_model = _migrate_model((model or "").strip())


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
                _user_default_model = _migrate_model(val)
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
        "deepseek-chat", "gemini-2.5-flash", "kimi-k2.5",
        "glm-4-flash", "qwen-turbo", "kimi-k2-turbo-preview",
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
        return "claude-sonnet-4-6"
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
    user_id: Optional[int] = None,
) -> str:
    """
    解析最终使用的模型。

    SaaS 模式（平台部署 Key）优先级：
      1. 环境变量 MEDCOMM_DEFAULT_MODEL（平台运维配置）
      2. model_hint / 扫描第一个有 Key 的模型

    桌面模式（用户自部署 Key）优先级：
      1. 用户 DB 设置（Settings 页面选择，内存缓存 → DB 兜底）
      2. 环境变量 MEDCOMM_DEFAULT_MODEL
      3. 文章级 default_model
      4. model_hint 系统推荐
      5. 扫描所有 provider，返回第一个有 Key 的模型
    """
    from app.core.config import is_saas

    if is_saas():
        return _resolve_model_saas(model_hint)

    return await _resolve_model_desktop(article_id, article_default_model, model_hint)


def _resolve_model_saas(model_hint: str = "default") -> str:
    """SaaS 模式：平台 .env 中配置的 API Key，用户不可自选 Key（排除 Anthropic）"""
    env_model = settings.get_default_model()
    if env_model and _model_has_key(env_model):
        return env_model

    hint_model = MODEL_HINTS.get(model_hint, DEFAULT_MODEL)
    if _model_has_key(hint_model):
        return hint_model

    best = _pick_saas_model_from_providers(TaskTier.BALANCED)
    if best:
        return best

    fallback = _find_any_available_model()
    if fallback:
        return fallback

    raise RuntimeError(
        "SaaS 平台未配置可用的 LLM 模型，请联系管理员设置 MEDCOMM_DEFAULT_MODEL 及对应 API Key。"
    )


async def _resolve_model_desktop(
    article_id: Optional[int] = None,
    article_default_model: Optional[str] = None,
    model_hint: str = "default",
) -> str:
    """桌面模式：用户自部署 Key，支持用户自选模型"""
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
                    _user_default_model = _migrate_model(val)
                    if _model_has_key(_user_default_model):
                        return _user_default_model
        except Exception:
            pass

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
                _user_default_model = _migrate_model(val)
    except Exception:
        pass
    return _user_default_model


async def resolve_model_for_task(
    task: TaskTier = TaskTier.BALANCED,
    article_id: Optional[int] = None,
    article_default_model: Optional[str] = None,
    user=None,
) -> str:
    """
    基于任务类型的智能模型路由。

    SaaS 模式：平台 Key，仅用 env / provider 扫描。
    若传入 user 且充值积分不足，强制降级为 deepseek-chat。
    桌面模式：用户自有 Key，额外走用户 DB 设置。
    """
    from app.core.config import is_saas

    if is_saas():
        if user and should_downgrade_to_budget(user):
            if _model_has_key(BUDGET_MODEL):
                return BUDGET_MODEL
        return _resolve_task_saas(task)

    return await _resolve_task_desktop(task, article_id, article_default_model)


def _resolve_task_saas(task: TaskTier) -> str:
    """SaaS: 平台统一 Key，按 task tier 选最优模型（排除 Anthropic）"""
    env_model = settings.get_default_model()
    if env_model and _model_has_key(env_model):
        return _adapt_model_for_task(env_model, task)

    best = _pick_saas_model_from_providers(task)
    if best:
        return best

    fallback = _find_any_available_model()
    if fallback:
        return fallback

    raise RuntimeError(
        "SaaS 平台未配置可用的 LLM 模型，请联系管理员设置 MEDCOMM_DEFAULT_MODEL 及对应 API Key。"
    )


async def _resolve_task_desktop(
    task: TaskTier,
    article_id: Optional[int] = None,
    article_default_model: Optional[str] = None,
) -> str:
    """桌面: 用户自有 Key + 模型偏好"""
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

    fallback = _find_any_available_model()
    if fallback:
        logger.info("[task-router] %s: 无匹配 tier，回退到 '%s'", task.value, fallback)
        return fallback

    raise RuntimeError(
        "无法找到可用的 LLM 模型：未找到任何已配置 Key 的模型。"
        "请在设置中配置默认模型及对应的 API Key。"
    )


# ══════════════════════════════════════════════════════════════
#  SaaS 精确任务路由（8.3 / 8.4 / 8.5）
# ══════════════════════════════════════════════════════════════

def resolve_model_for_saas_task(task_type: str) -> list[str]:
    """从 SAAS_TASK_ROUTES 查表，返回 [primary, fallback, degraded] 候选模型列表。

    仅返回有可用 API Key 的模型；若路由表中无此 task_type，
    则回退到通用 _resolve_task_saas 逻辑。
    """
    route = SAAS_TASK_ROUTES.get(task_type)
    if not route:
        tier = TaskTier.BALANCED
        model = _resolve_task_saas(tier)
        return [model]

    candidates = []
    for key in ("primary", "fallback", "degraded"):
        model = route.get(key)
        if model and _model_has_key(model):
            candidates.append(model)

    if candidates:
        return candidates

    tier = route.get("task_tier", TaskTier.BALANCED)
    best = _pick_saas_model_from_providers(tier)
    if best:
        return [best]

    any_model = _find_any_available_model()
    if any_model:
        return [any_model]

    raise AllModelsFailedError(
        f"SaaS 任务 '{task_type}' 无可用模型，请联系管理员配置 API Key。"
    )


# ── 模型 → 积分档位映射（定价分层）──────────────────────────────────
_MODEL_TO_TIER: dict[str, str] = {
    # PRO — 高端模型
    "gpt-4o": "pro",
    "gpt-4o-mini": "standard",
    "gemini-3.1-pro-preview": "pro",
    # STANDARD — 中端模型
    "gemini-2.5-flash": "standard",
    "kimi-k2.5": "standard",
    "kimi-k2-0905-preview": "standard",
    "kimi-k2-turbo-preview": "basic",
    # BASIC — 经济模型
    "deepseek-chat": "basic",
    "deepseek-coder": "basic",
    "deepseek-reasoner": "basic",
    "qwen-plus": "basic",
    "qwen-turbo": "basic",
    "qwen-max": "standard",
    "glm-4-flash": "basic",
    "glm-4-plus": "basic",
    "glm-4.7": "standard",
    "glm-4.7-flash": "basic",
    # 聚合平台 — 按底层模型归类
    "deepseek-ai/DeepSeek-V3": "basic",
    "deepseek-ai/DeepSeek-R1": "basic",
    "Qwen/Qwen3-32B": "basic",
    "Qwen/Qwen2.5-7B-Instruct": "basic",
    "openrouter/openai/gpt-4o": "pro",
    "openrouter/openai/gpt-4o-mini": "standard",
    "openrouter/google/gemini-3.1-pro-preview": "pro",
    "openrouter/google/gemini-2.5-flash": "standard",
    "openrouter/deepseek/deepseek-v3": "basic",
    "openrouter/deepseek/deepseek-r1": "basic",
    "qiniu/deepseek-v3": "basic",
    "qiniu/deepseek-r1": "basic",
    "qiniu/qwen2.5-72b-instruct": "basic",
    "qiniu/qwen2.5-32b-instruct": "basic",
    "qiniu/glm-4-plus": "basic",
}


def get_model_tier(model: str) -> str:
    """返回模型对应的积分档位：basic / standard / pro"""
    return _MODEL_TO_TIER.get(model, "standard")


def get_primary_model_for_task(task_type: str) -> str | None:
    """获取 SAAS_TASK_ROUTES 中某任务的 primary 模型，用于预估费用。"""
    route = SAAS_TASK_ROUTES.get(task_type)
    if route:
        return route.get("primary")
    return None


BUDGET_MODEL = "deepseek-chat"


def should_downgrade_to_budget(user) -> bool:
    """判断是否应降级为预算模型。
    规则：如果用户的充值积分（credits）不足以覆盖本次预估费用，
    则降级为 deepseek-chat，使赠送积分 / 推广积分只消耗最便宜的模型。
    这里用简化阈值：credits <= 0 表示完全依赖赠送/推广积分。
    """
    from decimal import Decimal
    paid = getattr(user, "credits", None) or Decimal("0")
    return paid <= Decimal("0")


def resolve_model_for_saas_task_with_budget(
    task_type: str, user=None, preferred_provider: str | None = None,
) -> list[str]:
    """与 resolve_model_for_saas_task 相同，但额外检查用户积分类型。
    若用户无充值积分（仅赠送/推广积分），强制使用 deepseek-chat。
    preferred_provider 允许用户指定首选服务商，其模型排在候选列表最前。
    """
    if user and should_downgrade_to_budget(user):
        if _model_has_key(BUDGET_MODEL):
            return [BUDGET_MODEL]

    prov = preferred_provider
    if not prov:
        prov = _get_contextvar_preferred_provider(task_type)

    if prov:
        tier = (SAAS_TASK_ROUTES.get(task_type) or {}).get(
            "task_tier", TaskTier.BALANCED
        )
        pref_models = _get_provider_models_for_tier(prov, tier)
        fallbacks = resolve_model_for_saas_task(task_type)
        if pref_models:
            return pref_models + [m for m in fallbacks if m not in pref_models]

    return resolve_model_for_saas_task(task_type)


def _get_contextvar_preferred_provider(task_type: str) -> str | None:
    """从 contextvar 读取当前请求的用户 provider 偏好。"""
    try:
        from app.services.llm.provider_preference import (
            current_preferred_provider,
        )
        overrides = current_preferred_provider.get(None)
        if not overrides:
            return None
        if isinstance(overrides, str):
            return overrides
        if isinstance(overrides, dict):
            workflow = TASK_TYPE_TO_WORKFLOW.get(task_type)
            if workflow:
                return overrides.get(workflow)
        return None
    except Exception:
        return None


def _pick_saas_model_from_providers(task: TaskTier) -> str | None:
    """SaaS 专用：按 SAAS_PROVIDER_PRIORITY 扫描（排除 Anthropic）"""
    for provider in SAAS_PROVIDER_PRIORITY:
        info = PROVIDER_MODEL_TIERS.get(provider)
        if not info:
            continue
        if not os.environ.get(info["env_key"], "").strip():
            continue
        for model in info.get(task.value, []):
            return model
    return None


async def log_llm_call(
    user_id: int,
    task_type: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    status: str = "success",
    error: str | None = None,
    article_id: int | None = None,
    section_id: int | None = None,
    session_id: str | None = None,
    billing_session_id: str | None = None,
    cost_usd: float | None = None,
    cost_credits: float | None = None,
    cost_billable: bool | None = None,
    tokens_in_reported: int | None = None,
    tokens_out_reported: int | None = None,
    meta: dict | None = None,
) -> None:
    """写入 LlmCallLog 埋点（仅 SaaS 模式，静默失败）。

    cost_billable: None → 自动推断（success=True, error=False）。
    tokens_*_reported: API 返回的真实值（优先用于结算）。
    billing_session_id: 未显式传入时自动从 contextvar 获取。
    """
    try:
        from app.core.config import is_saas
        if not is_saas():
            return
        from app.core.database import AsyncSessionLocal
        from app.models.billing import LlmCallLog
        from decimal import Decimal

        if billing_session_id is None:
            try:
                from app.services.billing.dependency import get_billing_session_id
                billing_session_id = get_billing_session_id()
            except Exception:
                pass

        if cost_billable is None:
            cost_billable = (status == "success")

        final_in = tokens_in_reported if tokens_in_reported is not None else tokens_in
        final_out = tokens_out_reported if tokens_out_reported is not None else tokens_out
        token_source = "api" if tokens_in_reported is not None else "estimated"

        provider = _model_to_provider(model)

        if cost_usd is None and final_in + final_out > 0:
            cost_usd = _estimate_cost_usd(model, final_in, final_out)

        async with AsyncSessionLocal() as db:
            db.add(LlmCallLog(
                user_id=user_id,
                article_id=article_id,
                section_id=section_id,
                session_id=session_id,
                billing_session_id=billing_session_id,
                task_type=task_type,
                model=model,
                provider=provider,
                tokens_in=final_in,
                tokens_out=final_out,
                tokens_in_reported=tokens_in_reported,
                tokens_out_reported=tokens_out_reported,
                token_source=token_source,
                latency_ms=latency_ms,
                cost_usd=Decimal(str(cost_usd)) if cost_usd else None,
                cost_credits=Decimal(str(cost_credits)) if cost_credits else None,
                cost_billable=cost_billable,
                status=status,
                error_message=error,
                meta=meta,
            ))
            await db.commit()

        # Prometheus 指标
        try:
            from app.services.observability import record_llm_call
            record_llm_call(
                task_type=task_type, model=model, status=status,
                latency_s=latency_ms / 1000.0, cost_usd=cost_usd or 0,
            )
        except Exception:
            pass
    except Exception as exc:
        logger.debug("log_llm_call 写入失败: %s", exc)


# 各模型每 1M token 的价格（USD），用于成本估算
_MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    # (input_per_1M, output_per_1M)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-3.1-pro-preview": (1.25, 10.00),
    "gemini-2.5-flash": (0.075, 0.30),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "kimi-k2.5": (0.55, 2.00),
    "kimi-k2-turbo-preview": (0.20, 0.60),
    "qwen-plus": (0.80, 2.00),
    "qwen-turbo": (0.30, 0.60),
    "qwen-max": (2.40, 9.60),
    "glm-4-flash": (0.10, 0.10),
    "glm-4.7": (0.50, 0.50),
}


def _estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """根据模型定价估算 USD 成本"""
    pricing = _MODEL_PRICING_PER_1M.get(model)
    if not pricing:
        return 0.0
    input_price, output_price = pricing
    cost = (tokens_in / 1_000_000 * input_price) + (tokens_out / 1_000_000 * output_price)
    return round(cost, 6)

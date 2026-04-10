"""系统 API"""
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.services.user_settings import UserSettingService

from app.services.llm.manager import DOMESTIC_PROVIDERS, MODEL_MAX_TOKENS, set_user_default_model

router = APIRouter()

NCBI_KEY_SETTING = "ncbi_api_key"
S2_KEY_SETTING = "s2_api_key"
DEFAULT_MODEL_SETTING = "default_model"


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class SetNcbiKeyRequest(BaseModel):
    api_key: str = ""


class SetS2KeyRequest(BaseModel):
    api_key: str = ""


class SetDefaultModelRequest(BaseModel):
    model: str = ""


@router.get("/user-settings/summary")
async def get_user_settings_summary(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = user.id
    ncbi = await UserSettingService.get(db, user_id, NCBI_KEY_SETTING, default="")
    s2 = await UserSettingService.get(db, user_id, S2_KEY_SETTING, default="")

    def _mask(k: str) -> str:
        return (k[:3] + "****" + k[-2:]) if len(k) >= 6 else ("****" if k else "")

    return {
        "ncbi_key": {"has_value": bool(ncbi), "masked": _mask(ncbi)},
        "s2_key":   {"has_value": bool(s2),   "masked": _mask(s2)},
    }


@router.get("/user-settings/ncbi-key")
async def get_ncbi_key(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = user.id
    key = await UserSettingService.get(db, user_id, NCBI_KEY_SETTING, default="")
    masked = (key[:3] + "****" + key[-2:]) if len(key) >= 6 else ("****" if key else "")
    return {"has_value": bool(key), "masked": masked}


@router.put("/user-settings/ncbi-key")
async def set_ncbi_key(body: SetNcbiKeyRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = user.id
    key = (body.api_key or "").strip()
    await UserSettingService.set(db, user_id, NCBI_KEY_SETTING, key)
    return {"ok": True}


@router.delete("/user-settings/ncbi-key")
async def clear_ncbi_key(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = user.id
    await UserSettingService.delete(db, user_id, NCBI_KEY_SETTING)
    return {"ok": True}


# ── Semantic Scholar API Key ──────────────────────────────────────────────────

@router.get("/user-settings/s2-key")
async def get_s2_key(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    key = await UserSettingService.get(db, user.id, S2_KEY_SETTING, default="")
    masked = (key[:3] + "****" + key[-2:]) if len(key) >= 6 else ("****" if key else "")
    return {"has_value": bool(key), "masked": masked}


@router.put("/user-settings/s2-key")
async def set_s2_key(body: SetS2KeyRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    key = (body.api_key or "").strip()
    await UserSettingService.set(db, user.id, S2_KEY_SETTING, key)
    return {"ok": True}


@router.delete("/user-settings/s2-key")
async def clear_s2_key(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await UserSettingService.delete(db, user.id, S2_KEY_SETTING)
    return {"ok": True}


# ── Default Model ─────────────────────────────────────────────────────────────

@router.get("/user-settings/default-model")
async def get_default_model(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    model = await UserSettingService.get(db, user.id, DEFAULT_MODEL_SETTING, default="")
    if model:
        set_user_default_model(model)
    return {"model": model}


@router.put("/user-settings/default-model")
async def set_default_model(body: SetDefaultModelRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    model = (body.model or "").strip()
    await UserSettingService.set(db, user.id, DEFAULT_MODEL_SETTING, model)
    set_user_default_model(model)
    return {"ok": True, "model": model}


class TestApiKeyRequest(BaseModel):
    api_key: str = ""
    provider: str = "openai"


@router.get("/health")
async def system_health():
    return {"status": "ok"}


@router.get("/ollama/status")
async def ollama_status():
    """检测 Ollama 是否可用（用于 RAG 向量检索）"""
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
        return {"available": r.status_code == 200}
    except Exception:
        return {"available": False}


@router.get("/self-check")
async def connection_self_check():
    """
    轻量连接自检：Ollama 可达性、常见 LLM/翻译/生图相关环境变量是否已配置。
    不替代真实 API 调用（避免耗额度）；与 POST /apikey/test 配合使用。
    """
    ollama = await ollama_status()
    llm_keys: dict[str, bool] = {
        "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "ZHIPU_API_KEY": bool(os.environ.get("ZHIPU_API_KEY", "").strip()),
        "DASHSCOPE_API_KEY": bool(os.environ.get("DASHSCOPE_API_KEY", "").strip()),
        "MOONSHOT_API_KEY": bool(os.environ.get("MOONSHOT_API_KEY", "").strip()),
        "DEEPSEEK_API_KEY": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
        "SILICONFLOW_API_KEY": bool(os.environ.get("SILICONFLOW_API_KEY", "").strip()),
        "OPENROUTER_API_KEY": bool(os.environ.get("OPENROUTER_API_KEY", "").strip()),
        "QINIU_MAAS_API_KEY": bool(os.environ.get("QINIU_MAAS_API_KEY", "").strip()),
        "GOOGLE_API_KEY": bool(os.environ.get("GOOGLE_API_KEY", "").strip()),
    }
    translate_keys: dict[str, bool] = {
        "DEEPL_API_KEY": bool(os.environ.get("DEEPL_API_KEY", "").strip()),
        "GOOGLE_TRANSLATE_API_KEY": bool(os.environ.get("GOOGLE_TRANSLATE_API_KEY", "").strip()),
        "AZURE_TRANSLATE_KEY": bool(
            os.environ.get("AZURE_TRANSLATE_KEY", "").strip()
            and os.environ.get("AZURE_TRANSLATE_REGION", "").strip()
        ),
    }
    image_keys: dict[str, bool] = {
        "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "STABILITY_API_KEY": bool(os.environ.get("STABILITY_API_KEY", "").strip()),
        "REPLICATE_API_TOKEN": bool(os.environ.get("REPLICATE_API_TOKEN", "").strip()),
    }
    any_llm = any(llm_keys.values())
    translate_dedicated = any(translate_keys.values())
    return {
        "ollama": ollama,
        "llm_env_keys": llm_keys,
        "llm_any_configured": any_llm,
        "translate_env_keys": translate_keys,
        "translate_note": "未配置专用翻译 Key 时将尝试用当前默认 LLM 翻译（需 LLM 可用）",
        "translate_dedicated_configured": translate_dedicated,
        "image_env_keys": image_keys,
        "ollama_embed_model": os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    }


@router.post("/apikey/test")
async def test_api_key(req: TestApiKeyRequest | None = None):
    """测试 API Key 是否有效：支持 OpenAI 及 OpenAI-兼容国内供应商"""
    provider = (req.provider if req and req.provider else "openai").strip().lower()
    key = (req.api_key if req and req.api_key else "") or ""

    PROVIDER_CONFIGS: dict[str, tuple[str, str, str]] = {
        "openai": (os.environ.get("OPENAI_API_KEY", ""), "https://api.openai.com/v1", "gpt-4o-mini"),
        "deepseek": (os.environ.get("DEEPSEEK_API_KEY", ""), "https://api.deepseek.com/v1", "deepseek-chat"),
        "zhipu": (os.environ.get("ZHIPU_API_KEY", ""), "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        "moonshot": (os.environ.get("MOONSHOT_API_KEY", ""), "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        "siliconflow": (os.environ.get("SILICONFLOW_API_KEY", ""), "https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-7B-Instruct"),
        "dashscope": (os.environ.get("DASHSCOPE_API_KEY", ""), "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
        "google_ai": (os.environ.get("GOOGLE_API_KEY", ""), "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash"),
    }
    cfg = PROVIDER_CONFIGS.get(provider)
    if not cfg:
        return {"valid": False, "error": f"不支持的提供商: {provider}"}
    env_key, base_url, model = cfg
    final_key = key or env_key
    if not final_key:
        return {"valid": False, "error": f"未配置 {provider} API Key"}
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=final_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return {"valid": True, "model": resp.model, "provider": provider}
    except Exception as e:
        return {"valid": False, "error": str(e), "provider": provider}


# DOMESTIC_PROVIDERS 中 model_id 不够直观的，映射为用户友好的显示名称
_DISPLAY_NAMES: dict[str, str] = {
    "deepseek-chat": "DeepSeek V3",
    "deepseek-coder": "DeepSeek Coder",
    "deepseek-reasoner": "DeepSeek R1",
    "kimi-latest": "Kimi K2",
    "moonshot-v1-8k": "Moonshot v1 8K",
    "moonshot-v1-32k": "Moonshot v1 32K",
    "moonshot-v1-128k": "Moonshot v1 128K",
    "qwen3-235b-a22b": "Qwen3 235B",
    "qwen-turbo": "Qwen Turbo",
    "qwen-turbo-latest": "Qwen Turbo (Latest)",
    "qwen-plus": "Qwen Plus",
    "qwen-plus-latest": "Qwen Plus (Latest)",
    "qwen-max": "Qwen Max",
    "qwen-max-latest": "Qwen Max (Latest)",
    "qwen-long": "Qwen Long",
    "glm-4": "GLM-4",
    "glm-4-flash": "GLM-4 Flash",
    "glm-4-plus": "GLM-4 Plus",
    "glm-4-air": "GLM-4 Air",
    "glm-3-turbo": "GLM-3 Turbo",
}


def _fmt_tokens(model_id: str) -> int:
    """查找模型的最大上下文 tokens 数。"""
    return MODEL_MAX_TOKENS.get(model_id, 0)


def _model_entry(model_id: str, name: str, provider: str) -> dict:
    t = _fmt_tokens(model_id)
    entry: dict = {"id": model_id, "name": name, "provider": provider}
    if t:
        entry["max_tokens"] = t
    return entry


@router.get("/llm-models")
async def list_llm_models():
    """
    列出可用的 LLM 模型（根据已配置的 API Key），包含 max_tokens 供前端参考。
    """
    available: list[dict] = []
    added_ids: set[str] = set()

    def _add(model_id: str, name: str, provider: str):
        if model_id in added_ids:
            return
        available.append(_model_entry(model_id, name, provider))
        added_ids.add(model_id)

    # OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        _add("gpt-4o-mini", "GPT-4o Mini", "openai")
        _add("gpt-4o", "GPT-4o", "openai")
        _add("gpt-4.1-mini", "GPT-4.1 Mini", "openai")
        _add("gpt-4.1", "GPT-4.1", "openai")
    # Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        _add("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "anthropic")
        _add("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "anthropic")
    # Google AI Studio
    if os.environ.get("GOOGLE_API_KEY"):
        _add("gemini-2.5-flash", "Gemini 2.5 Flash", "google_ai")
        _add("gemini-2.5-pro", "Gemini 2.5 Pro", "google_ai")
        _add("gemini-2.0-flash", "Gemini 2.0 Flash", "google_ai")
    # DOMESTIC_PROVIDERS（跳过已添加的模型，避免重复）
    for model_id, (_, env_key) in DOMESTIC_PROVIDERS.items():
        if model_id in added_ids:
            continue
        if not os.environ.get(env_key):
            continue
        name = _DISPLAY_NAMES.get(model_id) or (model_id.split("/", 1)[1] if "/" in model_id else model_id)
        provider = (
            "openrouter" if model_id.startswith("openrouter/") else
            "qiniu" if model_id.startswith("qiniu/") else
            "siliconflow" if model_id.startswith(("Qwen/", "deepseek-ai/", "THUDM/", "meta-llama/")) else
            "google_ai" if "gemini" in model_id else
            "zhipu" if "glm" in model_id else
            "dashscope" if "qwen" in model_id else
            "moonshot" if ("moonshot" in model_id or "kimi" in model_id) else
            "deepseek" if "deepseek" in model_id else
            "domestic"
        )
        _add(model_id, name, provider)
    return {"models": available}

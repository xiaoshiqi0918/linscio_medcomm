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

from app.services.llm.manager import DOMESTIC_PROVIDERS, MODEL_HINTS, set_user_default_model

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


@router.get("/llm-models")
async def list_llm_models():
    """
    列出可用的 LLM 模型（根据已配置的 API Key）
    国内大模型：智谱 GLM、通义千问、月之暗面 Kimi、深度求索、硅基流动
    """
    available = []
    # OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        available.extend([
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
            {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "provider": "openai"},
            {"id": "gpt-4.1", "name": "GPT-4.1", "provider": "openai"},
        ])
    # Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        available.extend([
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "anthropic"},
        ])
    # 国内大模型
    for model_id, (_, env_key) in DOMESTIC_PROVIDERS.items():
        if os.environ.get(env_key):
            name = model_id.split("/", 1)[1] if "/" in model_id else model_id
            provider = (
                "openrouter" if model_id.startswith("openrouter/") else
                "qiniu" if model_id.startswith("qiniu/") else
                "siliconflow" if model_id.startswith(("Qwen/", "deepseek-ai/", "THUDM/")) else
                "zhipu" if "glm" in model_id else
                "dashscope" if "qwen" in model_id else
                "moonshot" if "moonshot" in model_id else
                "deepseek" if "deepseek" in model_id else
                "domestic"
            )
            available.append({"id": model_id, "name": name, "provider": provider})
    return {"models": available}

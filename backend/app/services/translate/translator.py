"""
翻译服务 — 支持 DeepL / Google Cloud Translation / 微软 Azure Translator，
未配置专用 Key 时自动回退到当前默认 LLM。
"""
import os
from typing import Optional

import httpx

_TIMEOUT = 30.0


# ── 提供商检测 ─────────────────────────────────────────────────────────────

def _available_provider() -> Optional[str]:
    """按优先级返回第一个可用的专用翻译提供商，无则 None（走 LLM 回退）。"""
    if os.environ.get("DEEPL_API_KEY"):
        return "deepl"
    if os.environ.get("GOOGLE_TRANSLATE_API_KEY"):
        return "google"
    if os.environ.get("AZURE_TRANSLATE_KEY") and os.environ.get("AZURE_TRANSLATE_REGION"):
        return "azure"
    return None


# ── DeepL ──────────────────────────────────────────────────────────────────

async def _deepl_translate(text: str, target_lang: str, source_lang: str) -> str:
    key = os.environ["DEEPL_API_KEY"]
    base = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
    lang_map = {"zh": "ZH", "en": "EN", "ja": "JA", "de": "DE", "fr": "FR", "es": "ES", "ko": "KO"}
    tgt = lang_map.get(target_lang, target_lang.upper())
    src = lang_map.get(source_lang, source_lang.upper()) if source_lang else None
    payload: dict = {"text": [text], "target_lang": tgt}
    if src:
        payload["source_lang"] = src
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(
            f"{base}/v2/translate",
            headers={"Authorization": f"DeepL-Auth-Key {key}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["translations"][0]["text"]


# ── Google Cloud Translation v2 ───────────────────────────────────────────

async def _google_translate(text: str, target_lang: str, source_lang: str) -> str:
    key = os.environ["GOOGLE_TRANSLATE_API_KEY"]
    params: dict = {"q": text, "target": target_lang, "key": key, "format": "text"}
    if source_lang:
        params["source"] = source_lang
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(
            "https://translation.googleapis.com/language/translate/v2",
            params=params,
        )
        r.raise_for_status()
        return r.json()["data"]["translations"][0]["translatedText"]


# ── Microsoft Azure Translator ────────────────────────────────────────────

async def _azure_translate(text: str, target_lang: str, source_lang: str) -> str:
    key = os.environ["AZURE_TRANSLATE_KEY"]
    region = os.environ.get("AZURE_TRANSLATE_REGION", "global")
    endpoint = os.environ.get("AZURE_TRANSLATE_ENDPOINT", "https://api.cognitive.microsofttranslator.com")
    params: dict = {"api-version": "3.0", "to": target_lang}
    if source_lang:
        params["from"] = source_lang
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(
            f"{endpoint}/translate",
            params=params,
            headers=headers,
            json=[{"text": text}],
        )
        r.raise_for_status()
        return r.json()[0]["translations"][0]["text"]


# ── LLM 回退 ──────────────────────────────────────────────────────────────

_LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語", "de": "Deutsch", "fr": "Français"}

async def _llm_translate(text: str, target_lang: str, source_lang: str) -> str:
    from app.services.llm.openai_client import chat_completion
    from app.services.llm.manager import TaskTier

    target_name = _LANG_NAMES.get(target_lang, target_lang)
    messages = [
        {
            "role": "system",
            "content": (
                f"You are a professional medical/scientific translator. "
                f"Translate the following text into {target_name}. "
                f"Requirements:\n"
                f"- Faithful translation only, do not add, remove, or explain any content.\n"
                f"- Preserve medical terminology accurately.\n"
                f"- Preserve numbers, units, and proper nouns.\n"
                f"- Output the translation only, no extra commentary."
            ),
        },
        {"role": "user", "content": text},
    ]
    try:
        return await chat_completion(messages, task=TaskTier.FAST)
    except Exception as e:
        raise RuntimeError(
            f"LLM 翻译失败: {e}。"
            f"请确认该模型的 API Key 已配置，或在设置中配置翻译专用 Key（推荐 DeepL）。"
        ) from e


# ── 统一入口 ───────────────────────────────────────────────────────────────

async def translate(
    text: str,
    target_lang: str = "zh",
    source_lang: str = "en",
) -> dict:
    """
    翻译文本，返回 {"text": "...", "provider": "deepl"|"google"|"azure"|"llm"}.
    优先使用专用翻译 API；未配置时回退到默认 LLM。
    """
    if not text or not text.strip():
        return {"text": "", "provider": "none"}

    provider = _available_provider()

    try:
        if provider == "deepl":
            result = await _deepl_translate(text, target_lang, source_lang)
        elif provider == "google":
            result = await _google_translate(text, target_lang, source_lang)
        elif provider == "azure":
            result = await _azure_translate(text, target_lang, source_lang)
        else:
            provider = "llm"
            result = await _llm_translate(text, target_lang, source_lang)
        return {"text": result, "provider": provider or "llm"}
    except Exception as e:
        if provider and provider != "llm":
            try:
                result = await _llm_translate(text, target_lang, source_lang)
                return {"text": result, "provider": "llm", "fallback_reason": str(e)}
            except Exception as e2:
                raise RuntimeError(f"Translation failed: {provider} → {e}; LLM → {e2}")
        raise

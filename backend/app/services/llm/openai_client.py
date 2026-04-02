"""
LLM 客户端 - OpenAI / Anthropic / 国内大模型，支持流式与非流式
国内大模型（智谱、通义、Kimi、深度求索、硅基流动）均走 OpenAI 兼容接口
"""
import os
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.services.llm.manager import get_domestic_base_url


def _strip_provider_prefix(model: str) -> str:
    """OpenRouter 模型名需要去掉 'openrouter/' 前缀，如 openrouter/openai/gpt-4o-mini → openai/gpt-4o-mini"""
    if model.startswith("openrouter/"):
        return model[len("openrouter/"):]
    if model.startswith("qiniu/"):
        return model[len("qiniu/"):]
    return model


def get_client(model: str | None = None) -> AsyncOpenAI:
    """根据 model 选择 API 端点；None 时用默认 OpenAI"""
    if model:
        base_url, api_key = get_domestic_base_url(model)
        if base_url and api_key:
            if "openrouter.ai" in base_url:
                return AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    default_headers={
                        "HTTP-Referer": "https://linscio.medcomm.local",
                        "X-Title": "LinScio MedComm",
                    },
                )
            return AsyncOpenAI(api_key=api_key, base_url=base_url)
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not openai_key:
        raise RuntimeError(
            f"无法为模型 '{model or 'unknown'}' 创建 API 客户端：未找到匹配的 API Key。"
            f"请在设置中配置正确的默认模型，或设置对应的环境变量。"
        )
    return AsyncOpenAI(api_key=openai_key)


def _is_anthropic(model: str) -> bool:
    return model.startswith("claude-")


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    stream: bool = False,
) -> str | AsyncIterator[str]:
    """Chat 补全，自动路由：国内大模型(OpenAI 兼容) / Anthropic / OpenAI。
    model 为 None 时自动调用 resolve_model() 获取用户配置的默认模型。
    """
    if model is None:
        from app.services.llm.manager import resolve_model
        model = await resolve_model()
    if _is_anthropic(model):
        if stream:
            return _anthropic_chat_stream(messages, model)
        return await _anthropic_chat_once(messages, model)
    if stream:
        return _openai_chat_stream(messages, model)
    return await _openai_chat_once(messages, model)


async def _openai_chat_once(
    messages: list[dict],
    model: str,
    ) -> str:
    client = get_client(model)
    api_model = _strip_provider_prefix(model)
    resp = await client.chat.completions.create(model=api_model, messages=messages)
    return resp.choices[0].message.content or ""


async def _openai_chat_stream(
    messages: list[dict],
    model: str,
) -> AsyncIterator[str]:
    client = get_client(model)
    api_model = _strip_provider_prefix(model)
    stream_obj = await client.chat.completions.create(model=api_model, messages=messages, stream=True)
    async for chunk in stream_obj:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def _anthropic_chat_once(
    messages: list[dict],
    model: str,
    ) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic 未安装，请 pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("未配置 ANTHROPIC_API_KEY")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    sys = ""
    msgs = []
    for m in messages:
        if m.get("role") == "system":
            sys = m.get("content", "")
        else:
            msgs.append({"role": m["role"], "content": m.get("content", "")})
    r = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=sys or None,
        messages=msgs,
    )
    return (r.content[0].text if r.content else "") or ""


async def _anthropic_chat_stream(
    messages: list[dict],
    model: str,
) -> AsyncIterator[str]:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic 未安装，请 pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("未配置 ANTHROPIC_API_KEY")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    sys = ""
    msgs = []
    for m in messages:
        if m.get("role") == "system":
            sys = m.get("content", "")
        else:
            msgs.append({"role": m["role"], "content": m.get("content", "")})
    async with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=sys or None,
        messages=msgs,
    ) as stream_obj:
        async for t in stream_obj.text_stream:
            yield t

"""
LLM 客户端 - OpenAI / Anthropic / 国内大模型，支持流式与非流式
国内大模型（智谱、通义、Kimi、深度求索、硅基流动）均走 OpenAI 兼容接口
SaaS 模式支持 call_llm_with_fallback() 三级降级 + 埋点
"""
from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, AsyncIterator

from openai import AsyncOpenAI

from app.services.llm.manager import get_domestic_base_url

if TYPE_CHECKING:
    from app.services.llm.manager import TaskTier

logger = logging.getLogger("uvicorn.error")


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
    task: "TaskTier | None" = None,
    temperature: float | None = None,
    *,
    _log_user_id: int = 0,
    _log_task_type: str = "",
) -> str | AsyncIterator[str]:
    """Chat 补全，自动路由：国内大模型(OpenAI 兼容) / Anthropic / OpenAI。

    优先级：model 显式指定 > task 智能路由 > resolve_model() 通用解析。
    task 为 TaskTier 枚举（从 app.services.llm.manager 导入）。
    temperature: 采样温度，None 时使用 API 默认值。
    _log_user_id / _log_task_type: 埋点字段，非流式调用时自动记录。
    """
    if model is None:
        if task is not None:
            from app.services.llm.manager import resolve_model_for_task
            model = await resolve_model_for_task(task=task)
        else:
            from app.services.llm.manager import resolve_model
            model = await resolve_model()

    if stream:
        if _is_anthropic(model):
            return _anthropic_chat_stream(messages, model, temperature=temperature)
        return _openai_chat_stream(messages, model, temperature=temperature)

    # 非流式：统一计时 + 埋点
    t0 = time.monotonic()
    try:
        if _is_anthropic(model):
            result = await _anthropic_chat_once(messages, model, temperature=temperature)
        else:
            result = await _openai_chat_once(messages, model, temperature=temperature)
        latency = int((time.monotonic() - t0) * 1000)
        tokens_in = sum(len(m.get("content", "")) // 4 for m in messages)
        tokens_out = len(result) // 4
        if _log_task_type:
            from app.services.llm.manager import log_llm_call
            await log_llm_call(
                user_id=_log_user_id,
                task_type=_log_task_type,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency,
                status="success",
            )
        return result
    except Exception as exc:
        latency = int((time.monotonic() - t0) * 1000)
        if _log_task_type:
            from app.services.llm.manager import log_llm_call
            await log_llm_call(
                user_id=_log_user_id,
                task_type=_log_task_type,
                model=model,
                latency_ms=latency,
                status="error",
                error=str(exc),
            )
        raise


async def _openai_chat_once(
    messages: list[dict],
    model: str,
    temperature: float | None = None,
) -> str:
    client = get_client(model)
    api_model = _strip_provider_prefix(model)
    kwargs: dict = {"model": api_model, "messages": messages}
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def _openai_chat_stream(
    messages: list[dict],
    model: str,
    temperature: float | None = None,
) -> AsyncIterator[str]:
    client = get_client(model)
    api_model = _strip_provider_prefix(model)
    kwargs: dict = {"model": api_model, "messages": messages, "stream": True}
    if temperature is not None:
        kwargs["temperature"] = temperature
    stream_obj = await client.chat.completions.create(**kwargs)
    async for chunk in stream_obj:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def _anthropic_chat_once(
    messages: list[dict],
    model: str,
    temperature: float | None = None,
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
    kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "system": sys or None,
        "messages": msgs,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    r = await client.messages.create(**kwargs)
    return (r.content[0].text if r.content else "") or ""


async def _anthropic_chat_stream(
    messages: list[dict],
    model: str,
    temperature: float | None = None,
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
    kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "system": sys or None,
        "messages": msgs,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    async with client.messages.stream(**kwargs) as stream_obj:
        async for t in stream_obj.text_stream:
            yield t


# ══════════════════════════════════════════════════════════════
#  SaaS 专用：带三级降级的 LLM 调用（8.5）
# ══════════════════════════════════════════════════════════════

async def call_llm_with_fallback(
    task_type: str,
    messages: list[dict],
    *,
    user_id: int = 0,
    article_id: int | None = None,
    section_id: int | None = None,
    stream: bool = False,
    temperature: float | None = None,
) -> str | AsyncIterator[str]:
    """带三级降级的 LLM 调用（SaaS 模式专用）。

    从 SAAS_TASK_ROUTES 获取 primary → fallback → degraded 候选列表，
    依次尝试调用，成功则记录埋点返回，全部失败则抛出 AllModelsFailedError。
    """
    from app.services.llm.manager import (
        resolve_model_for_saas_task,
        log_llm_call,
        AllModelsFailedError,
    )

    candidates = resolve_model_for_saas_task(task_type)
    last_error: Exception | None = None

    for model_key in candidates:
        t0 = time.monotonic()
        try:
            if stream:
                result = _streaming_with_log(
                    task_type, model_key, messages,
                    user_id=user_id,
                    article_id=article_id,
                    section_id=section_id,
                    temperature=temperature,
                )
                return result
            else:
                response = await chat_completion(
                    messages=messages,
                    model=model_key,
                    stream=False,
                    temperature=temperature,
                )
                latency = int((time.monotonic() - t0) * 1000)
                await log_llm_call(
                    user_id=user_id,
                    task_type=task_type,
                    model=model_key,
                    latency_ms=latency,
                    status="success",
                    article_id=article_id,
                    section_id=section_id,
                )
                return response
        except Exception as exc:
            latency = int((time.monotonic() - t0) * 1000)
            logger.warning(
                "[fallback] task=%s model=%s failed (%dms): %s",
                task_type, model_key, latency, exc,
            )
            await log_llm_call(
                user_id=user_id,
                task_type=task_type,
                model=model_key,
                latency_ms=latency,
                status="error",
                error=str(exc),
                article_id=article_id,
                section_id=section_id,
            )
            last_error = exc
            continue

    raise AllModelsFailedError(
        f"所有模型均调用失败 (task={task_type}): {last_error}"
    )


async def _streaming_with_log(
    task_type: str,
    model: str,
    messages: list[dict],
    *,
    user_id: int = 0,
    article_id: int | None = None,
    section_id: int | None = None,
    temperature: float | None = None,
) -> AsyncIterator[str]:
    """流式调用包装：在首次 chunk 成功后记录埋点，异常时也记录。"""
    from app.services.llm.manager import log_llm_call

    t0 = time.monotonic()
    try:
        gen = await chat_completion(
            messages=messages,
            model=model,
            stream=True,
            temperature=temperature,
        )
    except Exception as exc:
        latency = int((time.monotonic() - t0) * 1000)
        await log_llm_call(
            user_id=user_id,
            task_type=task_type,
            model=model,
            latency_ms=latency,
            status="error",
            error=str(exc),
            article_id=article_id,
            section_id=section_id,
        )
        raise

    async def _wrapper():
        logged = False
        try:
            async for chunk in gen:
                if not logged:
                    logged = True
                yield chunk
        finally:
            latency = int((time.monotonic() - t0) * 1000)
            await log_llm_call(
                user_id=user_id,
                task_type=task_type,
                model=model,
                latency_ms=latency,
                status="success" if logged else "error",
                article_id=article_id,
                section_id=section_id,
            )

    return _wrapper()

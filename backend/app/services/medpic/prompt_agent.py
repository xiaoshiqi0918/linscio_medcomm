"""
MedPic 智能提示词生成 Agent
- 接受中文/英文主题描述，生成 Stable Diffusion 正/反向提示词
- 自动推荐画风、画幅、场景等参数
- 支持多轮优化（更通俗/更专业/调整细节）
- 使用与文章模块相同的 LLM 基础设施
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from app.services.llm.openai_client import chat_completion
from app.services.llm.manager import resolve_model

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are MedPic Prompt Agent — a specialist in crafting Stable Diffusion prompts \
for **medical & health-education illustrations**.

## Your Task
Given a user description (Chinese or English), produce:
1. **positive** — comma-separated English tags/phrases for the image.
2. **negative** — comma-separated English tags for things to avoid.
3. **params** — recommended generation parameters (JSON object).

## Prompt Crafting Rules
- Always output prompts in **English** regardless of input language.
- Start positive with quality anchors: "masterpiece, best quality, highly detailed, professional".
- Include visual-style keywords matching the recommended style.
- For medical/health topics: add anatomically-relevant, educational, safe descriptors.
- Avoid any term that could be mistaken for a real diagnosis or prescription.
- negative must always include: "nsfw, gore, blood, graphic surgery, horror, \
low quality, blurry, jpeg artifacts, watermark, deformed, bad anatomy, \
extra limbs, mutation, ugly, worst quality, text, signature".
- Append topic-specific negative terms when relevant (e.g., for children: \
"needles, sharp objects, crying child, scary").

## Parameter Recommendation Rules
Return a JSON object with these fields:
- "scene": one of "article", "comic", "card", "poster", "picturebook", "longimage", "ppt".
- "style": one of "medical_illustration", "flat_design", "3d_render", "comic", "picture_book".
- "aspect": one of "1:1", "4:3", "3:4", "16:9", "9:16", "2:1".
- "audience": one of "public", "professional", "children".
- "color_tone": one of "warm", "cool", "neutral".
Choose based on the description context. If uncertain, prefer "article" / "medical_illustration" / "1:1" / "public" / "neutral".

## Output Format
You MUST output ONLY a single JSON object (no markdown fences, no explanation outside the JSON).
The JSON must have exactly these top-level keys:

{"positive": "english prompt tags...", "negative": "english negative tags...", "params": {"scene": "article", "style": "medical_illustration", "aspect": "1:1", "audience": "public", "color_tone": "neutral"}, "explanation": "一两句中文说明"}

Do NOT wrap in ```json``` blocks. Output raw JSON only.
"""

REFINE_SYSTEM_PROMPT = """\
You are MedPic Prompt Agent in refinement mode. The user previously generated \
prompts and now wants adjustments.

You will receive the current positive/negative prompts and the user's refinement request.
Apply the same rules as initial generation.

Refinement shortcuts the user may use:
- "更通俗" / "more accessible" → simplify visual elements, brighter colors, patient-friendly
- "更专业" / "more clinical" → add anatomical accuracy, clinical style, muted colors
- "更儿向" / "child-friendly" → cute, gentle, picture book style, no scary elements
- "去掉文字元素" → add "text, labels, captions, typography" to negative
- "更简洁" → minimalist, flat design, fewer details

You MUST output ONLY a single JSON object (no markdown fences, no explanation outside the JSON).
The JSON must have exactly these top-level keys:

{"positive": "english prompt tags...", "negative": "english negative tags...", "params": {"scene": "article", "style": "medical_illustration", "aspect": "1:1", "audience": "public", "color_tone": "neutral"}, "explanation": "一两句中文说明"}

Do NOT wrap in ```json``` blocks. Output raw JSON only.
"""


def _build_messages(
    description: str,
    specialty: str = "",
    context_hint: str = "",
) -> list[dict]:
    user_parts = []
    if specialty:
        user_parts.append(f"科室/领域: {specialty}")
    user_parts.append(f"描述: {description}")
    if context_hint:
        user_parts.append(f"补充: {context_hint}")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def _build_refine_messages(
    current_positive: str,
    current_negative: str,
    current_params: dict,
    instruction: str,
) -> list[dict]:
    context = (
        f"当前正向提示词:\n{current_positive}\n\n"
        f"当前反向提示词:\n{current_negative}\n\n"
        f"当前参数:\n{json.dumps(current_params, ensure_ascii=False)}\n\n"
        f"用户调整需求: {instruction}"
    )
    return [
        {"role": "system", "content": REFINE_SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]


def _parse_response(raw: str) -> dict:
    """Parse LLM JSON response with aggressive tolerance for markdown, extra text, nested braces."""
    import re
    text = raw.strip()
    logger.debug("[MedPic PromptAgent] Raw LLM response: %s", text[:500])

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*\n?", "", text).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the outermost { ... } block (handles leading/trailing text)
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    pass
                break

    # Last resort: extract fields with regex
    pos_match = re.search(r'"positive"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    neg_match = re.search(r'"negative"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if pos_match and neg_match:
        logger.warning("[MedPic PromptAgent] Fell back to regex extraction")
        return {
            "positive": pos_match.group(1),
            "negative": neg_match.group(1),
            "params": {},
            "explanation": "（LLM 输出格式异常，已自动提取关键字段）",
        }

    logger.error("[MedPic PromptAgent] Cannot parse LLM output: %s", text[:300])
    raise ValueError(f"LLM returned unparseable response: {text[:200]}")


def _normalize_result(result: dict) -> dict:
    """Ensure result has 'positive', 'negative', 'params' keys, tolerating alternate names."""
    for alt in ("positive_prompt", "positive prompt", "pos"):
        if alt in result and "positive" not in result:
            result["positive"] = result.pop(alt)
    for alt in ("negative_prompt", "negative prompt", "neg"):
        if alt in result and "negative" not in result:
            result["negative"] = result.pop(alt)
    if "positive" not in result or "negative" not in result:
        logger.error("[MedPic PromptAgent] Missing fields in: %s", list(result.keys()))
        raise ValueError(f"LLM response missing required fields (got keys: {list(result.keys())})")
    result.setdefault("params", {})
    result.setdefault("explanation", "")
    return result


async def generate_prompt(
    description: str,
    specialty: str = "",
    context_hint: str = "",
) -> dict:
    """Generate positive/negative prompts + recommended params from description."""
    messages = _build_messages(description, specialty, context_hint)
    model = await resolve_model(model_hint="default")
    raw = await chat_completion(messages, model=model, stream=False)
    result = _parse_response(raw)
    return _normalize_result(result)


async def generate_prompt_stream(
    description: str,
    specialty: str = "",
    context_hint: str = "",
) -> AsyncIterator[str]:
    """Stream the prompt generation for real-time display."""
    messages = _build_messages(description, specialty, context_hint)
    model = await resolve_model(model_hint="default")
    stream = await chat_completion(messages, model=model, stream=True)
    async for chunk in stream:
        yield chunk


async def refine_prompt(
    current_positive: str,
    current_negative: str,
    current_params: dict,
    instruction: str,
) -> dict:
    """Refine existing prompts based on user instruction."""
    messages = _build_refine_messages(
        current_positive, current_negative, current_params, instruction,
    )
    model = await resolve_model(model_hint="default")
    raw = await chat_completion(messages, model=model, stream=False)
    result = _parse_response(raw)
    return _normalize_result(result)


async def refine_prompt_stream(
    current_positive: str,
    current_negative: str,
    current_params: dict,
    instruction: str,
) -> AsyncIterator[str]:
    """Stream the refinement for real-time display."""
    messages = _build_refine_messages(
        current_positive, current_negative, current_params, instruction,
    )
    model = await resolve_model(model_hint="default")
    stream = await chat_completion(messages, model=model, stream=True)
    async for chunk in stream:
        yield chunk

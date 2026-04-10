"""
文献分析智能体 - 通读绑定文献，生成结构化分析报告
用于科普写作前置步骤：帮助用户理解文献核心内容，为选题和写作方向提供依据
"""

import json
import logging
import re
from typing import AsyncIterator

logger = logging.getLogger("linscio.literature.analyzer")


ANALYSIS_SYSTEM_PROMPT = """你是一位医学科普写作的文献分析助手。用户将提供若干篇医学文献的摘要和全文片段。

你的任务是**仅基于用户提供的文献内容**，生成一份结构化的分析报告，帮助用户了解文献的核心内容，为后续科普写作做准备。

【最重要原则】
- 所有分析结论、数据和发现必须直接来自用户提供的文献，不得使用你自身训练数据中的知识
- 如果文献内容不足以支撑某个字段，请如实填写"文献中未提及"或留空数组，不要自行补充
- key_data_points 中的每条数据必须能在提供的文献中找到原文依据，source 字段必须是实际的文献标题

请用中文输出以下 JSON 格式（严格遵守，不要输出 JSON 之外的任何内容）：
{
  "research_topic": "文献群的核心研究主题（一句话概括）",
  "key_findings": [
    "关键发现1（必须来自文献原文）",
    "关键发现2",
    "关键发现3"
  ],
  "methodology_summary": "主要研究方法概述（仅基于文献描述）",
  "population": "研究对象/人群描述（仅基于文献描述）",
  "clinical_significance": "临床意义和实际应用价值（仅基于文献结论）",
  "limitations": ["局限性1（文献中明确提到的）", "局限性2"],
  "suggested_topics": [
    "基于文献内容建议的科普选题1",
    "基于文献内容建议的科普选题2",
    "基于文献内容建议的科普选题3"
  ],
  "suggested_audience": "建议的目标受众（public / patient / student / professional 中选一个）",
  "suggested_specialty": "建议的专科领域",
  "key_data_points": [
    {"label": "数据指标", "value": "数据值（必须是文献中的原始数据）", "source": "来源文献标题"}
  ],
  "writing_angles": [
    "可选写作角度/切入点1",
    "可选写作角度/切入点2"
  ]
}"""

# ── 动态预算分配：根据模型上下文窗口和文献数量分配每篇文献的字符预算 ──

_SYSTEM_PROMPT_CHARS = len(ANALYSIS_SYSTEM_PROMPT)
_OUTPUT_RESERVE = 8000
_PROMPT_OVERHEAD = 200
_MAX_TOTAL_PAPER_CHARS = 120000
_MIN_PER_PAPER_CHARS = 2000

_MODEL_CONTEXT_CHARS: dict[str, int] = {
    "gpt-4.1": 900000,
    "gpt-4o": 180000,
    "gpt-4": 180000,
    "gemini-2.5": 900000,
    "gemini": 180000,
    "claude": 280000,
    "deepseek": 90000,
    "qwen": 90000,
    "glm": 90000,
    "kimi": 180000,
    "llama-4": 900000,
    "moonshot": 90000,
}
_DEFAULT_CONTEXT_CHARS = 45000


def _per_paper_budget(model: str | None, num_papers: int) -> int:
    """根据模型上下文和文献数量计算每篇文献可用的字符预算。"""
    context = _DEFAULT_CONTEXT_CHARS
    if model:
        ml = model.lower()
        for prefix, chars in _MODEL_CONTEXT_CHARS.items():
            if prefix in ml:
                context = chars
                break
    available = context - _SYSTEM_PROMPT_CHARS - _OUTPUT_RESERVE - _PROMPT_OVERHEAD
    available = min(available, _MAX_TOTAL_PAPER_CHARS)
    return max(available // max(num_papers, 1), _MIN_PER_PAPER_CHARS)


_MAPREDUCE_THRESHOLD = 3

_PER_PAPER_SYSTEM_PROMPT = """你是一位医学文献精读助手。用户将提供一篇医学文献的摘要和全文片段。

你的任务是**仅基于用户提供的文献内容**，提取该文献的核心信息，生成结构化的单篇分析摘要。

【最重要原则】
- 所有内容必须直接来自用户提供的文献，不得使用你自身训练数据中的知识
- 如果文献内容不足以支撑某个字段，请如实填写"文献中未提及"或留空数组
- key_data_points 中的每条数据必须能在文献中找到原文依据

请用中文输出以下 JSON 格式（严格遵守，不要输出 JSON 之外的任何内容）：
{
  "title": "文献标题",
  "key_findings": ["关键发现1（来自原文）", "关键发现2"],
  "methodology": "研究方法概述",
  "population": "研究对象/人群描述",
  "clinical_significance": "临床意义（来自文献结论）",
  "limitations": ["局限性1（文献中明确提到的）"],
  "key_data_points": [
    {"label": "数据指标", "value": "数据值（文献原始数据）", "source": "本文献标题"}
  ],
  "writing_angles": ["可选科普写作角度/切入点"]
}"""

_SYNTHESIS_SYSTEM_PROMPT = """你是一位医学科普写作的文献综合分析助手。用户将提供多篇文献的**独立分析摘要**（JSON 格式）。

你的任务是将这些独立分析综合为一份统一的结构化报告，帮助用户了解文献群的整体脉络，为后续科普写作做准备。

【最重要原则】
- 所有分析结论、数据和发现必须来自用户提供的各篇文献分析摘要，不得使用你自身训练数据中的知识
- 综合分析时应体现不同文献之间的关联、互补或矛盾之处
- key_data_points 的 source 字段必须是实际的文献标题
- 如果某字段信息不足，请如实填写"文献中未提及"或留空数组

请用中文输出以下 JSON 格式（严格遵守，不要输出 JSON 之外的任何内容）：
{
  "research_topic": "文献群的核心研究主题（一句话概括）",
  "key_findings": [
    "关键发现1（标注来源文献）",
    "关键发现2",
    "关键发现3"
  ],
  "methodology_summary": "主要研究方法概述（综合各篇文献）",
  "population": "研究对象/人群描述（综合各篇文献）",
  "clinical_significance": "临床意义和实际应用价值（综合各篇文献结论）",
  "limitations": ["局限性1", "局限性2"],
  "suggested_topics": [
    "基于文献内容建议的科普选题1",
    "基于文献内容建议的科普选题2",
    "基于文献内容建议的科普选题3"
  ],
  "suggested_audience": "建议的目标受众（public / patient / student / professional 中选一个）",
  "suggested_specialty": "建议的专科领域",
  "key_data_points": [
    {"label": "数据指标", "value": "数据值", "source": "来源文献标题"}
  ],
  "writing_angles": [
    "可选写作角度/切入点1",
    "可选写作角度/切入点2"
  ]
}"""


async def _load_papers_text(paper_ids: list[int], budget_per_paper: int = 6000) -> list[dict]:
    """从数据库加载文献信息和全文片段"""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.literature import LiteraturePaper
    from app.models.paper import PaperChunk

    papers_info: list[dict] = []
    async with AsyncSessionLocal() as db:
        for pid in paper_ids:
            result = await db.execute(
                select(LiteraturePaper).where(LiteraturePaper.id == pid)
            )
            paper = result.scalar_one_or_none()
            if not paper or paper.deleted_at:
                continue

            chunk_result = await db.execute(
                select(PaperChunk)
                .where(PaperChunk.paper_id == pid)
                .order_by(PaperChunk.chunk_index)
            )
            chunks = chunk_result.scalars().all()

            authors_str = ""
            try:
                authors = json.loads(paper.authors) if isinstance(paper.authors, str) else (paper.authors or [])
                authors_str = ", ".join(
                    a.get("name", "") for a in authors[:5] if isinstance(a, dict)
                )
            except Exception:
                pass

            text_parts = [f"### 文献: {paper.title}"]
            text_parts.append(f"作者: {authors_str}")
            text_parts.append(f"期刊: {paper.journal or '未知'} ({paper.year or '未知'})")
            if paper.abstract:
                text_parts.append(f"摘要: {paper.abstract}")

            if chunks:
                meta_and_abstract_len = sum(len(t) for t in text_parts)
                remaining = max(budget_per_paper - meta_and_abstract_len, 0)
                if remaining > 0:
                    full_text = "\n".join(c.chunk_text for c in chunks if c.chunk_text)
                    if full_text:
                        text_parts.append(f"\n全文片段:\n{full_text[:remaining]}")

            papers_info.append({
                "id": pid,
                "title": paper.title,
                "text": "\n".join(text_parts),
            })

    return papers_info


async def _analyze_one_paper(paper_text: str, model: str) -> dict:
    """Map 阶段：非流式调用 LLM 对单篇文献做结构化提取。失败时返回降级结果。"""
    from app.services.llm.openai_client import chat_completion

    messages = [
        {"role": "system", "content": _PER_PAPER_SYSTEM_PROMPT},
        {"role": "user", "content": f"请分析以下文献：\n\n{paper_text}"},
    ]
    try:
        raw = await chat_completion(messages, model=model, stream=False)
        parsed = _try_parse_json(raw)
        if parsed and isinstance(parsed, dict) and "title" in parsed:
            return parsed
        logger.warning("Per-paper analysis returned unparseable JSON, using fallback")
    except Exception as e:
        logger.warning("Per-paper analysis failed: %s", e)
    return {"title": "(解析失败)", "key_findings": [], "methodology": "", "population": "",
            "clinical_significance": "", "limitations": [], "key_data_points": [], "writing_angles": []}


def _try_parse_json(raw: str) -> dict | None:
    """从 LLM 输出中提取第一个 JSON 对象。"""
    try:
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, ValueError):
        pass
    return None


async def analyze_literature_stream(
    paper_ids: list[int],
    topic_hint: str = "",
) -> AsyncIterator[dict]:
    """
    SSE 流式文献分析。
    - 1-2 篇文献：单次调用（快速路径）
    - 3+ 篇文献：MapReduce（逐篇精读 + 综合汇总）
    yield 事件格式: {"type": "start"|"progress"|"paper_start"|"paper_done"|"synthesizing"|"delta"|"report"|"done"|"error", ...}
    """
    from app.services.llm.openai_client import chat_completion
    from app.services.llm.manager import resolve_model_for_task as _resolve, TaskTier

    yield {"type": "start", "message": "正在读取文献内容…"}

    try:
        model = await _resolve(task=TaskTier.QUALITY)
    except Exception as e:
        yield {"type": "error", "message": f"模型初始化失败：{e}"}
        return
    budget = _per_paper_budget(model, len(paper_ids))

    papers_info = await _load_papers_text(paper_ids, budget_per_paper=budget)

    if not papers_info:
        yield {"type": "error", "message": "未找到可分析的文献内容，请确认文献已上传且包含摘要或全文"}
        return

    use_mapreduce = len(papers_info) >= _MAPREDUCE_THRESHOLD
    mode_label = "MapReduce" if use_mapreduce else "单次调用"

    logger.info(
        "Literature analysis: %d papers, model=%s, budget=%d chars/paper, mode=%s",
        len(papers_info), model, budget, mode_label,
    )

    yield {
        "type": "progress",
        "message": f"已加载 {len(papers_info)} 篇文献（模式: {mode_label}），正在进行深度分析…",
        "paper_count": len(papers_info),
    }

    if not use_mapreduce:
        # ── 快速路径：1-2 篇文献，单次 LLM 调用 ──
        combined = "\n\n---\n\n".join(p["text"] for p in papers_info)
        user_prompt = f"请分析以下 {len(papers_info)} 篇文献：\n\n{combined}"
        if topic_hint:
            user_prompt += f"\n\n用户关注的方向: {topic_hint}"

        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        full_response = ""
        try:
            stream = await chat_completion(messages, model=model, stream=True)
            async for token in stream:
                full_response += token
                yield {"type": "delta", "text": token}

            report = _try_parse_report(full_response)
            if report:
                yield {"type": "report", "data": report}
            else:
                yield {"type": "report_text", "text": full_response}

            yield {"type": "done", "message": "文献分析完成"}
        except Exception as e:
            logger.exception("Literature analysis failed: %s", e)
            yield {"type": "error", "message": f"分析失败: {str(e)}"}
        return

    # ── MapReduce 路径：3+ 篇文献，逐篇精读后综合汇总 ──
    total = len(papers_info)
    per_paper_analyses: list[dict] = []

    for idx, paper in enumerate(papers_info, 1):
        yield {
            "type": "paper_start",
            "index": idx,
            "total": total,
            "title": paper["title"],
            "message": f"正在精读第 {idx}/{total} 篇：{paper['title'][:60]}",
        }

        analysis = await _analyze_one_paper(paper["text"], model)
        if not analysis.get("title") or analysis["title"] == "(解析失败)":
            analysis["title"] = paper["title"]
        per_paper_analyses.append(analysis)

        logger.info("Map phase %d/%d done: %s", idx, total, paper["title"][:40])
        yield {
            "type": "paper_done",
            "index": idx,
            "total": total,
            "title": paper["title"],
            "message": f"第 {idx}/{total} 篇分析完成",
        }

    # ── Reduce 阶段：综合汇总 ──
    yield {
        "type": "synthesizing",
        "message": f"正在综合 {total} 篇文献的分析结果…",
    }

    analyses_text = "\n\n---\n\n".join(
        f"### 文献 {i}: {a.get('title', '未知')}\n{json.dumps(a, ensure_ascii=False, indent=2)}"
        for i, a in enumerate(per_paper_analyses, 1)
    )
    synthesis_prompt = f"请综合以下 {total} 篇文献的独立分析摘要，生成统一的分析报告：\n\n{analyses_text}"
    if topic_hint:
        synthesis_prompt += f"\n\n用户关注的方向: {topic_hint}"

    messages = [
        {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": synthesis_prompt},
    ]

    full_response = ""
    try:
        stream = await chat_completion(messages, model=model, stream=True)
        async for token in stream:
            full_response += token
            yield {"type": "delta", "text": token}

        report = _try_parse_report(full_response)
        if report:
            yield {"type": "report", "data": report}
        else:
            yield {"type": "report_text", "text": full_response}

        yield {"type": "done", "message": f"文献分析完成（MapReduce: {total} 篇）"}
    except Exception as e:
        logger.exception("Literature synthesis failed: %s", e)
        yield {"type": "error", "message": f"综合分析失败: {str(e)}"}


def _try_parse_report(raw: str) -> dict | None:
    """从 LLM 输出中尝试提取 JSON 报告"""
    try:
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            data = json.loads(json_match.group())
            if isinstance(data, dict) and "research_topic" in data:
                return data
    except (json.JSONDecodeError, ValueError):
        pass
    return None

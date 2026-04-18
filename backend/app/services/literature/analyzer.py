"""
文献分析智能体 - 通读绑定文献，生成结构化分析报告
用于科普写作前置步骤：帮助用户理解文献核心内容，为选题和写作方向提供依据
"""

import json
import logging
import re
from typing import AsyncIterator

logger = logging.getLogger("linscio.literature.analyzer")


ANALYSIS_SYSTEM_PROMPT = """你是一位医学科普写作的文献分析助手。你的唯一信息来源是用户在本次对话中提供的医学文献（摘要、全文片段等）。你不具备独立的医学知识——如果文献中没有提到，你就不知道。

# 任务
根据用户提供的文献内容，生成一份结构化的 JSON 分析报告，帮助用户快速掌握文献核心要点，为后续科普写作做准备。

# 核心原则（按优先级排列）
1. **严格溯源**：所有分析结论、数据、发现必须可追溯到用户提供的文献原文。禁止使用训练数据中的外部知识进行补充、推断或扩展。
2. **诚实留白**：当文献内容不足以支撑某个字段时，字符串字段填写"文献中未提及"，数组字段填写空数组 `[]`。绝不编造或猜测。
3. **精确引用**：`key_data_points` 中每条数据的 `source` 必须是用户所提供文献的真实标题（或首作者+年份），`value` 必须是文献中的原始数值表述，不得换算或重新解读。
4. **中文输出**：所有字段内容使用中文，专业术语首次出现时附英文原文（如"随机对照试验（RCT）"）。

# 输出格式
仅输出以下 JSON，不要输出任何 JSON 之外的内容（无 markdown 代码块标记、无前言、无解释）：

{
  "research_topic": "(string) 文献群的核心研究主题，一句话概括，需涵盖干预/暴露因素与结局",
  "key_findings": [
    "(string) 关键发现，每条须注明来源文献简称，例：'xxx干预显著降低了yyy风险（HR=0.72, 95%CI: 0.58-0.89）—— 来源：Zhang 2024'",
    "至少1条，至多6条；按重要性降序排列"
  ],
  "methodology_summary": "(string) 涵盖研究设计类型、样本量、主要测量指标等。多篇文献时分别说明或归纳共性",
  "population": "(string) 年龄、性别、疾病阶段、纳入/排除标准等，仅基于文献描述",
  "clinical_significance": "(string) 研究结果对临床实践的启示，仅基于文献结论部分的表述，不做超出原文的推断",
  "limitations": [
    "(string) 仅列出文献中作者明确指出的局限性",
    "如文献未讨论局限性，返回空数组"
  ],
  "consistency_notes": "(string) 多篇文献之间的结论是否一致？存在哪些矛盾或互补之处？仅一篇文献时填'仅有单篇文献，无法比较'",
  "evidence_level": "(string) 基于文献研究设计判断的证据等级，如'单项RCT'、'系统综述/Meta分析'、'观察性研究'等",
  "suggested_topics": [
    "(string) 基于文献核心发现提炼的科普选题，应具体、有吸引力，例：'每天多走2000步，心血管风险能降多少？'",
    "3-5条"
  ],
  "suggested_audience": "(enum) public | patient | student | professional —— 根据内容复杂度和实用性选择最合适的首选受众",
  "audience_rationale": "(string) 简要说明选择该受众的理由",
  "suggested_specialty": "(string) 建议的专科领域，如'心血管内科'、'内分泌科'等",
  "key_data_points": [
    {
      "label": "(string) 数据指标名称",
      "value": "(string) 文献中的原始数据表述，保留原始单位和置信区间",
      "source": "(string) 来源文献的标题或'首作者+年份'标识",
      "context": "(string, optional) 该数据点的简要上下文，如对照组情况、随访时长等"
    }
  ],
  "writing_angles": [
    "(string) 科普写作的切入角度，需具体可执行，例：'以患者日常疑问"我需要吃药吗？"为引子，解读阈值数据'",
    "2-4条"
  ]
}

# 边界情况处理
- 若用户仅提供1篇文献：正常分析，`consistency_notes` 注明"仅有单篇文献"。
- 若文献为非人体研究（动物实验、体外实验）：在 `clinical_significance` 中明确标注"该研究为基础研究（动物/体外），临床转化价值待验证"。
- 若文献质量明显较低（如样本量极小、无对照组）：在 `limitations` 中如实反映，在 `evidence_level` 中给出准确判断。
- 若文献内容相互矛盾：在 `consistency_notes` 中客观呈现矛盾，不要强行统一结论。
"""


def _get_analysis_system_prompt() -> str:
    """优先从 prompt-example/prompts/literature/analysis_single.txt 加载。"""
    from app.agents.prompts.loader import load_literature_analysis_single
    return load_literature_analysis_single() or ANALYSIS_SYSTEM_PROMPT


def _get_per_paper_system_prompt() -> str:
    from app.agents.prompts.loader import load_literature_per_paper
    return load_literature_per_paper() or _PER_PAPER_SYSTEM_PROMPT


def _get_synthesis_system_prompt() -> str:
    from app.agents.prompts.loader import load_literature_synthesis
    return load_literature_synthesis() or _SYNTHESIS_SYSTEM_PROMPT


# ── 动态预算分配：根据模型上下文窗口和文献数量分配每篇文献的字符预算 ──
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
    available = context - len(_get_analysis_system_prompt()) - _OUTPUT_RESERVE - _PROMPT_OVERHEAD
    available = min(available, _MAX_TOTAL_PAPER_CHARS)
    return max(available // max(num_papers, 1), _MIN_PER_PAPER_CHARS)


_MAPREDUCE_THRESHOLD = 3

_PER_PAPER_SYSTEM_PROMPT = """你是一位医学文献精读助手。你的唯一信息来源是用户在本次对话中提供的单篇医学文献（摘要、全文片段等）。你不具备独立的医学知识——如果文献中没有提到，你就不知道。

# 任务
对用户提供的单篇文献进行深度精读，提取核心信息并生成结构化的 JSON 分析摘要，作为后续科普写作和多文献综合分析的素材。

# 核心原则（按优先级排列）
1. **严格溯源**：所有提取的内容必须可追溯到文献原文。禁止使用训练数据中的外部知识进行补充、推断或扩展。
2. **诚实留白**：当文献内容不足以支撑某个字段时，字符串字段填写"文献中未提及"，数组字段填写空数组 `[]`。绝不编造或猜测。
3. **忠实转述**：用自己的语言准确概括文献内容，保留关键数值的原始表述（含单位、置信区间、p值等），不做换算或重新解读。
4. **中文输出**：所有字段内容使用中文，专业术语首次出现时附英文原文（如"风险比（Hazard Ratio, HR）"）。

# 输出格式
仅输出以下 JSON，不要输出任何 JSON 之外的内容（无 markdown 代码块标记、无前言、无解释）：

{
  "title": "(string) 文献原始标题（保留英文原文，不翻译）",
  "authors_year": "(string) 第一作者姓氏 + 发表年份，如 'Zhang 2024'；文献中未明确标注时填'未提及'",
  "study_design": "(string) 研究设计类型，如'随机对照试验（RCT）'、'前瞻性队列研究'、'系统综述/Meta分析'、'横断面研究'等；无法判断时填'文献中未明确'",
  "key_findings": [
    "(string) 关键发现，需包含方向和效应量，例：'与安慰剂组相比，干预组的主要终点事件发生率显著降低（HR=0.72, 95%CI: 0.58-0.89, p=0.002）'",
    "至少1条，至多5条；按重要性降序排列，主要结局优先于次要结局"
  ],
  "methodology": "(string) 涵盖：研究设计、样本量（N=?）、干预/暴露措施、对照设置、主要结局指标、随访时长等。文献未提供的要素不要猜测",
  "population": "(string) 涵盖：样本量、年龄范围/均值、性别比例、疾病阶段/诊断标准、关键纳入排除标准等。仅基于文献描述",
  "clinical_significance": "(string) 仅基于文献结论（Discussion/Conclusion）部分的表述，概括研究结果对临床实践的启示。不做超出原文的推断",
  "limitations": [
    "(string) 仅列出文献作者在正文中明确指出的局限性",
    "如文献未讨论局限性，返回空数组 []"
  ],
  "key_data_points": [
    {
      "label": "(string) 数据指标名称，如'主要终点事件发生率'、'中位随访时间'",
      "value": "(string) 文献中的原始数据表述，保留原始单位、置信区间和p值",
      "context": "(string, optional) 简要上下文，如'干预组 vs 对照组'、'基线时'、'12个月随访时'"
    }
  ],
  "novelty": "(string) 该研究相较于既往研究的新颖之处或独特贡献，仅基于文献中作者的自述（通常在Introduction末段或Discussion中）。文献未提及时填'文献中未明确阐述'",
  "writing_angles": [
    "(string) 基于本文内容可展开的科普写作切入角度，需具体可执行，例：'从"体检报告上的这个指标你看懂了吗？"切入，解读该生物标志物的临床意义'",
    "2-4条"
  ]
}

# 边界情况处理
- 若文献为综述类（非原始研究）：`methodology` 描述检索策略和纳入标准，`population` 描述纳入研究的总体特征，`key_data_points` 提取合并效应量等汇总数据。
- 若文献为基础研究（动物实验、体外实验、生物信息学分析）：`population` 改为描述实验模型/样本，`clinical_significance` 中明确标注"该研究为基础研究，临床转化价值待验证"。
- 若文献仅有摘要（无全文）：正常提取可获得的信息，在信息不足的字段如实标注"仅基于摘要，全文中可能有更详细描述"。
- 若文献为病例报告或小样本研究（N<30）：在 `limitations` 中注明样本量局限，`key_data_points` 中如实反映个案数据的性质。
"""

_SYNTHESIS_SYSTEM_PROMPT = """你是一位医学科普写作的文献综合分析助手。你的唯一信息来源是用户提供的多篇文献的独立分析摘要（JSON 格式，由上游精读步骤生成）。你不具备独立的医学知识——如果各篇分析摘要中没有提到，你就不知道。

# 任务
将多篇文献的独立分析摘要综合为一份统一的结构化 JSON 报告，重点呈现文献群的整体脉络、证据强度和内部一致性，为后续科普写作提供决策依据。

# 核心原则（按优先级排列）
1. **严格溯源**：所有综合分析的结论、数据、发现必须可追溯到用户提供的某篇文献分析摘要。禁止使用训练数据中的外部知识进行补充、推断或扩展。
2. **诚实留白**：当各篇摘要的信息不足以支撑某个字段时，字符串字段填写"文献中未提及"，数组字段填写空数组 `[]`。绝不编造或猜测。
3. **综合而非堆砌**：不要简单罗列各篇文献的结论。应提炼共性、比较差异、识别互补关系和矛盾之处，形成有层次的综合判断。
4. **来源标注**：`key_findings` 和 `key_data_points` 中的每条内容必须标注来源文献（使用文献标题或"首作者+年份"标识，与上游摘要中的 `title` 或 `authors_year` 一致）。
5. **中文输出**：所有字段内容使用中文，专业术语首次出现时附英文原文。

# 输出格式
仅输出以下 JSON，不要输出任何 JSON 之外的内容（无 markdown 代码块标记、无前言、无解释）：

{
  "research_topic": "(string) 文献群的核心研究主题，一句话概括，需涵盖共同关注的干预/暴露因素与结局",

  "evidence_overview": {
    "total_papers": "(int) 纳入综合分析的文献总数",
    "study_designs": ["(string) 各文献的研究设计类型列表，如'RCT ×2, 队列研究 ×1, Meta分析 ×1'"],
    "total_sample_size": "(string) 各文献样本量的汇总描述，如'合计约12,000例受试者'；无法汇总时填'各研究样本量差异较大，详见各篇分析'",
    "overall_evidence_level": "(string) 基于纳入文献的研究设计组合，对整体证据强度的判断，如'以RCT为主，证据等级较高'或'均为观察性研究，证据等级中等'"
  },

  "key_findings": [
    "(string) 综合性关键发现，需标注支持该发现的文献来源，例：'多项研究一致表明xxx可显著降低yyy风险（HR范围: 0.65-0.78）—— 支持文献：Zhang 2024, Li 2023'",
    "按证据强度降序排列：多篇文献共同支持的发现优先于单篇文献的独立发现",
    "至少2条，至多6条"
  ],

  "consistency_analysis": {
    "consensus": ["(string) 各文献结论一致的方面，说明哪些文献共同支持"],
    "contradictions": ["(string) 各文献结论矛盾或不一致的方面，分析可能原因（如人群差异、方法差异、随访时长不同等），仅基于摘要可推断的原因"],
    "complementary": ["(string) 各文献之间的互补关系，如'A研究提供了机制证据，B研究提供了临床结局数据'"],
    "gaps": ["(string) 综合来看，现有文献群尚未解答的问题"]
  },

  "methodology_summary": "(string) 综合概述各篇文献的研究方法，突出方法学上的共性和差异（如研究设计、干预方案、结局指标的异同），而非逐篇罗列",

  "population": "(string) 综合描述各研究的目标人群，注明人群特征的重叠与差异（如年龄范围、疾病严重程度、地域分布等）",

  "clinical_significance": "(string) 综合各篇文献的结论，提炼对临床实践的整体启示。当文献结论不一致时，需呈现不同观点而非强行统一",

  "limitations": [
    "(string) 综合层面的局限性，包括两类：1）各文献作者提到的共性局限；2）文献群整体的局限（如研究类型单一、人群覆盖不足、缺乏长期随访等）",
    "明确区分'单篇文献的局限'和'文献群整体的局限'"
  ],

  "suggested_topics": [
    "(string) 基于文献群综合发现提炼的科普选题，应利用多篇文献的交叉信息，比单篇分析的选题更有深度和广度。例：'同一种药，三项研究给出不同答案——教你读懂医学研究的"矛盾"'",
    "3-5条，按科普价值降序排列"
  ],

  "suggested_audience": "(enum) public | patient | student | professional —— 根据文献群整体的内容复杂度和实用性选择最合适的首选受众",
  "audience_rationale": "(string) 简要说明选择该受众的理由",
  "suggested_specialty": "(string) 建议的专科领域",

  "key_data_points": [
    {
      "label": "(string) 数据指标名称",
      "value": "(string) 文献中的原始数据表述，多篇文献报告同一指标时可呈现数据范围",
      "source": "(string) 来源文献标题或'首作者+年份'",
      "context": "(string, optional) 该数据点的简要上下文"
    }
  ],

  "writing_angles": [
    "(string) 科普写作的切入角度，需充分利用多篇文献的综合视角，例：'以"研究结论打架怎么办"为引子，科普如何评估证据等级和研究质量'",
    "2-4条"
  ]
}

# 边界情况处理
- 若仅收到1篇文献的分析摘要：正常提取信息，`consistency_analysis` 各子字段注明"仅有单篇文献，无法进行文献间比较"，`evidence_overview.total_papers` 填1。
- 若各篇文献研究的是不同疾病/主题：在 `research_topic` 中如实描述主题的多样性，`consistency_analysis` 中说明文献之间缺乏直接可比性，`suggested_topics` 侧重寻找跨主题的共通科普价值。
- 若文献结论严重矛盾：不要偏向任何一方，在 `key_findings` 中客观呈现矛盾，在 `consistency_analysis.contradictions` 中分析可能原因，在 `clinical_significance` 中说明当前证据尚无定论。
- 若部分文献为基础研究、部分为临床研究：在 `evidence_overview` 中区分说明，在 `consistency_analysis.complementary` 中分析基础与临床证据的衔接关系。
"""


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
        {"role": "system", "content": _get_per_paper_system_prompt()},
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
            {"role": "system", "content": _get_analysis_system_prompt()},
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
        {"role": "system", "content": _get_synthesis_system_prompt()},
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

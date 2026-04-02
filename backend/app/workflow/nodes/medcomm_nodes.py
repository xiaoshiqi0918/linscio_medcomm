"""
MedComm 写作图节点实现
"""
from typing import Any
from app.workflow.states import MedCommSectionState
from app.agents.registry import get_agent_for_section, get_skip_flags
from app.services.enhancement.rag_retriever import RAGRetriever
from app.services.enhancement.example_retriever import ExampleRetriever
from app.services.enhancement.term_injector import TermInjector
from app.services.verification.pipeline import run_verification
from app.services.quality import run_auto_quality_checks

_rag = RAGRetriever()
_examples = ExampleRetriever()
_terms = TermInjector()

QUALITY_RETRY_MAX = 2


def mode_detect_node(state: MedCommSectionState) -> MedCommSectionState:
    """入口：根据上下文决定 generate_new 或 generate_continue"""
    # 简化：默认 new；若有 prev_content 可判断 continue
    prev = state.get("generated_content") or state.get("verified_content")
    mode = "generate_continue" if prev else "generate_new"
    return {**state, "next": mode, "generate_mode": "continue" if prev else "new"}


async def retrieve_context_node(state: MedCommSectionState) -> MedCommSectionState:
    """RAG 检索上下文"""
    topic = state.get("topic", "")
    section_type = state.get("section_type", "")
    article_id = state.get("article_id")
    chunks, ollama_unavailable = await _rag.retrieve(
        query=f"{topic} {section_type}",
        article_id=article_id,
        section_type=section_type,
        top_k=3,
    )
    return {**state, "rag_context": chunks, "rag_ollama_unavailable": ollama_unavailable}


def context_check_node(state: MedCommSectionState) -> MedCommSectionState:
    """检查 RAG 是否足够，决定是否检索示例"""
    ctx = state.get("rag_context") or []
    # 始终补示例（可空），再注入术语
    return {**state, "next": "retrieve_examples"}


async def retrieve_examples_node(state: MedCommSectionState) -> MedCommSectionState:
    """Few-shot 示例检索"""
    ex = await _examples.retrieve(
        content_format=state.get("content_format", "article"),
        section_type=state.get("section_type", "intro"),
        target_audience=state.get("target_audience", "public"),
        platform=state.get("platform", "wechat"),
        specialty=state.get("specialty"),
        top_k=2,
    )
    return {**state, "examples": ex, "next": "inject_terms"}


async def inject_terms_node(state: MedCommSectionState) -> MedCommSectionState:
    """术语注入"""
    terms = await _terms.get_terms_for_audience(
        topic=state.get("topic", ""),
        target_audience=state.get("target_audience", "public"),
        specialty=state.get("specialty"),
    )
    return {**state, "domain_terms": terms, "next": "format_route"}


def format_route_node(state: MedCommSectionState) -> MedCommSectionState:
    """按 content_format 选择 Agent，设置 skip 标志"""
    cf = state.get("content_format", "article")
    st = state.get("section_type", "intro")
    agent = get_agent_for_section(cf, st)
    skip_verify, skip_level = get_skip_flags(cf)
    return {
        **state,
        "active_agent": agent.__class__.__name__,
        "skip_verify": skip_verify,
        "skip_level": skip_level,
        "generate_mode": state.get("generate_mode", "new"),
    }


async def generate_new_node(state: MedCommSectionState) -> MedCommSectionState:
    """生成新内容（new 模式）"""
    return await _do_generate(state)


async def generate_continue_node(state: MedCommSectionState) -> MedCommSectionState:
    """续写（continue 模式）"""
    return await _do_generate(state)


async def _do_generate(state: MedCommSectionState) -> MedCommSectionState:
    """统一生成逻辑（Agent 仅 LLM，验证由图节点完成）"""
    agent = get_agent_for_section(
        state.get("content_format", "article"),
        state.get("section_type", "intro"),
    )
    # 图内单独执行 verify/reading_level 节点，此处仅生成
    content, _ = await agent.run(
        state=state,
        rag_context=state.get("rag_context"),
        skip_verify=True,
        skip_level=True,
    )
    return {
        **state,
        "generated_content": content,
        "verified_content": content,
        "verify_report": {},
    }


def quality_check_node(state: MedCommSectionState) -> MedCommSectionState:
    """质量检查：启发式 + 自动化规则 + ACCEPTANCE_CRITERIA，决定 regenerate / verify / save_partial"""
    content = state.get("generated_content", "") or state.get("verified_content", "")
    retry = state.get("retry_count", 0)
    content_format = state.get("content_format", "article")
    section_type = state.get("section_type", "")
    issues = []

    # 过短
    if len(content.strip()) < 50:
        issues.append("content_too_short")
    # 含失败占位
    if "[生成失败" in content or "API Key" in content:
        issues.append("generation_failed")

    # 自动化规则（含 v2.0 开场套话/感谢阅读/图像描述中文）
    auto_result = run_auto_quality_checks(content, content_format, section_type)
    if auto_result.get("has_errors"):
        for e in auto_result.get("errors", [])[:5]:
            issues.append(f"auto_{e['rule']}")

    # 图像描述字段中文：注入 regenerate_hint 指导重新生成
    auto_errors = auto_result.get("errors", [])
    img_desc_errors = [
        e for e in auto_errors
        if e.get("rule") in ("scene_desc中文", "图像描述字段中文", "illustration_desc中文")
    ]
    regenerate_hint = state.get("regenerate_hint", "")
    if img_desc_errors and retry < QUALITY_RETRY_MAX:
        regenerate_hint = (
            "上次输出的图像描述字段（scene_desc/illustration_desc等）包含中文，"
            "这些字段必须完全使用英文。请重新生成，确保所有图像描述字段只使用英文。"
        )

    # ACCEPTANCE_CRITERIA 可执行验收（v2.0）
    from app.agents.prompts.acceptance_checker import AcceptanceChecker

    acceptance_report = AcceptanceChecker().check(
        content,
        content_format,
        target_audience=state.get("target_audience", "public"),
        platform=state.get("platform", "universal"),
    )
    if not acceptance_report.passed:
        for e in acceptance_report.errors:
            issues.append(f"acceptance_{e.rule_name}")
        if not regenerate_hint and acceptance_report.errors:
            regenerate_hint = "请修复以下问题后重新生成：\n" + "\n".join(
                f"[{e.rule_name}] {e.message}" for e in acceptance_report.errors[:3]
            )

    quality_report = {
        **(state.get("quality_report") or {}),
        "auto_errors": auto_result.get("errors", []),
        "auto_warnings": auto_result.get("warnings", []),
        "acceptance_errors": [{"rule": r.rule_name, "message": r.message} for r in acceptance_report.errors],
        "acceptance_warnings": [{"rule": r.rule_name, "message": r.message} for r in acceptance_report.warnings],
        "checklist_key": auto_result.get("checklist_key"),
        "format_specific_checks": auto_result.get("format_specific_checks", ""),
    }

    if issues and retry < QUALITY_RETRY_MAX:
        return {
            **state,
            "next": "regenerate",
            "retry_count": retry + 1,
            "regenerate_hint": regenerate_hint or state.get("regenerate_hint"),
            "quality_report": quality_report,
        }
    if state.get("skip_verify") and state.get("skip_level"):
        return {**state, "next": "save_partial", "quality_report": quality_report}
    return {**state, "next": "verify_medical_claims", "quality_report": quality_report}


async def verify_medical_claims_node(state: MedCommSectionState) -> MedCommSectionState:
    """医学声明核实（skip_verify 时由路由跳过，此处仅做占位符/绝对化检测）"""
    content = state.get("verified_content", state.get("generated_content", ""))
    if state.get("skip_verify"):
        return {**state, "next": "check_reading_level"}
    content, report = await run_verification(
        content=content,
        article_id=state.get("article_id"),
        rag_context=state.get("rag_context", []),
        target_audience=state.get("target_audience", "public"),
        skip_verify=False,  # 执行医学声明核实
        skip_level=True,   # 阅读难度在下一节点
    )
    return {**state, "verified_content": content, "verify_report": {**(state.get("verify_report") or {}), **report}, "next": "check_reading_level"}


async def check_reading_level_node(state: MedCommSectionState) -> MedCommSectionState:
    """阅读难度检查（skip_level 时由路由跳过）"""
    content = state.get("verified_content", "")
    if state.get("skip_level"):
        return {**state, "reading_level_report": {"skipped": True}, "next": "suggest_images"}
    _, report = await run_verification(
        content=content,
        article_id=state.get("article_id"),
        rag_context=[],
        target_audience=state.get("target_audience", "public"),
        skip_verify=True,
        skip_level=False,
    )
    rl = report.get("reading_level", {})
    return {**state, "reading_level_report": rl, "next": "suggest_images"}


async def suggest_images_node(state: MedCommSectionState) -> MedCommSectionState:
    """LLM 分析内容推荐配图位置；条漫/分镜/卡片每格已有画面描述，跳过"""
    cf = state.get("content_format", "article")
    if cf in ("comic_strip", "storyboard", "card_series"):
        return {**state, "image_suggestions": [], "next": "normalize_terms"}
    current_content = state.get("verified_content", "")
    content = await _resolve_full_content_for_suggest(state, current_content)
    if not content or len(content.strip()) < 100:
        return {**state, "image_suggestions": [], "next": "normalize_terms"}

    # LLM 分析推荐配图
    try:
        from app.services.llm.openai_client import chat_completion
        from app.agents.prompts.verification import SUGGEST_IMAGES_PROMPT
        import json
        import re

        prompt = SUGGEST_IMAGES_PROMPT.format(
            verified_content=content[:5000],  # 放宽以容纳全文
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            target_audience=state.get("target_audience", "public"),
            content_format=cf,
        )
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        raw = (resp or "").strip()
        m = re.search(r"\[[\s\S]*\]", raw)
        if m:
            suggestions = json.loads(m.group())
            for i, s in enumerate(suggestions[:3]):
                s.setdefault("index", i)
                s.setdefault("anchor_text", (s.get("anchor_text") or "")[:20])
            if suggestions:  # 有推荐才返回，否则走 fallback
                return {**state, "image_suggestions": suggestions, "next": "normalize_terms"}
    except Exception:
        pass

    # Fallback：段落/句块分割
    suggestions = _fallback_image_suggestions(content)
    return {**state, "image_suggestions": suggestions[:3], "next": "normalize_terms"}


async def _resolve_full_content_for_suggest(state: dict, current_content: str) -> str:
    """尽可能使用全文（已保存章节 + 当前章节），否则仅用当前章节"""
    article_id = state.get("article_id")
    section_id = state.get("section_id")
    if not article_id or not current_content:
        return current_content
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.article import ArticleSection, ArticleContent
        import json

        def _extract_text(node):
            if isinstance(node, str):
                return node
            if not isinstance(node, dict):
                return ""
            if node.get("type") == "text":
                return node.get("text", "")
            return "".join(_extract_text(c) for c in node.get("content", []))

        parts = []
        async with AsyncSessionLocal() as db:
            sec_result = await db.execute(
                select(ArticleSection).where(ArticleSection.article_id == article_id).order_by(ArticleSection.order_num)
            )
            sections = sec_result.scalars().all()
            if not sections:
                return current_content
            platform = state.get("platform", "wechat")
            for sec in sections:
                if sec.id == section_id:
                    parts.append((sec.order_num, current_content))
                    continue
                cont_result = await db.execute(
                    select(ArticleContent).where(
                        ArticleContent.section_id == sec.id,
                        ArticleContent.is_current == True,
                    )
                )
                candidates = cont_result.scalars().all()
                c = next((x for x in candidates if getattr(x, "platform", None) == platform), None) or (candidates[0] if candidates else None)
                text = ""
                if c and c.content_json:
                    try:
                        doc = json.loads(c.content_json)
                        text = _extract_text(doc)
                    except Exception:
                        pass
                if text.strip():
                    parts.append((sec.order_num, text))
        parts.sort(key=lambda x: x[0])
        return "\n\n".join(p[1] for p in parts)
    except Exception:
        return current_content


def _fallback_image_suggestions(content: str) -> list[dict]:
    """无 LLM 或解析失败时，按段落/句块生成简单建议"""
    suggestions = []
    paras = [p.strip() for p in content.split("\n\n") if p.strip()]
    for i, para in enumerate(paras):
        if len(para) > 60:
            anchor_text = para[:20].replace("\n", " ")
            suggestions.append({
                "index": i,
                "anchor_text": anchor_text,
                "image_type": "anatomy",
                "style": "medical_illustration",
                "description": para[:50] + "…",
                "en_description": "",
                "reason": "段落内容适合配图",
                "priority": "medium",
            })
    if suggestions:
        return suggestions
    # 无 \n\n 时按句号分句，取较长句
    for sent in content.replace("。", "。\n").split("\n"):
        s = sent.strip()
        if len(s) > 60:
            suggestions.append({
                "index": len(suggestions),
                "anchor_text": s[:20],
                "image_type": "anatomy",
                "style": "medical_illustration",
                "description": s[:50] + "…",
                "en_description": "",
                "reason": "段落内容适合配图",
                "priority": "medium",
            })
            if len(suggestions) >= 3:
                break
    return suggestions


def normalize_terms_node(state: MedCommSectionState) -> MedCommSectionState:
    """术语标准化（占位，可接入 medical_terms 替换）"""
    return {**state, "next": "save"}


async def save_node(state: MedCommSectionState) -> MedCommSectionState:
    """持久化，含 enforce_version_limit"""
    from app.core.database import AsyncSessionLocal, get_domain_lock
    from app.services.content_version import save_node as cv_save
    import json

    from app.services.med_claim_marks import apply_med_claim_marks_to_doc

    content = state.get("verified_content", state.get("generated_content", ""))
    doc = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": content}]}]}
    report = state.get("verify_report")
    if isinstance(report, dict):
        doc = apply_med_claim_marks_to_doc(doc, report)
    lock = get_domain_lock("articles")
    async with lock:
        async with AsyncSessionLocal() as db:
            await cv_save(
                db,
                article_id=state["article_id"],
                section_id=state["section_id"],
                content_json=doc,
                version_type="ai_generated",
                platform=state.get("platform", "wechat"),
                verify_report=report if isinstance(report, dict) else None,
            )
            await db.commit()
    return {**state, "is_complete": True, "next": "end"}


async def save_partial_node(state: MedCommSectionState) -> MedCommSectionState:
    """部分保存（跳过验证时）"""
    return await save_node(state)


async def error_handler_node(state: MedCommSectionState, error: BaseException) -> MedCommSectionState:
    """错误处理"""
    return {**state, "error": str(error), "is_complete": False}

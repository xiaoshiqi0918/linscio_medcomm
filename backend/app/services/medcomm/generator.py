"""
章节生成服务 - 支持 SSE 流式输出
"""
import json
from typing import AsyncIterator

from app.agents.registry import get_agent_for_section, get_skip_flags


async def generate_section_stream(
    article_id: int,
    section_id: int,
    topic: str,
    content_format: str,
    section_type: str,
    target_audience: str = "public",
    platform: str = "wechat",
    specialty: str = "",
    model_hint: str = "default",
    article_default_model: str | None = None,
    format_meta: dict | None = None,
    scene_setup_context: str | None = None,
    target_word_count: int | None = None,
    skip_sections: list[str] | None = None,
) -> AsyncIterator[dict]:
    """
    流式生成章节内容，yield SSE 事件
    """
    from app.services.llm.openai_client import chat_completion
    from app.services.llm.manager import resolve_model_for_task, TaskTier
    from app.agents.base import _build_system_prompt
    from app.services.enhancement.prompt_builder import build_enhanced_prompt
    from app.services.enhancement.rag_retriever import RAGRetriever
    from app.services.verification.pipeline import run_verification
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.article import Article, ArticleSection, ArticleContent

    agent = get_agent_for_section(content_format, section_type)
    skip_verify, skip_level = get_skip_flags(content_format)

    state = {
        "article_id": article_id,
        "section_id": section_id,
        "topic": topic,
        "content_format": content_format,
        "section_type": section_type,
        "target_audience": target_audience,
        "platform": platform,
        "specialty": specialty,
        "model_hint": model_hint,
        "article_default_model": article_default_model,
        "format_meta": format_meta or {},
        "target_word_count": target_word_count,
        "skip_sections": skip_sections or [],
    }

    async def _resolve_prior_section_text(target_section_type: str) -> str:
        """Fallback: read a prior section's text from DB when not pre-supplied."""
        try:
            async with AsyncSessionLocal() as db:
                sec_result = await db.execute(
                    select(ArticleSection).where(
                        ArticleSection.article_id == article_id,
                        ArticleSection.section_type == target_section_type,
                    )
                )
                setup_sec = sec_result.scalar_one_or_none()
                if not setup_sec:
                    return ""
                cont_result = await db.execute(
                    select(ArticleContent).where(
                        ArticleContent.section_id == setup_sec.id,
                        ArticleContent.is_current == True,
                    )
                )
                candidates = cont_result.scalars().all()
                c = next((x for x in candidates if getattr(x, "platform", None) == platform), None) or (candidates[0] if candidates else None)
                if not c or not c.content_json:
                    return ""
                doc = json.loads(c.content_json)
                def _extract_text(node):
                    if isinstance(node, str):
                        return node
                    if isinstance(node, dict):
                        if node.get("type") == "text":
                            return node.get("text", "")
                        return "".join(_extract_text(x) for x in node.get("content", []))
                    if isinstance(node, list):
                        return "".join(_extract_text(x) for x in node)
                    return ""
                return _extract_text(doc).strip()
        except Exception:
            return ""

    if not scene_setup_context and content_format == "drama_script" and (section_type.startswith("scene_") or section_type == "ending"):
        scene_setup_context = await _resolve_prior_section_text("scene_setup")
    state["scene_setup_context"] = scene_setup_context or ""

    _PLANNER_FORMATS = {"storyboard", "comic_strip", "picture_book", "long_image"}
    if content_format in _PLANNER_FORMATS and section_type != "planner" and not state["format_meta"].get("planner_json"):
        planner_text = await _resolve_prior_section_text("planner")
        if planner_text:
            try:
                planner_data = json.loads(planner_text)
                state["format_meta"]["planner_json"] = planner_data
                for key in ("story_arc", "story_type", "total_panels", "total_pages",
                            "total_sections", "main_character", "core_message",
                            "story_title", "color_theme", "layout_style", "story_line"):
                    if key in planner_data and key not in state["format_meta"]:
                        state["format_meta"][key] = planner_data[key]
                panels_or_pages = planner_data.get("panels") or planner_data.get("pages") or planner_data.get("sections") or []
                state["format_meta"].setdefault("planner_items", panels_or_pages)
            except Exception:
                pass

    # 读取同一篇文章中已生成的前序章节内容（通用上下文记忆）
    import logging
    _log = logging.getLogger(__name__)

    prior_sections_context = ""
    try:
        from app.services.format_router import SECTION_TYPES_BY_FORMAT, SECTION_TITLES
        all_section_types = SECTION_TYPES_BY_FORMAT.get(content_format, [])
        current_idx = all_section_types.index(section_type) if section_type in all_section_types else -1
        _log.info("[prior_sections] format=%s section=%s idx=%d total_types=%d",
                  content_format, section_type, current_idx, len(all_section_types))
        if current_idx > 0:
            prior_types = all_section_types[:current_idx]
            _log.info("[prior_sections] looking for prior types: %s", prior_types)
            async with AsyncSessionLocal() as db:
                sec_result = await db.execute(
                    select(ArticleSection).where(
                        ArticleSection.article_id == article_id,
                        ArticleSection.section_type.in_(prior_types),
                    ).order_by(ArticleSection.order_num)
                )
                prior_secs = sec_result.scalars().all()
                _log.info("[prior_sections] found %d section records in DB", len(prior_secs))
                titles_map = SECTION_TITLES.get(content_format, {})
                parts = []
                for ps in prior_secs:
                    cont_result = await db.execute(
                        select(ArticleContent).where(
                            ArticleContent.section_id == ps.id,
                            ArticleContent.is_current == True,
                        )
                    )
                    candidates = cont_result.scalars().all()
                    c = next((x for x in candidates if getattr(x, "platform", None) == platform), None) or (candidates[0] if candidates else None)
                    if not c or not c.content_json:
                        _log.info("[prior_sections] section %s (id=%d): no content found", ps.section_type, ps.id)
                        continue
                    try:
                        doc = json.loads(c.content_json)
                    except Exception:
                        _log.warning("[prior_sections] section %s: content_json parse failed", ps.section_type)
                        continue
                    def _extract_text(node):
                        if isinstance(node, str):
                            return node
                        if isinstance(node, dict):
                            if node.get("type") == "text":
                                return node.get("text", "")
                            return "".join(_extract_text(x) for x in node.get("content", []))
                        if isinstance(node, list):
                            return "".join(_extract_text(x) for x in node)
                        return ""
                    text = _extract_text(doc).strip()
                    if text:
                        label = titles_map.get(ps.section_type, ps.section_type)
                        parts.append(f"【{label}】\n{text}")
                        _log.info("[prior_sections] section %s: extracted %d chars", ps.section_type, len(text))
                    else:
                        _log.info("[prior_sections] section %s: extracted empty text", ps.section_type)
                if parts:
                    prior_sections_context = "\n\n".join(parts)
                    _log.info("[prior_sections] ✅ total prior context: %d chars from %d sections",
                              len(prior_sections_context), len(parts))
                else:
                    _log.warning("[prior_sections] ⚠️ no prior content extracted (sections exist but empty)")
        else:
            _log.info("[prior_sections] first section or unknown type, no prior context needed")
    except Exception as exc:
        _log.error("[prior_sections] ❌ failed to read prior sections: %s", exc, exc_info=True)
        prior_sections_context = ""

    # 文献通道检索（用于写作注入与后续事实核验）
    rag_retriever = RAGRetriever()
    rag_context, ollama_unavailable = await rag_retriever.retrieve_literature(
        query=f"{topic} {section_type}",
        article_id=article_id,
        section_type=section_type,
        top_k=5 if content_format not in ("oral_script", "drama_script", "storyboard", "comic_strip", "card_series", "poster") else 3,
    )

    # ── 文献充分性预检 ──
    bound_paper_count = 0
    try:
        async with AsyncSessionLocal() as _db:
            from app.models.article import ArticleLiteratureBinding
            cnt_result = await _db.execute(
                select(ArticleLiteratureBinding.id)
                .where(ArticleLiteratureBinding.article_id == article_id)
            )
            bound_paper_count = len(cnt_result.fetchall())
    except Exception:
        pass

    user_id_for_corpus = 1
    try:
        async with AsyncSessionLocal() as _db:
            ur = await _db.execute(select(Article.user_id).where(Article.id == article_id))
            urow = ur.first()
            if urow and urow[0]:
                user_id_for_corpus = int(urow[0])
    except Exception:
        pass

    # 读取文献分析报告（若存在）
    analysis_report = None
    try:
        async with AsyncSessionLocal() as _db:
            ar = await _db.execute(select(Article.analysis_report).where(Article.id == article_id))
            arow = ar.first()
            if arow and arow[0]:
                analysis_report = arow[0]
    except Exception:
        pass

    base_prompt = agent.get_base_prompt(state)
    enhanced_prompt, rag_meta = await build_enhanced_prompt(
        base_prompt=base_prompt,
        topic=topic,
        section_type=section_type,
        content_format=content_format,
        target_audience=target_audience,
        platform=platform,
        specialty=specialty or None,
        article_id=article_id,
        rag_context=rag_context,
        prior_sections_context=prior_sections_context,
        user_id=user_id_for_corpus,
        analysis_report=analysis_report,
        target_word_count=target_word_count,
    )

    try:
        model = await resolve_model_for_task(
            task=TaskTier.QUALITY,
            article_id=article_id,
            article_default_model=article_default_model,
        )
    except Exception as e:
        yield {"type": "error", "message": f"模型初始化失败：{e}"}
        return

    system_prompt = _build_system_prompt(content_format, platform=platform, target_audience=target_audience)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": enhanced_prompt},
    ]

    yield {"type": "start", "task_id": "", "content_format": content_format}

    if bound_paper_count < 3:
        if bound_paper_count == 0:
            yield {
                "type": "literature_warning",
                "level": "critical",
                "bound_count": bound_paper_count,
                "message": "未绑定任何参考文献，生成内容将缺少文献支撑，建议返回配置页添加文献后再生成。",
            }
        else:
            yield {
                "type": "literature_warning",
                "level": "warning",
                "bound_count": bound_paper_count,
                "message": f"当前仅绑定 {bound_paper_count} 篇文献（建议 ≥ 3 篇），生成内容的事实覆盖度可能不足。",
            }

    if rag_meta.get("ollama_unavailable") or ollama_unavailable:
        yield {"type": "ollama_warning", "message": "Ollama 不可用，已降级为 FTS5 全文检索"}

    full_content = ""
    try:
        stream = await chat_completion(messages, model=model, stream=True)
        async for token in stream:
            full_content += token
            yield {"type": "delta", "text": token}

        if skip_verify:
            yield {"type": "claim_skipped", "reason": "图示类形式，跳过声明核实"}
        if skip_level:
            yield {"type": "reading_level_skipped", "reason": "脚本类/图示类形式，跳过阅读难度检查"}
        else:
            content, report = await run_verification(
                content=full_content,
                article_id=article_id,
                rag_context=rag_context,
                target_audience=target_audience,
                skip_verify=skip_verify,
                skip_level=skip_level,
            )
            full_content = content

            from app.services.verification.pipeline import (
                detect_ai_patterns,
                extract_provenance_summary,
                detect_uncited_medical_facts,
            )
            ai_patterns_result = detect_ai_patterns(full_content)
            report["ai_patterns"] = ai_patterns_result
            report["provenance"] = extract_provenance_summary(full_content)
            report["uncited_facts"] = detect_uncited_medical_facts(full_content)

            # ── 去AI化多轮自动改写：始终触发 ──
            ai_score = ai_patterns_result.get("score", 100)
            if len(full_content.strip()) >= 100:
                yield {"type": "rewriting", "message": "正在执行去AI化改写..."}
                from app.services.enhancement.deai_rewriter import rewrite_multi_pass

                async def _on_rewrite_progress(msg: str):
                    pass  # progress via SSE already sent above

                rewritten, was_rewritten, rewrite_stats = await rewrite_multi_pass(
                    content=full_content,
                    section_type=section_type,
                    article_id=article_id,
                    article_default_model=article_default_model,
                    platform=platform,
                    target_audience=target_audience,
                )
                if was_rewritten:
                    full_content = rewritten
                    ai_patterns_after = detect_ai_patterns(full_content)
                    report["ai_patterns_before_rewrite"] = ai_patterns_result
                    report["ai_patterns"] = ai_patterns_after
                    report["deai_rewrite"] = {
                        "applied": True,
                        "rounds": rewrite_stats.get("rounds", 1),
                        "score_before": ai_score,
                        "score_after": ai_patterns_after.get("score", 0),
                        **{k: v for k, v in rewrite_stats.items() if k != "rounds"},
                    }
                    yield {"type": "rewritten_content", "content": full_content}

            yield {"type": "verify_report", "report": report}

        # 读者向格式：清理可能残留的内部标签、元数据泄露、空占位标题
        from app.agents.prompts.system import _READER_FACING_CONTENT_FORMATS
        if content_format in _READER_FACING_CONTENT_FORMATS:
            import re
            full_content = re.sub(r"\[共识\]", "", full_content)
            full_content = re.sub(r"\[推断[:：][^\]]*\]", "", full_content)
            full_content = re.sub(r"\[\[待补充(?:[:：][^\]]*?)?\]\]", "", full_content)
            full_content = re.sub(r"\[DATA[:：][^\]]*\]", "", full_content)
            full_content = re.sub(r"\[文献(\d+)\]", r"[\1]", full_content)
            full_content = re.sub(
                r"^.*(?:主题：|形式：|平台：|文章类型：|内容形式：|目标读者：).*[\|｜]?.*$",
                "", full_content, flags=re.MULTILINE,
            )
            full_content = re.sub(r"^#+\s*(引言|前言|正文|案例|Q&A|问答|小结|结语)\s*$", "", full_content, flags=re.MULTILINE)
            full_content = re.sub(r"\[N\]", "", full_content)
            full_content = re.sub(
                r"(?:\n---\n|\n-{3,}\n)?\s*(?:^#+\s*)?参考文献.*",
                "", full_content, flags=re.DOTALL | re.MULTILINE,
            )
            full_content = re.sub(r"\n{3,}", "\n\n", full_content)
            full_content = re.sub(r"  +", " ", full_content)
            full_content = full_content.strip()

        # 配图建议：仅 article 形式，条漫/分镜/卡片每格已有画面描述则跳过
        image_suggestions = []
        if content_format not in ("comic_strip", "storyboard", "card_series") and len(full_content.strip()) >= 100:
            from app.workflow.nodes.medcomm_nodes import suggest_images_node
            sug_state = await suggest_images_node({
                "article_id": article_id,
                "section_id": section_id,
                "verified_content": full_content,
                "topic": topic,
                "content_format": content_format,
                "target_audience": target_audience,
                "platform": platform,
                "specialty": specialty,
            })
            image_suggestions = sug_state.get("image_suggestions") or []

        yield {
            "type": "done",
            "content": full_content,
            "word_count": len(full_content),
            "content_format": content_format,
            "image_suggestions": image_suggestions,
        }
    except Exception as e:
        yield {"type": "error", "message": str(e)}

"""
章节生成服务 - 支持 SSE 流式输出
"""
import json
import re
from typing import AsyncIterator

from app.agents.registry import get_agent_for_section, get_skip_flags


_METADATA_OUTPUT_INSTRUCTION = """

⚠️ 输出格式要求：
1. 正文中禁止出现任何字数统计标注（如"(84字)""（全文共X字）"），不要输出任何写作过程的元信息。
2. 在正文内容之后，额外输出一段结构化元数据，用于后续章节的上下文衔接。格式如下：

<section_metadata>
- 核心论点：（本章讲了哪些要点，一句话一个）
- 使用的比喻：（列出本章用过的所有比喻/类比，如"把胃比作搅拌机"）
- 使用的案例：（列出本章用过的案例人物/场景）
- 引用的数据：（列出本章引用的具体数据点）
- 解释过的术语：（术语 + 解释方式，如"幽门螺杆菌：用'一种螺旋形细菌'解释"）
- 结尾衔接句：（本章最后一句原文）
</section_metadata>"""


def _parse_section_metadata(content: str) -> tuple[str, dict | None]:
    """从 LLM 输出中分离正文和 section_metadata。
    返回 (clean_content, metadata_dict_or_None)。"""
    match = re.search(
        r"<section_metadata>\s*(.*?)\s*</section_metadata>",
        content, re.DOTALL,
    )
    if not match:
        return content, None

    raw_meta = match.group(1).strip()
    clean = content[:match.start()].rstrip()
    # 同时移除可能存在的 <article_section> 标签
    clean = re.sub(r"</?article_section>", "", clean).strip()

    meta: dict[str, list[str] | str] = {}
    current_key = None
    for line in raw_meta.splitlines():
        line = line.strip().lstrip("- ")
        if not line:
            continue
        if "：" in line:
            key, val = line.split("：", 1)
            key = key.strip()
            val = val.strip()
            _KEY_MAP = {
                "核心论点": "core_points",
                "使用的比喻": "metaphors",
                "使用的案例": "cases",
                "引用的数据": "data_points",
                "解释过的术语": "explained_terms",
                "结尾衔接句": "ending_sentence",
            }
            mapped = _KEY_MAP.get(key)
            if mapped:
                current_key = mapped
                if mapped == "ending_sentence":
                    meta[mapped] = val
                else:
                    meta.setdefault(mapped, [])
                    if val and val not in ("无", "（无）", "暂无"):
                        meta[mapped].append(val)
            else:
                if current_key and current_key != "ending_sentence":
                    meta.setdefault(current_key, [])
                    meta[current_key].append(line)
        else:
            if current_key and current_key != "ending_sentence":
                meta.setdefault(current_key, [])
                meta[current_key].append(line)

    return clean, meta if meta else None


def _paragraph_similarity(a: str, b: str) -> float:
    """简单的字符级 Jaccard 相似度（基于 2-gram），无需外部依赖。"""
    if len(a) < 20 or len(b) < 20:
        return 0.0
    def _bigrams(s: str) -> set[str]:
        return {s[i:i+2] for i in range(len(s) - 1)}
    sa, sb = _bigrams(a), _bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _detect_repetition_with_prior(
    content: str, prior_context: str, threshold: float = 0.55,
) -> list[dict]:
    """检测新生成内容中与前序内容高度相似的段落。
    返回 [{paragraph, similarity, prior_excerpt}] 列表。"""
    if not prior_context or not content:
        return []
    new_paras = [p.strip() for p in content.split("\n\n") if len(p.strip()) >= 30]
    prior_paras = [p.strip() for p in prior_context.split("\n") if len(p.strip()) >= 30]
    if not new_paras or not prior_paras:
        return []

    duplicates = []
    for np in new_paras:
        for pp in prior_paras:
            sim = _paragraph_similarity(np, pp)
            if sim >= threshold:
                duplicates.append({
                    "paragraph": np[:80],
                    "similarity": round(sim, 3),
                    "prior_excerpt": pp[:80],
                })
                break
    return duplicates


def _build_metadata_prior_context(
    prior_secs: list, titles_map: dict[str, str],
) -> str:
    """将前序章节的 section_metadata 汇总为结构化修辞资源清单。"""
    all_points: list[str] = []
    all_metaphors: list[str] = []
    all_cases: list[str] = []
    all_data: list[str] = []
    all_terms: list[str] = []
    last_ending = ""

    for ps in prior_secs:
        meta = getattr(ps, "section_metadata", None)
        if not meta or not isinstance(meta, dict):
            continue
        label = titles_map.get(ps.section_type, ps.section_type)
        for pt in meta.get("core_points", []):
            all_points.append(f"[{label}] {pt}")
        for m in meta.get("metaphors", []):
            all_metaphors.append(f"[{label}] {m}")
        for c in meta.get("cases", []):
            all_cases.append(f"[{label}] {c}")
        for d in meta.get("data_points", []):
            all_data.append(f"[{label}] {d}")
        for t in meta.get("explained_terms", []):
            all_terms.append(t)
        ending = meta.get("ending_sentence", "")
        if ending:
            last_ending = ending

    lines = ["## 前文已建立的内容（不要重复，但保持一致）", ""]

    if all_points:
        lines.append("【已讲过的核心论点】（一句话一个）")
        for p in all_points:
            lines.append(f"- {p}")
        lines.append("")

    if all_metaphors or all_cases or all_data:
        lines.append("【已用过的修辞资源 - 严禁重复使用】")
        for m in all_metaphors:
            lines.append(f"- 比喻：{m}")
        for c in all_cases:
            lines.append(f"- 案例：{c}")
        for d in all_data:
            lines.append(f"- 数据点：{d}")
        lines.append("")

    if all_terms:
        lines.append("【术语首次出现处理方式】")
        for t in all_terms:
            lines.append(f"- {t}")
        lines.append("")

    if last_ending:
        lines.append("【上一章结尾衔接句】")
        lines.append(f"> {last_ending}")
        lines.append("")

    return "\n".join(lines)


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
    saas_user=None,
) -> AsyncIterator[dict]:
    """
    流式生成章节内容，yield SSE 事件
    """
    from app.services.llm.openai_client import chat_completion, call_llm_with_fallback
    from app.services.llm.manager import resolve_model_for_task, TaskTier
    from app.core.config import is_saas
    from app.agents.base import _build_system_prompt
    from app.services.enhancement.prompt_builder import build_enhanced_prompt
    from app.services.enhancement.rag_retriever import RAGRetriever
    from app.services.verification.pipeline import run_verification
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.article import Article, ArticleSection, ArticleContent

    agent = get_agent_for_section(content_format, section_type)
    skip_verify, skip_level = get_skip_flags(content_format)

    reading_level = None
    try:
        async with AsyncSessionLocal() as _rl_db:
            _art = await _rl_db.get(Article, article_id)
            if _art:
                reading_level = getattr(_art, "reading_level", None)
    except Exception:
        pass

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
        "reading_level": reading_level,
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

    # 读取同一篇文章中已生成的前序章节 metadata / 内容（用于上下文衔接）
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

                has_any_metadata = any(
                    getattr(ps, "section_metadata", None) for ps in prior_secs
                )

                if has_any_metadata:
                    prior_sections_context = _build_metadata_prior_context(
                        prior_secs, titles_map,
                    )
                    _log.info("[prior_sections] ✅ using metadata-based context (%d chars)",
                              len(prior_sections_context))
                else:
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
                            continue
                        try:
                            doc = json.loads(c.content_json)
                        except Exception:
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
                    if parts:
                        prior_sections_context = "\n\n".join(parts)
                        _log.info("[prior_sections] ✅ fallback full-text context: %d chars from %d sections",
                                  len(prior_sections_context), len(parts))
                    else:
                        _log.warning("[prior_sections] ⚠️ no prior content extracted")
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
    contest_constraints = None
    try:
        async with AsyncSessionLocal() as _db:
            ar = await _db.execute(
                select(Article.analysis_report, Article.contest_custom_rules, Article.contest_pack_id)
                .where(Article.id == article_id)
            )
            arow = ar.first()
            if arow:
                if arow[0]:
                    analysis_report = arow[0]
                _custom_rules = arow[1]
                _pack_id = arow[2]
                if content_format == "contest_article":
                    _cc: dict = {}
                    if _pack_id:
                        from app.models.contest import ContestPack
                        _cp_r = await _db.execute(select(ContestPack).where(ContestPack.id == _pack_id))
                        _cp = _cp_r.scalar_one_or_none()
                        if _cp:
                            if _cp.word_limit:
                                _cc["word_limit"] = _cp.word_limit
                                # 参赛包的字数上限优先级最高，覆盖 target_word_count
                                if not target_word_count or target_word_count > _cp.word_limit:
                                    target_word_count = _cp.word_limit
                                    state["target_word_count"] = target_word_count
                            if _cp.image_format:
                                _cc["image_format"] = _cp.image_format
                            if _cp.file_format:
                                _cc["file_format"] = _cp.file_format
                            if _cp.ai_disclosure:
                                _cc["ai_disclosure"] = _cp.ai_disclosure
                            if _cp.font:
                                _cc["font"] = _cp.font
                    if isinstance(_custom_rules, dict):
                        for k, v in _custom_rules.items():
                            if v:
                                _cc[k] = v
                    if _cc:
                        contest_constraints = _cc
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
        reading_level=reading_level,
        skip_sections=skip_sections,
        contest_constraints=contest_constraints,
    )

    _use_saas_route = is_saas()

    try:
        if _use_saas_route:
            model = None  # SaaS 模式由 call_llm_with_fallback 内部路由
        else:
            model = await resolve_model_for_task(
                task=TaskTier.QUALITY,
                article_id=article_id,
                article_default_model=article_default_model,
                user=saas_user,
            )
    except Exception as e:
        yield {"type": "error", "message": f"模型初始化失败：{e}"}
        return

    _METADATA_FORMATS = {"article", "qa_article", "debunk", "story", "research_read", "contest_article"}
    _need_metadata = content_format in _METADATA_FORMATS
    if _need_metadata:
        enhanced_prompt += _METADATA_OUTPUT_INSTRUCTION

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
    parsed_metadata = None
    _actual_model = model  # 桌面模式下已知；SaaS 模式下从 StreamWithModel 读取
    try:
        if _use_saas_route:
            stream = await call_llm_with_fallback(
                "generation_round1", messages,
                user_id=user_id_for_corpus,
                article_id=article_id,
                section_id=section_id,
                stream=True,
                user=saas_user,
            )
            _actual_model = getattr(stream, "model", None)
        else:
            stream = await chat_completion(messages, model=model, stream=True)
        async for token in stream:
            full_content += token
            yield {"type": "delta", "text": token}

        if _need_metadata:
            full_content, parsed_metadata = _parse_section_metadata(full_content)
            if parsed_metadata:
                _log.info("[section_metadata] parsed keys: %s", list(parsed_metadata.keys()))

        # 相似度检测：与前序内容比较，如果重复率过高则触发带反馈的重写
        if prior_sections_context and len(full_content.strip()) >= 100:
            dups = _detect_repetition_with_prior(full_content, prior_sections_context)
            if len(dups) >= 2:
                _log.warning("[repetition] detected %d repeated paragraphs, triggering rewrite", len(dups))
                yield {"type": "rewriting", "message": f"检测到 {len(dups)} 处与前文重复，正在重新生成..."}
                dup_details = "\n".join(
                    f"- 「{d['paragraph']}…」与前文「{d['prior_excerpt']}…」相似度 {d['similarity']}"
                    for d in dups[:5]
                )
                retry_prompt = (
                    f"你刚刚生成的内容存在以下与前文重复的问题：\n{dup_details}\n\n"
                    f"请重新生成本章节内容，确保：\n"
                    f"1. 不复述前文已讲过的论点和修辞\n"
                    f"2. 提供全新的角度和表达\n"
                    f"3. 保持字数要求不变\n\n"
                    f"以下是需要重写的原文：\n{full_content}"
                )
                retry_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": enhanced_prompt},
                    {"role": "assistant", "content": full_content},
                    {"role": "user", "content": retry_prompt},
                ]
                retry_content = ""
                try:
                    if _use_saas_route:
                        retry_stream = await call_llm_with_fallback(
                            "generation_round1", retry_messages,
                            user_id=user_id_for_corpus,
                            article_id=article_id,
                            section_id=section_id,
                            stream=True,
                            user=saas_user,
                        )
                        _actual_model = getattr(retry_stream, "model", _actual_model)
                    else:
                        retry_stream = await chat_completion(retry_messages, model=model, stream=True)
                    async for token in retry_stream:
                        retry_content += token
                    if _need_metadata:
                        retry_content, retry_meta = _parse_section_metadata(retry_content)
                        if retry_meta:
                            parsed_metadata = retry_meta
                    if len(retry_content.strip()) >= 50:
                        full_content = retry_content
                        yield {"type": "rewritten_content", "content": full_content}
                        _log.info("[repetition] rewrite complete, new length: %d", len(full_content))
                except Exception as retry_err:
                    _log.error("[repetition] rewrite failed: %s", retry_err)

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
            "section_metadata": parsed_metadata,
            "actual_model": _actual_model,
        }
    except Exception as e:
        yield {"type": "error", "message": str(e)}

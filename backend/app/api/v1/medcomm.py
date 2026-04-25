"""MedComm 科普写作 API"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal, get_domain_lock
from app.core.config import is_saas
from app.models.article import Article, ArticleSection, ArticleContent
from app.services.medcomm.generator import generate_section_stream

router = APIRouter()


def _skip_article_legacy_intro(content_format: str | None, section_type: str | None) -> bool:
    """图文 article 已不再使用独立「引言」章节（正文首段承担引入）。旧库中可能仍有 intro 行，应跳过生成与全文合并。"""
    return (content_format or "article") == "article" and (section_type or "") == "intro"


def _strip_reference_nodes(nodes: list[dict]) -> list[dict]:
    """Remove LLM-generated '参考文献' heading and everything after it from TipTap nodes."""
    import re
    cut_idx = None
    for i, node in enumerate(nodes):
        if node.get("type") == "heading":
            text = "".join(
                c.get("text", "") for c in node.get("content", []) if isinstance(c, dict)
            )
            if re.search(r"参考文献|references", text, re.IGNORECASE):
                cut_idx = i
                break
        if node.get("type") == "paragraph":
            text = "".join(
                c.get("text", "") for c in node.get("content", []) if isinstance(c, dict)
            )
            if re.match(r"^\s*参考文献\s*$", text):
                cut_idx = i
                break
    if cut_idx is not None:
        nodes = nodes[:cut_idx]
        while nodes and nodes[-1].get("type") == "paragraph" and not nodes[-1].get("content"):
            nodes.pop()
    return nodes


VISUAL_JSON_EXPORT_VERSION = "1.0"

# content_format → 绘图软件 type 字段
_FORMAT_TO_DRAWING_TYPE: dict[str, str] = {
    "comic_strip": "comic",
    "storyboard": "comic",
    "card_series": "comic",
    "poster": "comic",
    "picture_book": "comic",
    "long_image": "comic",
}

# 各格式中属于"面板/画面"的 section_type 前缀或集合
_PANEL_SECTION_PREFIXES: dict[str, list[str]] = {
    "comic_strip": ["panel_"],
    "storyboard": ["reel_"],
    "card_series": ["card_", "cover_card", "ending_card"],
    "poster": ["headline", "body_visual", "cta_footer"],
    "picture_book": ["spread_", "cover", "back_cover"],
    "long_image": ["title_block", "intro_block", "core_", "tips_block", "warning_block", "summary_cta", "footer_info"],
}

# 各格式中属于"规划"的 section_type（包含全局信息：characters / style / 色调等）
_PLANNER_SECTION_TYPES: dict[str, str] = {
    "comic_strip": "planner",
    "storyboard": "anim_plan",
    "card_series": "series_plan",
    "poster": "poster_brief",
    "picture_book": "book_plan",
    "long_image": "image_plan",
}

# 从 ProseMirror doc 中提取纯文本并尝试解析 JSON
def _extract_section_text(content_json_obj: dict | None) -> str:
    """从 ProseMirror doc 提取拼接的纯文本"""
    if not content_json_obj:
        return ""
    from app.services.export.utils import _extract_text
    return _extract_text(content_json_obj).strip()


def _try_parse_section_json(text: str) -> dict | None:
    """尝试将章节文本解析为 JSON 对象；失败返回 None"""
    if not text:
        return None
    # 有时 LLM 输出包裹在 ```json ... ``` 中
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _is_panel_section(section_type: str, content_format: str) -> bool:
    prefixes = _PANEL_SECTION_PREFIXES.get(content_format, [])
    return any(section_type == p or section_type.startswith(p) for p in prefixes)


def _build_drawing_export(article, sections_with_content: list[tuple]) -> dict:
    """
    构建符合外部绘图软件规范的 JSON。
    sections_with_content: [(ArticleSection, content_json_obj), ...]
    """
    cf = article.content_format or "comic_strip"
    planner_st = _PLANNER_SECTION_TYPES.get(cf)
    planner_data: dict | None = None
    panels: list[dict] = []
    panel_idx_counter = 0

    for sec, content_obj in sections_with_content:
        text = _extract_section_text(content_obj)
        parsed = _try_parse_section_json(text)

        if sec.section_type == planner_st:
            planner_data = parsed
            continue

        if not _is_panel_section(sec.section_type, cf):
            continue

        panel_idx_counter += 1
        panel: dict = {
            "panel_index": panel_idx_counter,
            "scene_desc": "",
            "dialogue": "",
            "narration": "",
            "emotion": "",
            "caption": "",
            "visual_notes": "",
            "act": "",
            "characters_in_panel": [],
            "suggested_ckpt": None,
            "locked_seed": None,
        }

        if parsed:
            panel["panel_index"] = parsed.get("panel_index", panel_idx_counter)
            # 画面描述：兼容多格式不同字段名
            panel["scene_desc"] = (
                parsed.get("scene_desc")
                or parsed.get("scene_description")
                or parsed.get("key_visual")
                or parsed.get("visual_desc")
                or parsed.get("illustration_desc")
                or parsed.get("image_prompt")
                or parsed.get("main_visual_desc")
                or ""
            )
            # 对白
            panel["dialogue"] = parsed.get("dialogue") or parsed.get("dialog") or ""
            # 旁白
            panel["narration"] = (
                parsed.get("narration")
                or parsed.get("voiceover")
                or parsed.get("page_text")
                or parsed.get("body_text")
                or ""
            )
            panel["emotion"] = parsed.get("emotion") or ""
            panel["caption"] = (
                parsed.get("caption")
                or parsed.get("subtitle_highlight")
                or parsed.get("headline")
                or ""
            )
            panel["visual_notes"] = (
                parsed.get("visual_notes")
                or parsed.get("layout_note")
                or parsed.get("design_element")
                or parsed.get("effects_transition")
                or ""
            )
            panel["act"] = parsed.get("act") or parsed.get("panel_theme") or ""
            panel["characters_in_panel"] = parsed.get("characters_in_panel") or []

            # picture_book 双页结构：合并左右页描述
            if cf == "picture_book":
                lp = parsed.get("left_page") or {}
                rp = parsed.get("right_page") or {}
                descs = [d for d in [
                    lp.get("illustration_desc"), rp.get("illustration_desc")
                ] if d]
                if descs and not panel["scene_desc"]:
                    panel["scene_desc"] = " | ".join(descs)
                notes = [n for n in [
                    lp.get("layout_note"), rp.get("layout_note")
                ] if n]
                if notes and not panel["visual_notes"]:
                    panel["visual_notes"] = " | ".join(notes)
        elif text:
            panel["scene_desc"] = text[:200]

        panels.append(panel)

    # 从 planner 提取全局信息
    global_style_parts: list[str] = []
    characters: list[dict] = []
    if planner_data:
        if planner_data.get("art_style"):
            global_style_parts.append(planner_data["art_style"])
        if planner_data.get("color_theme"):
            global_style_parts.append(planner_data["color_theme"])
        if planner_data.get("animation_style"):
            global_style_parts.append(planner_data["animation_style"])
        if planner_data.get("visual_style"):
            global_style_parts.append(planner_data["visual_style"])

        raw_chars = planner_data.get("characters") or []
        if isinstance(raw_chars, list):
            for i, ch in enumerate(raw_chars):
                if not isinstance(ch, dict):
                    continue
                characters.append({
                    "id": ch.get("id") or f"char_{i+1}",
                    "name": ch.get("name") or f"角色{i+1}",
                    "description": ch.get("visual_desc") or ch.get("description") or "",
                    "trigger_words": ch.get("trigger_words") or "",
                    "reference_images": ch.get("reference_images") or [],
                })

        # 用 planner panels 数据补充缺失的 emotion / act
        planner_panels = (
            planner_data.get("panels")
            or planner_data.get("pages")
            or planner_data.get("cards")
            or planner_data.get("sections")
            or []
        )
        planner_by_idx = {}
        for pp in planner_panels:
            if isinstance(pp, dict) and pp.get("panel_index"):
                planner_by_idx[pp["panel_index"]] = pp
        for panel in panels:
            pp = planner_by_idx.get(panel["panel_index"])
            if pp:
                if not panel["emotion"]:
                    panel["emotion"] = pp.get("emotion") or ""
                if not panel["act"]:
                    panel["act"] = pp.get("act") or pp.get("panel_theme") or ""

    return {
        "version": VISUAL_JSON_EXPORT_VERSION,
        "type": _FORMAT_TO_DRAWING_TYPE.get(cf, "comic"),
        "title": article.title or article.topic or "",
        "meta": {
            "global_style": ", ".join(global_style_parts) if global_style_parts else "",
            "global_negative": "",
            "default_aspect_ratio": "3:4",
            "source_format": cf,
            "platform": article.platform or "",
            "specialty": article.specialty or "",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "panels": panels,
        "characters": characters,
    }


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


_PLATFORM_DEFAULT_WORD_COUNT = {
    "wechat": 1200,
    "xiaohongshu": 800,
    "douyin": 300,
    "journal": 3000,
    "offline": 2000,
}


class CreateArticleRequest(BaseModel):
    content_format: str = "article"
    topic: str = ""
    platform: str = "wechat"
    target_audience: str = "public"
    reading_level: str | None = None
    specialty: str = ""
    template_id: int | None = None
    default_model: str | None = None
    target_word_count: int | None = None
    skip_sections: list[str] = []
    analysis_report: dict | None = None


class UpdateArticleContentRequest(BaseModel):
    content_json: dict


class UpdateSectionContentRequest(BaseModel):
    content_json: dict


class SaveSectionRequest(BaseModel):
    content_json: dict


class UpdateImageStageRequest(BaseModel):
    image_stage: str = "pending"


class PatchArticleVisualContinuityRequest(BaseModel):
    """条漫/分镜/卡片等系列图示：锁定文案与可选种子基准（整篇统一）"""
    visual_continuity_prompt: str = ""
    image_series_seed_base: int | None = None


class PatchArticleTitleRequest(BaseModel):
    """篇名（导出篇首、顶栏展示；与主题 topic 不同）"""
    title: str = ""


@router.get("/articles")
async def list_articles(
    content_format: str | None = None,
    platform: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """作品列表，支持形式/平台过滤"""
    q = select(Article).where(Article.deleted_at.is_(None))
    if content_format:
        q = q.where(Article.content_format == content_format)
    if platform:
        q = q.where(Article.platform == platform)
    q = q.order_by(Article.updated_at.desc().nullslast(), Article.created_at.desc())
    result = await db.execute(q)
    items = result.scalars().all()
    return {"items": [article_to_dict(a) for a in items]}


@router.post("/articles")
async def create_article(
    req: CreateArticleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """新建文章"""
    # ── 入口审核：敏感词扫描 ──────────────────────────────────
    if is_saas():
        from app.services.moderation import scan_input
        from app.core.deps import get_current_user as _get_mod_user
        mod_user = await _get_mod_user(request, db)
        input_text = " ".join(filter(None, [
            req.topic,
            req.target_audience,
            req.specialty,
        ]))
        scan_result = await scan_input(input_text, mod_user.id, db)
        if scan_result.has_block:
            raise HTTPException(status_code=403, detail=scan_result.message)

    lock = get_domain_lock("articles")
    async with lock:
        twc = req.target_word_count or _PLATFORM_DEFAULT_WORD_COUNT.get(req.platform, 1500)
        article = Article(
            user_id=1,
            topic=req.topic or "未命名",
            title=req.topic or "未命名",
            content_format=req.content_format,
            platform=req.platform,
            target_audience=req.target_audience,
            specialty=req.specialty or "",
            reading_level=req.reading_level,
            default_model=req.default_model,
            target_word_count=twc,
            skip_sections=req.skip_sections or None,
            analysis_report=req.analysis_report,
            status="draft",
            current_stage="outline",
        )
        db.add(article)
        await db.flush()

        from app.services.format_router import get_format_sections

        sections = None
        if req.template_id:
            from app.models.template import ContentTemplate as CT
            tmpl_result = await db.execute(
                select(CT).where(CT.id == req.template_id, CT.is_active == True)
            )
            template = tmpl_result.scalar_one_or_none()
            if template:
                if isinstance(template.structure, list) and template.structure:
                    sections = template.structure
                if template.target_word_count and not req.target_word_count:
                    article.target_word_count = template.target_word_count
                if template.skip_sections and not req.skip_sections:
                    article.skip_sections = template.skip_sections

        if not sections:
            sections = get_format_sections(req.content_format) or ["body"]
        for i, st in enumerate(sections):
            if isinstance(st, dict):
                section_type = st.get("section_type", st.get("id", f"section_{i+1}"))
                title = st.get("title", section_type)
            else:
                section_type = str(st)
                title = section_type
            sec_status = "skipped" if section_type in (req.skip_sections or []) else "pending"
            sec = ArticleSection(
                article_id=article.id,
                section_type=section_type,
                title=title,
                order_num=i + 1,
                status=sec_status,
            )
            db.add(sec)
            await db.flush()
            # 为每章创建空内容
            empty_doc = json.dumps({"type": "doc", "content": []})
            content = ArticleContent(
                article_id=article.id,
                section_id=sec.id,
                content_json=empty_doc,
                version=1,
                version_type="ai_generated",
                is_current=True,
            )
            db.add(content)

        await db.commit()
        await db.refresh(article)
        return article_to_dict(article)


# 具体路径需注册在 /articles/{article_id} 之前，避免旧版路由匹配歧义
@router.get("/articles/{article_id}/export-check")
async def export_check_route(
    article_id: int,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """导出前检查：数据占位符、绝对化表述、孤儿引用、敏感词扫描"""
    from app.services.export.utils import load_article_sections, collect_orphan_citations
    from app.services.verification.pipeline import run_export_check

    try:
        article, parts = await load_article_sections(article_id, db)
        full_text = "\n\n".join(b for _, b, _ in parts)
        result = await run_export_check(full_text)
        orphans, valid_paper_ids = await collect_orphan_citations(article_id, db)
        result["orphan_citations"] = orphans
        result["valid_paper_ids"] = list(valid_paper_ids)
        if orphans:
            result["can_export"] = False
            result["message"] = (result.get("message") or "") + f"存在 {len(orphans)} 处孤儿引用（文献已移除绑定）建议修复；"

        # ── SaaS 出口审核：敏感词扫描 ──
        if is_saas() and request:
            try:
                from app.core.deps import get_current_user as _get_chk_user
                from app.services.moderation import scan_export
                chk_user = await _get_chk_user(request, db)
                mod_result = await scan_export(full_text, chk_user.id, db, article_id=article_id)
                if mod_result.matches:
                    result["moderation"] = {
                        "passed": mod_result.passed,
                        "level": mod_result.highest_level,
                        "message": mod_result.message,
                        "matches": [{"word": m.word, "level": m.level, "rule": m.rule_name}
                                    for m in mod_result.matches],
                    }
                    if not mod_result.passed:
                        result["can_export"] = False
                        result["message"] = (result.get("message") or "") + mod_result.message
            except Exception:
                pass

        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/articles/{article_id}/export")
async def export_article_route(
    article_id: int,
    fmt: str = Query("html", alias="format", description="html / docx / md / pdf / txt / json"),
    platform: str | None = None,
    watermark: bool = Query(True, description="是否带水印（无水印需 3 积分）"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """导出文章：json 导出原始结构化数据；html/docx/md/txt 走稳定合并导出；pdf 走 WeasyPrint 等形式路由。"""
    if is_saas() and not watermark and request:
        from app.core.deps import get_current_user as _get_exp_user
        from app.services.credit.pricing import calc_export_cost
        from app.services.credit.service import InsufficientCreditsError
        exp_user = await _get_exp_user(request, db)
        export_cost = calc_export_cost(with_watermark=False)

        paid = Decimal(str(exp_user.credits or 0))
        promo = Decimal(str(exp_user.promo_credits or 0))
        usable = paid + promo
        if usable < export_cost:
            raise HTTPException(
                status_code=402,
                detail=f"无水印导出需要 {export_cost} 积分（赠送积分不可用于导出），当前可用 {usable} 积分",
            )

        remaining = export_cost
        promo_deduct = min(promo, remaining)
        remaining -= promo_deduct
        if promo_deduct > 0:
            exp_user.promo_credits -= promo_deduct
        if remaining > 0:
            exp_user.credits -= remaining
        exp_user.total_consumed += export_cost

        from app.models.billing import UsageLog
        db.add(UsageLog(
            user_id=exp_user.id,
            article_id=article_id,
            operation="export_clean",
            cost=export_cost,
            breakdown={"promo": float(promo_deduct), "credits": float(remaining)},
            meta={"format": fmt, "watermark": False},
        ))
        await db.commit()
    from app.services.export.router import export_article as do_export
    from app.services.export.utils import (
        load_article_sections,
        prepend_export_title_markdown,
        prepend_export_title_plain,
        strip_markdown,
    )
    from app.services.export import html_docx
    from app.services.literature.citation_formatter import CitationFormatter
    from app.models.article import ArticleLiteratureBinding, ArticleExternalReference
    from app.models.literature import LiteraturePaper
    from app.utils.content_disposition import attachment_content_disposition
    from fastapi.responses import Response

    async def _build_reference_text(article_id: int) -> str:
        bind_result = await db.execute(
            select(ArticleLiteratureBinding.paper_id)
            .where(ArticleLiteratureBinding.article_id == article_id)
            .order_by(ArticleLiteratureBinding.priority.asc(), ArticleLiteratureBinding.id.asc())
        )
        paper_ids = []
        seen = set()
        for r in bind_result.fetchall():
            if r[0] not in seen:
                seen.add(r[0])
                paper_ids.append(r[0])
        lines: list[str] = []
        if paper_ids:
            paper_result = await db.execute(
                select(LiteraturePaper).where(LiteraturePaper.id.in_(paper_ids))
            )
            papers = {p.id: p for p in paper_result.scalars().all()}
            for i, pid in enumerate(paper_ids, 1):
                p = papers.get(pid)
                if not p:
                    continue
                lines.append(f"[{i}] {CitationFormatter(p).format('popular')}")

        ext_result = await db.execute(
            select(ArticleExternalReference)
            .where(ArticleExternalReference.article_id == article_id)
            .order_by(ArticleExternalReference.id.asc())
        )
        ext_refs = ext_result.scalars().all()
        offset = len(lines)
        for j, r in enumerate(ext_refs, 1):
            lines.append(f"[{offset + j}] {CitationFormatter.format_external_ref(r)}")
        if not lines:
            return ""
        return "\n\n## 参考文献\n\n" + "\n".join(lines)

    _DISCLAIMER_TEXT = (
        "\n\n---\n\n"
        "**免责声明**：本文由 AI 辅助生成，仅供科普参考，不构成任何医疗建议。"
        "文中涉及的疾病、治疗方案等信息请以专业医疗机构的诊断和建议为准。"
        "如有健康问题，请及时就医。\n"
    )

    def _merged_export(article, parts, export_fmt: str, refs_text: str = "") -> tuple[bytes, str, str]:
        """各章节合并后的通用导出"""
        base_name = (article.topic or "article").replace("/", "-")
        cf = getattr(article, "content_format", None) or "article"
        hide_headings = cf == "article"

        filtered = [
            (t, b, st) for t, b, st in parts
            if not _skip_article_legacy_intro(cf, st) and b.strip()
        ]

        disclaimer = _DISCLAIMER_TEXT if (is_saas() and watermark) else ""

        if hide_headings:
            md_body = "\n\n".join(b for _, b, _ in filtered) + (refs_text or "") + disclaimer
        else:
            md_body = "\n\n".join(f"## {t}\n\n{b}" for t, b, _ in filtered) + (refs_text or "") + disclaimer

        if export_fmt == "md":
            asset_block = (
                "\n\n---\n\n## 配图与资源说明\n\n"
                "- 正文中的插图若在软件内为本地或 `medcomm-image` 链接，发布到公众号/知乎/小红书前请重新上传图片并替换为平台图片地址。\n"
            )
            full_md = prepend_export_title_markdown(article, md_body) + asset_block
            return full_md.encode("utf-8"), "text/markdown; charset=utf-8", f"{base_name}.md"

        if hide_headings:
            plain_body = "\n\n".join(strip_markdown(b) for _, b, _ in filtered)
        else:
            plain_body = "\n\n".join(f"{t}\n\n{strip_markdown(b)}" for t, b, _ in filtered)
        if refs_text:
            plain_body += "\n\n" + strip_markdown(refs_text)

        if export_fmt == "html":
            html = html_docx.to_html(article, plain_body)
            return html.encode("utf-8"), "text/html; charset=utf-8", f"{base_name}.html"
        if export_fmt == "docx":
            try:
                if hide_headings:
                    docx_parts = [("", strip_markdown(b)) for _, b, _ in filtered]
                else:
                    docx_parts = [(t, strip_markdown(b)) for t, b, _ in filtered]
                if refs_text:
                    docx_parts.append(("参考文献", strip_markdown(refs_text)))
                buf, fn = html_docx.to_docx(article, docx_parts)
                return buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", fn
            except Exception:
                txt = prepend_export_title_plain(article, plain_body)
                return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"
        txt = prepend_export_title_plain(article, plain_body)
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"

    normalized = (fmt or "html").strip().lower()
    if normalized not in ("html", "docx", "md", "pdf", "txt", "json"):
        normalized = "txt"

    # JSON 导出：转换为外部绘图软件兼容的标准格式（comic_v1 适配器）
    if normalized == "json":
        try:
            result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
            article = result.scalar_one_or_none()
            if not article:
                raise HTTPException(status_code=404, detail="Article not found")
            sec_result = await db.execute(
                select(ArticleSection).where(ArticleSection.article_id == article_id).order_by(ArticleSection.order_num)
            )
            sections = sec_result.scalars().all()
            platform = article.platform or "wechat"
            sections_with_content: list[tuple] = []
            for sec in sections:
                cont_result = await db.execute(
                    select(ArticleContent).where(
                        ArticleContent.section_id == sec.id,
                        ArticleContent.is_current == True,
                    )
                )
                candidates = cont_result.scalars().all()
                c = next((x for x in candidates if x.platform == platform), None) or next(
                    (x for x in candidates if x.platform is None), candidates[0] if candidates else None
                )
                content_obj = None
                if c and c.content_json:
                    try:
                        content_obj = json.loads(c.content_json)
                    except Exception:
                        pass
                sections_with_content.append((sec, content_obj))

            export_obj = _build_drawing_export(article, sections_with_content)
            base_name = (article.topic or "article").replace("/", "-")
            payload = json.dumps(export_obj, ensure_ascii=False, indent=2).encode("utf-8")
            return Response(content=payload, media_type="application/json; charset=utf-8", headers={
                "Content-Disposition": attachment_content_disposition(f"{base_name}.json"),
            })
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # docx/html/md/txt：不经过 export.router 的形式分发，避免个别导出器异常导致 404/500
    if normalized != "pdf":
        try:
            article, parts = await load_article_sections(article_id, db)
            refs_text = await _build_reference_text(article_id)
            use_fmt = normalized if normalized in ("html", "docx", "md") else "txt"
            content, media_type, filename = _merged_export(article, parts, use_fmt, refs_text=refs_text)
            return Response(content=content, media_type=media_type, headers={
                "Content-Disposition": attachment_content_disposition(filename),
            })
        except UnicodeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except ValueError as e:
            if str(e) == "Article not found":
                raise HTTPException(status_code=404, detail=str(e))
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    try:
        content, media_type, filename = await do_export(
            article_id, "pdf", platform=platform or "wechat", db=db
        )
        return Response(content=content, media_type=media_type, headers={
            "Content-Disposition": attachment_content_disposition(filename),
        })
    except UnicodeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        if str(e) == "Article not found":
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/articles/{article_id}")
async def get_article(
    article_id: int,
    section_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取文章详情，section_id 指定时返回该章节内容"""
    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    sections_result = await db.execute(
        select(ArticleSection).where(ArticleSection.article_id == article_id).order_by(ArticleSection.order_num)
    )
    sections = sections_result.scalars().all()

    target_section = None
    if section_id:
        target_section = next((s for s in sections if s.id == section_id), None)
    if not target_section:
        target_section = sections[0] if sections else None

    content_json = None
    section_verify_report = None
    if target_section:
        platform = article.platform or "wechat"
        cont_result = await db.execute(
            select(ArticleContent).where(
                ArticleContent.section_id == target_section.id,
                ArticleContent.is_current == True,
            )
        )
        candidates = cont_result.scalars().all()
        content = next((c for c in candidates if c.platform == platform), None) or next((c for c in candidates if c.platform is None), candidates[0] if candidates else None)
        if content and content.content_json:
            content_json = json.loads(content.content_json)
        if content is not None:
            section_verify_report = content.verify_report

    d = article_to_dict(article)
    d["content_json"] = content_json or {"type": "doc", "content": []}
    d["verify_report"] = section_verify_report
    d["current_section_id"] = target_section.id if target_section else None

    platform = article.platform or "wechat"
    section_has_content: dict[int, bool] = {}
    full_doc_nodes: list[dict] = []

    if sections:
        all_section_ids = [s.id for s in sections]
        all_cont_result = await db.execute(
            select(ArticleContent)
            .where(
                ArticleContent.section_id.in_(all_section_ids),
                ArticleContent.is_current == True,
            )
        )
        all_contents = all_cont_result.scalars().all()
        content_by_section: dict[int, list] = {}
        for c in all_contents:
            content_by_section.setdefault(c.section_id, []).append(c)

        from app.services.format_router import SECTION_TITLES
        titles_map = SECTION_TITLES.get(article.content_format or "article", {})
        cf = article.content_format or "article"
        hide_section_headings = cf == "article"

        for sec in sections:
            if _skip_article_legacy_intro(article.content_format, sec.section_type):
                continue
            candidates = content_by_section.get(sec.id, [])
            has = bool(candidates)
            section_has_content[sec.id] = has

            c = next((x for x in candidates if x.platform == platform), None) or \
                next((x for x in candidates if x.platform is None), candidates[0] if candidates else None)
            if not c or not c.content_json:
                continue
            try:
                doc = json.loads(c.content_json)
            except Exception:
                continue
            nodes = doc.get("content", []) if isinstance(doc, dict) else []
            if not nodes:
                continue

            nodes = _strip_reference_nodes(nodes)
            if not nodes:
                continue

            if not hide_section_headings:
                sec_title = sec.title or titles_map.get(sec.section_type, sec.section_type)
                full_doc_nodes.append({
                    "type": "heading", "attrs": {"level": 2},
                    "content": [{"type": "text", "text": sec_title}]
                })
            if full_doc_nodes:
                full_doc_nodes.append({"type": "paragraph"})
            full_doc_nodes.extend(nodes)

    d["full_content_json"] = {"type": "doc", "content": full_doc_nodes} if full_doc_nodes else {"type": "doc", "content": []}

    d["sections"] = [
        {
            "id": s.id,
            "section_type": s.section_type,
            "title": s.title,
            "order_num": s.order_num,
            "status": s.status or "pending",
            "has_content": section_has_content.get(s.id, False),
        }
        for s in sections
        if not _skip_article_legacy_intro(article.content_format, s.section_type)
    ]
    return d


@router.patch("/sections/{section_id}/skip")
async def skip_section(section_id: int, db: AsyncSession = Depends(get_db)):
    """将章节标记为跳过"""
    sec = await db.get(ArticleSection, section_id)
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found")
    sec.status = "skipped"
    article = await db.get(Article, sec.article_id)
    if article:
        current = article.skip_sections or []
        if sec.section_type not in current:
            article.skip_sections = current + [sec.section_type]
    await db.commit()
    return {"ok": True, "status": "skipped"}


@router.patch("/sections/{section_id}/unskip")
async def unskip_section(section_id: int, db: AsyncSession = Depends(get_db)):
    """恢复被跳过的章节"""
    sec = await db.get(ArticleSection, section_id)
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found")
    sec.status = "pending"
    article = await db.get(Article, sec.article_id)
    if article and article.skip_sections:
        article.skip_sections = [s for s in article.skip_sections if s != sec.section_type]
        if not article.skip_sections:
            article.skip_sections = None
    await db.commit()
    return {"ok": True, "status": "pending"}


@router.post("/sections/{section_id}/save")
async def save_section(
    section_id: int,
    req: SaveSectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """保存章节内容（规范：POST /sections/{id}/save）"""
    sec_result = await db.execute(
        select(ArticleSection, Article).join(Article, ArticleSection.article_id == Article.id).where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    section, article = row
    from app.services.content_version import save_node
    lock = get_domain_lock("articles")
    async with lock:
        await save_node(
            db,
            article_id=article.id,
            section_id=section.id,
            content_json=req.content_json,
            version_type="user_edited",
            platform=article.platform or "wechat",
        )
        await db.commit()
    return {"ok": True}


@router.get("/sections/{section_id}/versions")
async def get_section_versions(
    section_id: int,
    platform: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取章节版本历史"""
    sec_result = await db.execute(
        select(ArticleSection, Article).join(Article, ArticleSection.article_id == Article.id).where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    section, article = row
    pf = platform or article.platform or "wechat"
    from sqlalchemy import or_
    platform_filter = (ArticleContent.platform == pf) | ((ArticleContent.platform.is_(None)) & (pf == "wechat"))
    result = await db.execute(
        select(ArticleContent)
        .where(ArticleContent.section_id == section_id, platform_filter)
        .order_by(ArticleContent.version.desc())
    )
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": c.id,
                "version": c.version,
                "version_type": c.version_type,
                "is_current": c.is_current,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in items
        ]
    }


@router.post("/sections/{section_id}/revert/{ver_id}")
async def revert_section(
    section_id: int,
    ver_id: int,
    db: AsyncSession = Depends(get_db),
):
    """回滚到指定版本"""
    sec_result = await db.execute(
        select(ArticleSection, Article).join(Article, ArticleSection.article_id == Article.id).where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    section, article = row
    target = await db.execute(
        select(ArticleContent).where(
            ArticleContent.id == ver_id,
            ArticleContent.section_id == section_id,
        )
    )
    content = target.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Version not found")
    from sqlalchemy import or_
    platform = content.platform or "wechat"
    platform_filter = (ArticleContent.platform == platform) | ((ArticleContent.platform.is_(None)) & (platform == "wechat"))
    others = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == section_id,
            platform_filter,
            ArticleContent.id != ver_id,
        )
    )
    for c in others.scalars().all():
        c.is_current = False
    content.is_current = True
    await db.commit()
    return {"ok": True}


@router.patch("/articles/{article_id}/visual-continuity")
async def patch_article_visual_continuity(
    article_id: int,
    req: PatchArticleVisualContinuityRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新文章级图示连贯性配置（生图时注入正向提示词；种子仅 ComfyUI 等有效）"""
    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.visual_continuity_prompt = (req.visual_continuity_prompt or "").strip() or None
    article.image_series_seed_base = req.image_series_seed_base
    await db.commit()
    await db.refresh(article)
    return article_to_dict(article)


@router.post("/articles/{article_id}/generate-title")
async def generate_article_title_route(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """全文各章节有内容后，用模型总结一条发布用标题并写入 articles.title"""
    from app.services.export.utils import load_article_sections
    from app.services.medcomm.title_generator import generate_article_title as gen_title

    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    _art, parts = await load_article_sections(article_id, db)
    title = await gen_title(
        article_id=article_id,
        topic=article.topic or "",
        content_format=article.content_format or "article",
        platform=article.platform or "wechat",
        target_audience=article.target_audience or "public",
        parts=parts,
        article_default_model=article.default_model,
    )
    if not title:
        raise HTTPException(status_code=400, detail="正文为空，请先生成或填写各章节内容后再总结标题")
    article.title = title[:500]
    await db.commit()
    await db.refresh(article)
    return article_to_dict(article)


@router.patch("/articles/{article_id}/title")
async def patch_article_title_route(
    article_id: int,
    req: PatchArticleTitleRequest,
    db: AsyncSession = Depends(get_db),
):
    """手动修改篇名"""
    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    t = (req.title or "").strip()[:500]
    article.title = t if t else None
    await db.commit()
    await db.refresh(article)
    return article_to_dict(article)


@router.patch("/articles/{article_id}/image-stage")
async def update_article_image_stage(
    article_id: int,
    req: UpdateImageStageRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新文章配图阶段（pending / in_progress / done）"""
    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.image_stage = req.image_stage
    await db.commit()
    return {"ok": True}


@router.put("/articles/{article_id}/save-full-content")
async def save_full_content(
    article_id: int,
    req: UpdateArticleContentRequest,
    db: AsyncSession = Depends(get_db),
):
    """保存合并视图的全文内容到 body 章节，并取消其他章节的 is_current 标记以避免重复"""
    from app.services.content_version import save_node

    lock = get_domain_lock("articles")
    async with lock:
        result = await db.execute(
            select(Article).where(Article.id == article_id, Article.deleted_at.is_(None))
        )
        article = result.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        platform = article.platform or "wechat"
        cf = article.content_format or "article"

        sec_result = await db.execute(
            select(ArticleSection)
            .where(ArticleSection.article_id == article_id)
            .order_by(ArticleSection.order_num)
        )
        sections = sec_result.scalars().all()
        if not sections:
            raise HTTPException(status_code=404, detail="No sections found")

        body_section = next(
            (s for s in sections if s.section_type == "body"),
            sections[0],
        )

        await save_node(
            db,
            article_id=article_id,
            section_id=body_section.id,
            content_json=req.content_json,
            version_type="user_edited",
            platform=platform,
        )

        other_section_ids = [
            s.id for s in sections
            if s.id != body_section.id
        ]
        if other_section_ids:
            from sqlalchemy import or_
            stale = await db.execute(
                select(ArticleContent).where(
                    ArticleContent.section_id.in_(other_section_ids),
                    or_(
                        ArticleContent.platform == platform,
                        (ArticleContent.platform.is_(None)) & (platform == "wechat"),
                    ),
                    ArticleContent.is_current == True,
                )
            )
            for c in stale.scalars().all():
                c.is_current = False

        await db.commit()
    return {"ok": True}


@router.patch("/articles/{article_id}")
async def update_article_content(
    article_id: int,
    req: UpdateArticleContentRequest,
    section_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """更新文章内容，section_id 指定章节；创建新版本并执行版本上限清理"""
    from app.services.content_version import save_node

    lock = get_domain_lock("articles")
    async with lock:
        if section_id:
            sec_result = await db.execute(select(ArticleSection).where(
                ArticleSection.id == section_id,
                ArticleSection.article_id == article_id,
            ))
            section = sec_result.scalar_one_or_none()
        else:
            sec_result = await db.execute(
                select(ArticleSection)
                .where(ArticleSection.article_id == article_id)
                .order_by(ArticleSection.order_num)
                .limit(1)
            )
            section = sec_result.scalar_one_or_none()
        if not section:
            raise HTTPException(status_code=404, detail="No section found")

        art_result = await db.execute(select(Article).where(Article.id == article_id))
        article = art_result.scalar_one_or_none()
        platform = (article.platform if article else None) or "wechat"

        await save_node(
            db,
            article_id=article_id,
            section_id=section.id,
            content_json=req.content_json,
            version_type="user_edited",
            platform=platform,
        )
        await db.commit()
    return {"ok": True}


_ORAL_TIME_MAP = {
    "golden_hook": ("00:00", "00:05"),
    "problem_setup": ("00:05", "00:20"),
    "core_knowledge": ("00:20", "00:50"),
    "practical_tips": ("00:50", "01:05"),
    "closing_hook": ("00:55", "01:05"),
}


def _build_format_meta(section, article) -> dict:
    """构建 format_meta，供条漫/口播/分镜/播客等 Agent 使用"""
    meta = dict((section.format_meta or {}) if hasattr(section, "format_meta") else {})
    cf = article.content_format or "article"
    st = section.section_type or ""
    from app.services.format_router import SECTION_TYPES_BY_FORMAT

    types_list = SECTION_TYPES_BY_FORMAT.get(cf, [])

    if cf == "comic_strip" and not meta.get("panel_index") and st.startswith("panel_"):
        try:
            idx = int(st.replace("panel_", ""))
            panel_types = [t for t in types_list if t.startswith("panel_")]
            meta = {"panel_index": idx, "total_panels": len(panel_types) or 12}
        except ValueError:
            meta = {"panel_index": section.order_num or 1, "total_panels": 12}
    elif cf == "oral_script":
        if st == "script_plan":
            meta["script_role"] = "planner"
        elif st == "extras":
            meta["script_role"] = "extras"
        else:
            start, end = _ORAL_TIME_MAP.get(st, ("00:00", "01:00"))
            meta["start_time"] = start
            meta["end_time"] = end
            meta["script_role"] = "content"
    elif cf == "storyboard":
        if st == "anim_plan":
            meta["storyboard_role"] = "planner"
        elif st == "char_design":
            meta["storyboard_role"] = "char"
        elif st.startswith("reel_"):
            try:
                reel_idx = int(st.replace("reel_", ""))
                meta["reel_index"] = reel_idx
                meta["total_reels"] = 5
            except ValueError:
                meta["reel_index"] = 1
                meta["total_reels"] = 5
            meta["storyboard_role"] = "reel"
        elif st == "prod_notes":
            meta["storyboard_role"] = "prod"
    elif cf == "drama_script":
        if st == "drama_plan":
            meta["drama_role"] = "planner"
        elif st == "cast_table":
            meta["drama_role"] = "cast"
        elif st.startswith("act_"):
            try:
                act_idx = int(st.replace("act_", ""))
                meta["act_index"] = act_idx
                meta["total_acts"] = 5
            except ValueError:
                meta["act_index"] = 1
                meta["total_acts"] = 5
            meta["drama_role"] = "act"
        elif st == "finale":
            meta["drama_role"] = "finale"
        elif st == "filming_notes":
            meta["drama_role"] = "filming"
    elif cf == "audio_script" and not meta.get("duration_sec"):
        # 默认每段约 2-3 分钟
        meta["duration_sec"] = 150
        meta["start_time"] = 0
        meta["end_time"] = 2.5
    elif cf == "card_series":
        content_card_types = [t for t in types_list if t.startswith("card_")]
        total_visible = len(content_card_types) + 2  # cover + content cards + ending
        meta.setdefault("total_cards", total_visible)
        meta.setdefault("color_scheme", "blue")
        if st.startswith("card_"):
            if not meta.get("card_index"):
                try:
                    idx = int(st.replace("card_", ""))
                    meta["card_index"] = idx
                except ValueError:
                    meta["card_index"] = section.order_num or 1
            meta["card_role"] = "content"
        elif st == "cover_card":
            meta["card_role"] = "cover"
        elif st == "ending_card":
            meta["card_role"] = "ending"
        elif st == "series_plan":
            meta["card_role"] = "planner"
    elif cf == "quiz_article" and st.startswith("q_"):
        if not meta.get("question_index"):
            try:
                idx = int(st.replace("q_", ""))
                q_types = ["误区识别", "知识测试", "行为评估"]
                meta["question_index"] = idx
                meta["question_type"] = q_types[(idx - 1) % len(q_types)]
            except ValueError:
                meta["question_index"] = 1
                meta["question_type"] = "误区识别"
    elif cf == "h5_outline" and st.startswith("page_") and st != "page_cover" and st != "page_end":
        if not meta.get("page_index"):
            try:
                idx = int(st.replace("page_", ""))
                meta["page_index"] = idx
            except ValueError:
                meta["page_index"] = 1
    elif cf == "picture_book":
        if st == "book_plan":
            pass
        elif st.startswith("spread_"):
            try:
                idx = int(st.replace("spread_", ""))
                meta["spread_index"] = idx
                spread_types = [t for t in types_list if t.startswith("spread_")]
                meta["total_spreads"] = len(spread_types) or 7
            except ValueError:
                meta["spread_index"] = section.order_num or 1
                meta["total_spreads"] = 7
        elif st in ("cover", "back_cover"):
            meta["page_role"] = st
    elif cf == "poster":
        meta["poster_section"] = st
    elif cf == "long_image":
        if st.startswith("core_"):
            try:
                idx = int(st.replace("core_", ""))
                meta["block_index"] = idx
            except ValueError:
                meta["block_index"] = 1

    return meta


def _extract_doc_text(node) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_extract_doc_text(x) for x in node.get("content", []))
    if isinstance(node, list):
        return "".join(_extract_doc_text(x) for x in node)
    return ""


async def _auto_generate_title_if_complete(article_id: int) -> dict | None:
    """所有章节都有内容且尚无标题时，自动生成标题并写入 DB，返回 SSE 事件或 None"""
    from app.services.export.utils import load_article_sections
    from app.services.medcomm.title_generator import generate_article_title as gen_title

    lock = get_domain_lock("articles")
    async with lock:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
            article = result.scalar_one_or_none()
            if not article:
                return None
            if (article.title or "").strip():
                return None
            _, parts = await load_article_sections(article_id, db)
            if not parts or any(not body.strip() for _, body, _ in parts):
                return None
            title = await gen_title(
                article_id=article_id,
                topic=article.topic or "",
                content_format=article.content_format or "article",
                platform=article.platform or "wechat",
                target_audience=article.target_audience or "public",
                parts=parts,
                article_default_model=article.default_model,
            )
            if not title:
                return None
            article.title = title[:500]
            await db.commit()
            return {"type": "title_generated", "title": title[:500]}


async def _get_section_text(db: AsyncSession, article_id: int, section_type: str, platform: str) -> str:
    """通用：从数据库读取某 section_type 的当前内容纯文本"""
    sec_result = await db.execute(
        select(ArticleSection).where(
            ArticleSection.article_id == article_id,
            ArticleSection.section_type == section_type,
        )
    )
    sec = sec_result.scalar_one_or_none()
    if not sec:
        return ""
    cont_result = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == sec.id,
            ArticleContent.is_current == True,
        )
    )
    candidates = cont_result.scalars().all()
    c = next((x for x in candidates if getattr(x, "platform", None) == platform), None) or (candidates[0] if candidates else None)
    if not c or not c.content_json:
        return ""
    try:
        doc = json.loads(c.content_json)
    except Exception:
        return ""
    return _extract_doc_text(doc).strip()


async def _get_scene_setup_context(db: AsyncSession, article_id: int, platform: str) -> str:
    text = await _get_section_text(db, article_id, "scene_setup", platform)
    if not text:
        text = await _get_section_text(db, article_id, "cast_table", platform)
    return text


async def _get_prior_sections_context(db: AsyncSession, article_id: int, content_format: str, section_type: str, platform: str) -> str:
    """读取同一篇文章中当前章节之前的所有已生成章节内容"""
    from app.services.format_router import SECTION_TYPES_BY_FORMAT, SECTION_TITLES
    all_types = SECTION_TYPES_BY_FORMAT.get(content_format, [])
    try:
        current_idx = all_types.index(section_type)
    except ValueError:
        return ""
    if current_idx <= 0:
        return ""
    prior_types = all_types[:current_idx]
    sec_result = await db.execute(
        select(ArticleSection).where(
            ArticleSection.article_id == article_id,
            ArticleSection.section_type.in_(prior_types),
        ).order_by(ArticleSection.order_num)
    )
    prior_secs = sec_result.scalars().all()
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
            continue
        try:
            doc = json.loads(c.content_json)
        except Exception:
            continue
        text = _extract_doc_text(doc).strip()
        if text:
            label = titles_map.get(ps.section_type, ps.section_type)
            parts.append(f"【{label}】\n{text}")
    return "\n\n".join(parts) if parts else ""


_PLANNER_FORMATS = {"storyboard", "comic_strip", "picture_book", "long_image", "card_series", "poster", "oral_script", "drama_script", "patient_handbook"}
_PLANNER_SECTION_TYPE = {"card_series": "series_plan", "poster": "poster_brief", "picture_book": "book_plan", "long_image": "image_plan", "oral_script": "script_plan", "drama_script": "drama_plan", "storyboard": "anim_plan", "patient_handbook": "handbook_plan"}


async def _get_planner_context(db: AsyncSession, article_id: int, platform: str, planner_section_type: str = "planner") -> dict:
    """读取 planner 章节的 JSON 内容，解析为 dict 供 format_meta 合并"""
    text = await _get_section_text(db, article_id, planner_section_type, platform)
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


@router.post("/sections/{section_id}/generate-full")
async def generate_section_full(
    section_id: int,
    db: AsyncSession = Depends(get_db),
):
    """全流程图生成：mode_detect → retrieve → format_route → generate → verify → save"""
    from app.workflow.graphs.medcomm_graph import run_medcomm_graph

    sec_result = await db.execute(
        select(ArticleSection, Article).join(Article, ArticleSection.article_id == Article.id).where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    section, article = row
    if article.deleted_at:
        raise HTTPException(status_code=404, detail="Article not found")

    format_meta = _build_format_meta(section, article)
    cf = article.content_format or "article"
    st = section.section_type or "intro"
    pf = article.platform or "wechat"

    scene_setup_context = ""
    if cf == "drama_script" and st not in ("drama_plan", "cast_table"):
        scene_setup_context = await _get_scene_setup_context(db, article.id, pf)
    elif cf == "storyboard" and st not in ("anim_plan", "char_design"):
        scene_setup_context = await _get_section_text(db, article.id, "char_design", pf)

    planner_st = _PLANNER_SECTION_TYPE.get(cf, "planner")
    if cf in _PLANNER_FORMATS and st != planner_st:
        planner_data = await _get_planner_context(db, article.id, pf, planner_st)
        if planner_data:
            format_meta.setdefault("planner_json", planner_data)
            for key in ("story_arc", "story_type", "total_panels", "total_pages",
                        "total_sections", "main_character", "core_message",
                        "story_title", "color_theme", "layout_style", "story_line",
                        "series_theme", "visual_style", "total_cards"):
                if key in planner_data and key not in format_meta:
                    format_meta[key] = planner_data[key]
            panels_or_pages = (planner_data.get("panels") or planner_data.get("pages")
                               or planner_data.get("sections") or planner_data.get("cards") or [])
            format_meta.setdefault("planner_items", panels_or_pages)

    prior_sections_context = await _get_prior_sections_context(db, article.id, cf, st, pf)

    initial_state = {
        "article_id": article.id,
        "section_id": section.id,
        "topic": article.topic or "",
        "content_format": cf,
        "section_type": st,
        "target_audience": article.target_audience or "public",
        "platform": pf,
        "specialty": article.specialty or "",
        "model_hint": "default",
        "article_default_model": getattr(article, "default_model", None),
        "generate_mode": "new",
        "format_meta": format_meta,
        "scene_setup_context": scene_setup_context,
        "prior_sections_context": prior_sections_context,
        "user_id": getattr(article, "user_id", None) or 1,
        "target_word_count": getattr(article, "target_word_count", None),
        "skip_sections": getattr(article, "skip_sections", None),
    }
    try:
        final = await run_medcomm_graph(initial_state)
        if final.get("error"):
            raise HTTPException(status_code=500, detail=final["error"])
        return {
            "content": final.get("verified_content", final.get("generated_content", "")),
            "verify_report": final.get("verify_report"),
            "image_suggestions": final.get("image_suggestions", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sections/{section_id}/generate")
async def generate_section(
    section_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式生成章节内容"""
    sec_result = await db.execute(
        select(ArticleSection, Article).join(Article, ArticleSection.article_id == Article.id).where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    section, article = row
    if article.deleted_at:
        raise HTTPException(status_code=404, detail="Article not found")

    # ── SaaS 积分预检 + 会话追踪（单章）───────────────────────
    sec_saas_user_id: int | None = None
    sec_estimated_cost = Decimal("0")
    sec_session_id: str | None = None
    sec_is_free_gen = False
    if is_saas():
        from app.core.deps import get_current_user as _get_user
        from app.models.user import User as _User
        user: _User = await _get_user(request, db)
        sec_saas_user_id = user.id

        from app.core.rate_limit import check_generate_rate
        await check_generate_rate(user.id)

        sec_target_wc = getattr(article, "target_word_count", None) or 2000
        total_sections = await db.execute(
            select(func.count(ArticleSection.id)).where(ArticleSection.article_id == article.id)
        )
        num_sections = max(total_sections.scalar() or 1, 1)
        from app.services.credit.pricing import calc_generation_cost
        sec_estimated_cost = (calc_generation_cost(sec_target_wc) / Decimal(num_sections)).quantize(Decimal("0.01"))
        sec_estimated_cost = max(sec_estimated_cost, Decimal("1"))

        if not user.free_generation_used:
            sec_is_free_gen = True
        else:
            from app.services.streaming_session import (
                start_streaming_session, TooManyConcurrentStreamsError,
            )
            from app.services.credit.service import InsufficientCreditsError
            try:
                sec_session_id = await start_streaming_session(
                    user.id, "generate_section", sec_estimated_cost, db,
                    article_id=article.id, section_id=section.id,
                )
                await db.commit()
            except InsufficientCreditsError as e:
                raise HTTPException(
                    status_code=402,
                    detail=f"积分不足：需要 {e.required} 积分，当前可用 {e.available} 积分",
                )
            except TooManyConcurrentStreamsError as e:
                raise HTTPException(status_code=429, detail=str(e))

    a_id, s_id = article.id, section.id
    cf = article.content_format or "article"
    st = section.section_type or "intro"
    pf = article.platform or "wechat"

    if _skip_article_legacy_intro(cf, st):
        raise HTTPException(
            status_code=400,
            detail="图文文章已不再使用独立「引言」章节，正文承担开篇引入。请使用一键生成全文或单独生成「正文」等章节。",
        )

    format_meta = _build_format_meta(section, article)
    scene_setup_context = ""
    if cf == "drama_script" and st not in ("drama_plan", "cast_table"):
        scene_setup_context = await _get_scene_setup_context(db, article.id, pf)
    elif cf == "storyboard" and st not in ("anim_plan", "char_design"):
        scene_setup_context = await _get_section_text(db, article.id, "char_design", pf)

    planner_st = _PLANNER_SECTION_TYPE.get(cf, "planner")
    if cf in _PLANNER_FORMATS and st != planner_st:
        planner_data = await _get_planner_context(db, article.id, pf, planner_st)
        if planner_data:
            format_meta.setdefault("planner_json", planner_data)
            for key in ("story_arc", "story_type", "total_panels", "total_pages",
                        "total_sections", "main_character", "core_message",
                        "story_title", "color_theme", "layout_style", "story_line",
                        "series_theme", "visual_style", "total_cards"):
                if key in planner_data and key not in format_meta:
                    format_meta[key] = planner_data[key]
            panels_or_pages = (planner_data.get("panels") or planner_data.get("pages")
                               or planner_data.get("sections") or planner_data.get("cards") or [])
            format_meta.setdefault("planner_items", panels_or_pages)

    async def event_stream():
        from app.services.streaming_session import StreamingTokenCounter
        token_counter = StreamingTokenCounter(sec_session_id or "")
        stream_completed = False
        last_verify_report = None

        try:
            async for evt in generate_section_stream(
                article_id=a_id,
                section_id=s_id,
                topic=article.topic or "",
                content_format=cf,
                section_type=st,
                target_audience=article.target_audience or "public",
                platform=pf,
                specialty=article.specialty or "",
                article_default_model=article.default_model,
                format_meta=format_meta,
                scene_setup_context=scene_setup_context,
                target_word_count=getattr(article, "target_word_count", None),
                skip_sections=getattr(article, "skip_sections", None),
            ):
                if evt.get("type") == "verify_report" and evt.get("report") is not None:
                    last_verify_report = evt["report"]
                if evt.get("type") == "delta" and evt.get("text"):
                    await token_counter.add_output_tokens(evt["text"])
                if evt.get("type") == "done" and evt.get("content"):
                    stream_completed = True
                    # SaaS: 零宽字符隐写水印
                    _gen_content = evt["content"]
                    if is_saas() and sec_saas_user_id:
                        try:
                            from app.services.security.watermark import embed_watermark
                            _gen_content = embed_watermark(_gen_content, sec_saas_user_id)
                        except Exception:
                            pass
                    from app.services.content_version import save_node
                    from app.services.med_claim_marks import apply_med_claim_marks_to_doc
                    from app.services.markdown_to_tiptap import markdown_to_tiptap
                    lock = get_domain_lock("articles")
                    async with lock:
                        async with AsyncSessionLocal() as sess:
                            doc = markdown_to_tiptap(_gen_content)
                            doc = apply_med_claim_marks_to_doc(doc, last_verify_report)
                            await save_node(
                                sess,
                                article_id=a_id,
                                section_id=s_id,
                                content_json=doc,
                                version_type="ai_generated",
                                platform=article.platform or "wechat",
                                verify_report=last_verify_report,
                            )
                            sug_list = evt.get("image_suggestions")
                            if sug_list:
                                await sess.execute(
                                    update(ArticleSection)
                                    .where(ArticleSection.id == s_id)
                                    .values(image_suggestions=sug_list)
                                )
                            await sess.commit()
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

                if evt.get("type") == "done" and evt.get("content"):
                    # ── 生成后审核：敏感词扫描 ──
                    if is_saas() and sec_saas_user_id:
                        try:
                            from app.services.moderation import scan_generation_output
                            async with AsyncSessionLocal() as mod_sess:
                                mod_result = await scan_generation_output(
                                    evt["content"], sec_saas_user_id, mod_sess,
                                    article_id=a_id, section_id=s_id,
                                )
                                if mod_result.matches:
                                    mod_evt = {
                                        "type": "moderation_warning",
                                        "level": mod_result.highest_level,
                                        "message": mod_result.message,
                                        "matches": [{"word": m.word, "level": m.level, "rule": m.rule_name}
                                                    for m in mod_result.matches],
                                    }
                                    yield f"data: {json.dumps(mod_evt, ensure_ascii=False)}\n\n"
                        except Exception:
                            pass

                    try:
                        title_evt = await _auto_generate_title_if_complete(a_id)
                        if title_evt:
                            yield f"data: {json.dumps(title_evt, ensure_ascii=False)}\n\n"
                    except Exception as te:
                        import logging
                        logging.getLogger(__name__).warning("auto title generation failed: %s", te)
        except GeneratorExit:
            pass

        # ── 单章 SaaS 积分结算 ──
        if sec_saas_user_id and is_saas():
            try:
                async with AsyncSessionLocal() as settle_db:
                    if sec_is_free_gen:
                        from app.models.user import User as _U2
                        _u = await settle_db.get(_U2, sec_saas_user_id, with_for_update=True)
                        if _u:
                            _u.free_generation_used = True
                            await settle_db.commit()
                    elif sec_session_id:
                        from app.services.streaming_session import (
                            complete_streaming_session, abort_streaming_session,
                        )
                        if stream_completed:
                            await complete_streaming_session(
                                sec_session_id,
                                token_counter.tokens_in,
                                token_counter.tokens_out,
                                settle_db,
                            )
                        else:
                            await abort_streaming_session(
                                sec_session_id, settle_db,
                                reason="client_disconnect",
                            )
                        await settle_db.commit()
            except Exception as _ce:
                import logging
                logging.getLogger(__name__).error("[generate-section] 积分结算异常: %s", _ce)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/articles/{article_id}/generate-all")
async def generate_all_sections(
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式按顺序生成全文所有章节，每一章节完成后保存，
    下一章节自动注入前序内容，保证章节间的逻辑衔接。"""
    import logging
    _log = logging.getLogger(__name__)

    art_result = await db.execute(select(Article).where(Article.id == article_id))
    article = art_result.scalar_one_or_none()
    if not article or article.deleted_at:
        raise HTTPException(status_code=404, detail="Article not found")

    # ── SaaS 积分预检 + 会话追踪 ────────────────────────────────
    saas_user_id: int | None = None
    estimated_cost = Decimal("0")
    is_free_gen = False
    all_session_id: str | None = None
    if is_saas():
        from app.core.deps import get_current_user
        from app.models.user import User
        user: User = await get_current_user(request, db)
        saas_user_id = user.id

        from app.core.rate_limit import check_generate_rate as _check_gen_rate
        await _check_gen_rate(user.id)

        target_wc = getattr(article, "target_word_count", None) or 2000
        from app.services.credit.pricing import calc_generation_cost
        estimated_cost = calc_generation_cost(target_wc)
        if not user.free_generation_used:
            is_free_gen = True
            _log.info("[generate-all] 用户 %d 首次免费生成，跳过扣费", user.id)
        else:
            from app.services.streaming_session import (
                start_streaming_session, TooManyConcurrentStreamsError,
            )
            from app.services.credit.service import InsufficientCreditsError
            try:
                all_session_id = await start_streaming_session(
                    user.id, "generate_all", estimated_cost, db,
                    article_id=article.id,
                )
                await db.commit()
            except InsufficientCreditsError as e:
                raise HTTPException(
                    status_code=402,
                    detail=f"积分不足：需要 {e.required} 积分，当前可用 {e.available} 积分",
                )
            except TooManyConcurrentStreamsError as e:
                raise HTTPException(status_code=429, detail=str(e))

    cf = article.content_format or "article"
    pf = article.platform or "wechat"
    skip_list = set(getattr(article, "skip_sections", None) or [])
    art_topic = article.topic or ""
    art_audience = article.target_audience or "public"
    art_specialty = article.specialty or ""
    art_default_model = article.default_model
    art_word_count = getattr(article, "target_word_count", None)
    art_skip_sections = getattr(article, "skip_sections", None)

    sec_result = await db.execute(
        select(ArticleSection)
        .where(ArticleSection.article_id == article_id)
        .order_by(ArticleSection.order_num)
    )
    all_sections = sec_result.scalars().all()
    section_infos = [
        {"id": s.id, "section_type": s.section_type or "", "order_num": s.order_num,
         "format_meta": dict((s.format_meta or {}) if hasattr(s, "format_meta") else {})}
        for s in all_sections
    ]

    async def event_stream():
        from app.services.content_version import save_node
        from app.services.markdown_to_tiptap import markdown_to_tiptap
        from app.services.med_claim_marks import apply_med_claim_marks_to_doc
        from app.services.streaming_session import StreamingTokenCounter

        token_counter = StreamingTokenCounter(all_session_id or "")

        total = len([
            si for si in section_infos
            if si["section_type"] not in skip_list and not _skip_article_legacy_intro(cf, si["section_type"])
        ])
        completed = 0

        yield f"data: {json.dumps({'type': 'batch_start', 'total_sections': total}, ensure_ascii=False)}\n\n"

        try:
            for si in section_infos:
                st = si["section_type"]
                sec_id = si["id"]
                if st in skip_list or _skip_article_legacy_intro(cf, st):
                    continue

                _log.info("[generate-all] starting section %s (id=%d)", st, sec_id)
                yield f"data: {json.dumps({'type': 'section_start', 'section_id': sec_id, 'section_type': st, 'index': completed + 1, 'total': total}, ensure_ascii=False)}\n\n"

                format_meta = dict(si.get("format_meta") or {})
                scene_setup_context = ""
                async with AsyncSessionLocal() as _db:
                    if cf == "drama_script" and st not in ("drama_plan", "cast_table"):
                        scene_setup_context = await _get_scene_setup_context(_db, article_id, pf)
                    elif cf == "storyboard" and st not in ("anim_plan", "char_design"):
                        scene_setup_context = await _get_section_text(_db, article_id, "char_design", pf)

                    planner_st = _PLANNER_SECTION_TYPE.get(cf, "planner")
                    if cf in _PLANNER_FORMATS and st != planner_st:
                        planner_data = await _get_planner_context(_db, article_id, pf, planner_st)
                        if planner_data:
                            format_meta.setdefault("planner_json", planner_data)
                            for key in ("story_arc", "story_type", "total_panels", "total_pages",
                                        "total_sections", "main_character", "core_message",
                                        "story_title", "color_theme", "layout_style", "story_line",
                                        "series_theme", "visual_style", "total_cards"):
                                if key in planner_data and key not in format_meta:
                                    format_meta[key] = planner_data[key]
                            panels_or_pages = (planner_data.get("panels") or planner_data.get("pages")
                                               or planner_data.get("sections") or planner_data.get("cards") or [])
                            format_meta.setdefault("planner_items", panels_or_pages)

                last_verify_report = None
                section_content = ""
                image_suggestions = None

                async for evt in generate_section_stream(
                    article_id=article_id,
                    section_id=sec_id,
                    topic=art_topic,
                    content_format=cf,
                    section_type=st,
                    target_audience=art_audience,
                    platform=pf,
                    specialty=art_specialty,
                    article_default_model=art_default_model,
                    format_meta=format_meta,
                    scene_setup_context=scene_setup_context,
                    target_word_count=art_word_count,
                    skip_sections=art_skip_sections,
                ):
                    if evt.get("type") == "verify_report" and evt.get("report") is not None:
                        last_verify_report = evt["report"]
                    if evt.get("type") == "delta":
                        await token_counter.add_output_tokens(evt.get("text", ""))
                        yield f"data: {json.dumps({'type': 'delta', 'text': evt.get('text', ''), 'section_id': sec_id}, ensure_ascii=False)}\n\n"
                    if evt.get("type") == "rewriting":
                        yield f"data: {json.dumps({'type': 'rewriting', 'message': evt.get('message', ''), 'section_id': sec_id}, ensure_ascii=False)}\n\n"
                    if evt.get("type") == "rewritten_content" and evt.get("content"):
                        yield f"data: {json.dumps({'type': 'rewritten_content', 'content': evt['content'], 'section_id': sec_id}, ensure_ascii=False)}\n\n"
                    if evt.get("type") == "done" and evt.get("content"):
                        section_content = evt["content"]
                        image_suggestions = evt.get("image_suggestions")

                if section_content:
                    lock = get_domain_lock("articles")
                    async with lock:
                        async with AsyncSessionLocal() as sess:
                            doc = markdown_to_tiptap(section_content)
                            doc = apply_med_claim_marks_to_doc(doc, last_verify_report)
                            await save_node(
                                sess,
                                article_id=article_id,
                                section_id=sec_id,
                                content_json=doc,
                                version_type="ai_generated",
                                platform=pf,
                                verify_report=last_verify_report,
                            )
                            if image_suggestions:
                                await sess.execute(
                                    update(ArticleSection)
                                    .where(ArticleSection.id == sec_id)
                                    .values(image_suggestions=image_suggestions)
                                )
                            await sess.commit()
                    _log.info("[generate-all] section %s saved", st)

                completed += 1
                yield f"data: {json.dumps({'type': 'section_done', 'section_id': sec_id, 'section_type': st, 'index': completed, 'total': total}, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            pass

        try:
            title_evt = await _auto_generate_title_if_complete(article_id)
            if title_evt:
                yield f"data: {json.dumps(title_evt, ensure_ascii=False)}\n\n"
        except Exception as te:
            _log.warning("auto title generation failed: %s", te)

        # ── SaaS 积分结算 ────
        if saas_user_id and is_saas():
            try:
                async with AsyncSessionLocal() as settle_db:
                    if is_free_gen:
                        from app.models.user import User as _User
                        _u = await settle_db.get(_User, saas_user_id, with_for_update=True)
                        if _u:
                            _u.free_generation_used = True
                            await settle_db.commit()
                        _log.info("[generate-all] 首次免费生成已标记 user=%d", saas_user_id)
                    elif all_session_id:
                        from app.services.streaming_session import (
                            complete_streaming_session, abort_streaming_session,
                        )
                        if completed >= total and total > 0:
                            await complete_streaming_session(
                                all_session_id,
                                token_counter.tokens_in,
                                token_counter.tokens_out,
                                settle_db,
                            )
                        else:
                            await abort_streaming_session(
                                all_session_id, settle_db,
                                reason="incomplete" if completed > 0 else "client_disconnect",
                            )
                        await settle_db.commit()
            except Exception as credit_err:
                _log.error("[generate-all] 积分结算异常: %s", credit_err)

        yield f"data: {json.dumps({'type': 'batch_done', 'completed': completed}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sections/{section_id}/recheck")
async def recheck_section(
    section_id: int,
    db: AsyncSession = Depends(get_db),
):
    """对已有内容补跑 AI 味检测 + 共识缺失检测 + 溯源统计，更新 verify_report"""
    from app.services.verification.pipeline import (
        detect_ai_patterns,
        extract_provenance_summary,
        detect_uncited_medical_facts,
    )

    sec_result = await db.execute(
        select(ArticleSection, Article)
        .join(Article, ArticleSection.article_id == Article.id)
        .where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    section, article = row

    platform = article.platform or "wechat"
    cont_result = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == section_id,
            ArticleContent.is_current == True,
        )
    )
    candidates = cont_result.scalars().all()
    content_row = (
        next((c for c in candidates if c.platform == platform), None)
        or next((c for c in candidates if c.platform is None), candidates[0] if candidates else None)
    )
    if not content_row or not content_row.content_json:
        raise HTTPException(status_code=404, detail="No content to check")

    doc = json.loads(content_row.content_json)

    _BLOCK_TYPES = {"paragraph", "heading", "blockquote", "listItem", "codeBlock"}

    def _extract_text(node):
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return "".join(_extract_text(x) for x in node)
        if isinstance(node, dict):
            if node.get("type") == "text":
                return node.get("text", "")
            parts = "".join(_extract_text(x) for x in node.get("content", []))
            if node.get("type") in _BLOCK_TYPES:
                return parts + "\n\n"
            return parts
        return ""

    plain_text = _extract_text(doc).strip()
    if not plain_text:
        raise HTTPException(status_code=404, detail="Content is empty")

    ai_patterns = detect_ai_patterns(plain_text)
    provenance = extract_provenance_summary(plain_text)
    uncited_facts = detect_uncited_medical_facts(plain_text)

    from app.services.verification.pipeline import detect_ai_patterns_by_paragraph
    paragraph_analysis = detect_ai_patterns_by_paragraph(plain_text)
    high_risk_paras = sum(1 for p in paragraph_analysis if p["risk_level"] == "high")

    report = content_row.verify_report or {}
    report["ai_patterns"] = ai_patterns
    report["ai_patterns"]["high_risk_paragraphs"] = high_risk_paras
    report["provenance"] = provenance
    report["uncited_facts"] = uncited_facts

    lock = get_domain_lock("articles")
    async with lock:
        content_row.verify_report = report
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(content_row, "verify_report")
        await db.commit()

    return {"ok": True, "verify_report": report}


@router.get("/sections/{section_id}/aigc-check")
async def aigc_check_section(
    section_id: int,
    db: AsyncSession = Depends(get_db),
):
    """段落级AIGC特征检测：返回每个段落的AI风险等级、具体问题和改写建议"""
    from app.services.verification.pipeline import (
        detect_ai_patterns,
        detect_ai_patterns_by_paragraph,
    )

    sec_result = await db.execute(
        select(ArticleSection, Article)
        .join(Article, ArticleSection.article_id == Article.id)
        .where(ArticleSection.id == section_id)
    )
    row = sec_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    section, article = row

    platform = article.platform or "wechat"
    cont_result = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == section_id,
            ArticleContent.is_current == True,
        )
    )
    candidates = cont_result.scalars().all()
    content_row = (
        next((c for c in candidates if c.platform == platform), None)
        or next((c for c in candidates if c.platform is None), candidates[0] if candidates else None)
    )
    if not content_row or not content_row.content_json:
        raise HTTPException(status_code=404, detail="No content to check")

    doc = json.loads(content_row.content_json)

    _BLOCK_TYPES = {"paragraph", "heading", "blockquote", "listItem", "codeBlock"}

    def _extract_text(node):
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return "".join(_extract_text(x) for x in node)
        if isinstance(node, dict):
            if node.get("type") == "text":
                return node.get("text", "")
            parts = "".join(_extract_text(x) for x in node.get("content", []))
            if node.get("type") in _BLOCK_TYPES:
                return parts + "\n\n"
            return parts
        return ""

    plain_text = _extract_text(doc).strip()
    if not plain_text:
        raise HTTPException(status_code=404, detail="Content is empty")

    overall = detect_ai_patterns(plain_text)
    paragraphs = detect_ai_patterns_by_paragraph(plain_text)

    high_risk = [p for p in paragraphs if p["risk_level"] == "high"]
    medium_risk = [p for p in paragraphs if p["risk_level"] == "medium"]

    pattern_score = overall.get("score", 100)
    para_penalty = len(high_risk) * 8 + len(medium_risk) * 4
    adjusted_score = max(0, min(pattern_score, pattern_score - para_penalty))

    summary = {
        "overall_score": adjusted_score,
        "pattern_score": pattern_score,
        "paragraph_penalty": para_penalty,
        "needs_polish": adjusted_score < 60 or overall.get("needs_polish", False),
        "total_paragraphs": len(paragraphs),
        "high_risk_count": len(high_risk),
        "medium_risk_count": len(medium_risk),
        "low_risk_count": len(paragraphs) - len(high_risk) - len(medium_risk),
    }

    return {
        "ok": True,
        "summary": summary,
        "overall": overall,
        "paragraphs": [
            {
                "index": p["index"],
                "text": p["text"],
                "full_text": p.get("full_text", p["text"]),
                "risk_level": p["risk_level"],
                "issues": p["issues"],
                "suggestions": p["suggestions"],
                "sentence_stats": p["sentence_stats"],
            }
            for p in paragraphs
        ],
    }


@router.post("/articles/{article_id}/aigc-check")
async def aigc_check_article(
    article_id: int,
    body: dict | None = None,
    db: AsyncSession = Depends(get_db),
):
    """全文级 AIGC 段落检测：优先使用前端传入的 content_json，否则从 DB 合并"""
    from app.services.verification.pipeline import (
        detect_ai_patterns,
        detect_ai_patterns_by_paragraph,
    )

    _BLOCK_TYPES = {"paragraph", "heading", "blockquote", "listItem", "codeBlock"}

    def _extract_text(node):
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return "".join(_extract_text(x) for x in node)
        if isinstance(node, dict):
            if node.get("type") == "text":
                return node.get("text", "")
            parts = "".join(_extract_text(x) for x in node.get("content", []))
            if node.get("type") in _BLOCK_TYPES:
                return parts + "\n\n"
            return parts
        return ""

    content_json = (body or {}).get("content_json")
    if content_json and isinstance(content_json, dict):
        plain_text = _extract_text(content_json).strip()
    else:
        result = await db.execute(
            select(Article).where(Article.id == article_id, Article.deleted_at.is_(None))
        )
        article = result.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        platform = article.platform or "wechat"
        cf = article.content_format or "article"

        sec_result = await db.execute(
            select(ArticleSection)
            .where(ArticleSection.article_id == article_id)
            .order_by(ArticleSection.order_num)
        )
        sections = sec_result.scalars().all()

        cont_result = await db.execute(
            select(ArticleContent).where(
                ArticleContent.section_id.in_([s.id for s in sections]),
                ArticleContent.is_current == True,
            )
        )
        all_contents = cont_result.scalars().all()
        content_by_section: dict[int, list] = {}
        for c in all_contents:
            content_by_section.setdefault(c.section_id, []).append(c)

        all_text_parts: list[str] = []
        for sec in sections:
            if _skip_article_legacy_intro(cf, sec.section_type):
                continue
            candidates = content_by_section.get(sec.id, [])
            c = next((x for x in candidates if x.platform == platform), None) or \
                next((x for x in candidates if x.platform is None), candidates[0] if candidates else None)
            if not c or not c.content_json:
                continue
            try:
                doc = json.loads(c.content_json)
            except Exception:
                continue
            part = _extract_text(doc).strip()
            if part:
                all_text_parts.append(part)

        plain_text = "\n\n".join(all_text_parts).strip()

    if not plain_text:
        raise HTTPException(status_code=404, detail="No content to check")

    overall = detect_ai_patterns(plain_text)
    paragraphs = detect_ai_patterns_by_paragraph(plain_text)

    high_risk = [p for p in paragraphs if p["risk_level"] == "high"]
    medium_risk = [p for p in paragraphs if p["risk_level"] == "medium"]

    pattern_score = overall.get("score", 100)
    para_penalty = len(high_risk) * 8 + len(medium_risk) * 4
    adjusted_score = max(0, min(pattern_score, pattern_score - para_penalty))

    summary = {
        "overall_score": adjusted_score,
        "pattern_score": pattern_score,
        "paragraph_penalty": para_penalty,
        "needs_polish": adjusted_score < 60 or overall.get("needs_polish", False),
        "total_paragraphs": len(paragraphs),
        "high_risk_count": len(high_risk),
        "medium_risk_count": len(medium_risk),
        "low_risk_count": len(paragraphs) - len(high_risk) - len(medium_risk),
    }

    return {
        "ok": True,
        "summary": summary,
        "overall": overall,
        "paragraphs": [
            {
                "index": p["index"],
                "text": p["text"],
                "full_text": p.get("full_text", p["text"]),
                "risk_level": p["risk_level"],
                "issues": p["issues"],
                "suggestions": p["suggestions"],
                "sentence_stats": p["sentence_stats"],
            }
            for p in paragraphs
        ],
    }


@router.post("/articles/batch-delete")
async def batch_delete_articles(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """批量软删除"""
    from datetime import datetime

    ids = data.get("ids", [])
    if not ids:
        return {"ok": True, "deleted": 0}
    now = datetime.utcnow()
    lock = get_domain_lock("articles")
    async with lock:
        result = await db.execute(
            select(Article).where(Article.id.in_(ids), Article.deleted_at.is_(None))
        )
        articles = result.scalars().all()
        for a in articles:
            a.deleted_at = now
        await db.commit()
    return {"ok": True, "deleted": len(articles)}


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """软删除"""
    from datetime import datetime

    lock = get_domain_lock("articles")
    async with lock:
        result = await db.execute(select(Article).where(Article.id == article_id))
        article = result.scalar_one_or_none()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        article.deleted_at = datetime.utcnow()
        await db.commit()
    return {"ok": True}


def article_to_dict(a: Article) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "topic": a.topic,
        "content_format": a.content_format,
        "platform": a.platform,
        "target_audience": a.target_audience,
        "reading_level": getattr(a, "reading_level", None),
        "specialty": a.specialty,
        "status": a.status,
        "current_stage": a.current_stage,
        "image_stage": a.image_stage,
        "target_word_count": a.target_word_count,
        "skip_sections": a.skip_sections or [],
        "word_count": a.word_count,
        "visual_continuity_prompt": a.visual_continuity_prompt or "",
        "image_series_seed_base": a.image_series_seed_base,
        "analysis_report": a.analysis_report,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


# ── AI 辅助写作 ──────────────────────────────────────────────────


class AiAssistRequest(BaseModel):
    selected_text: str
    action: str  # continue | polish | rewrite | simplify | expand | custom
    context_before: str = ""
    context_after: str = ""
    custom_instruction: str = ""
    article_id: int | None = None


_AI_ASSIST_PROMPTS: dict[str, str] = {
    "continue": (
        "你是专业的医学科普写作助手。请根据已有内容自然续写，保持风格一致、逻辑连贯。\n\n"
        "【上文】\n{context_before}\n\n【当前段落】\n{selected_text}\n\n"
        "请直接续写，不要输出额外说明。"
    ),
    "polish": (
        "你是专业的中文润色助手。请对以下文本进行润色，使语言更流畅、专业、易读。"
        "保持原意不变，不增删核心信息。\n\n【原文】\n{selected_text}\n\n"
        "请直接输出润色后的文本，不要输出额外说明。"
    ),
    "rewrite": (
        "你是专业的改写助手。请用不同的表达方式改写以下文本，保持核心含义不变。\n\n"
        "【原文】\n{selected_text}\n\n请直接输出改写后的文本，不要输出额外说明。"
    ),
    "simplify": (
        "你是科普通俗化助手。请将以下专业内容改写为普通读者也能轻松理解的通俗表述。\n\n"
        "【原文】\n{selected_text}\n\n请直接输出通俗化后的文本，不要输出额外说明。"
    ),
    "expand": (
        "你是专业的医学科普写作助手。请将以下内容扩展，补充更多细节、解释或例子，使读者更容易理解。\n\n"
        "【上文】\n{context_before}\n\n【待扩展段落】\n{selected_text}\n\n"
        "请直接输出扩展后的文本，不要输出额外说明。"
    ),
}


@router.post("/ai-assist")
async def ai_assist_stream(req: AiAssistRequest):
    """AI 辅助写作：续写 / 润色 / 改写 / 精简 / 扩展，SSE 流式返回"""
    import logging
    _log = logging.getLogger(__name__)

    if not req.selected_text.strip():
        raise HTTPException(status_code=400, detail="未提供选中文本")

    from app.services.llm.openai_client import chat_completion
    from app.services.llm.manager import TaskTier

    if req.action == "custom":
        if not req.custom_instruction.strip():
            raise HTTPException(status_code=400, detail="自定义指令不能为空")
        prompt = (
            f"你是专业的医学科普写作助手。请按以下要求处理文本：\n{req.custom_instruction}\n\n"
            f"【原文】\n{req.selected_text}\n\n请直接输出结果，不要输出额外说明。"
        )
    else:
        tpl = _AI_ASSIST_PROMPTS.get(req.action)
        if not tpl:
            raise HTTPException(status_code=400, detail=f"不支持的操作类型: {req.action}")
        prompt = tpl.format(
            selected_text=req.selected_text[:3000],
            context_before=(req.context_before or "")[-1500:],
            context_after=(req.context_after or "")[:500],
        )

    async def _stream():
        try:
            gen = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                task=TaskTier.BALANCED,
            )
            async for chunk in gen:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            _log.warning("ai-assist stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

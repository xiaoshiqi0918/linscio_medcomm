"""MedComm 科普写作 API"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal, get_domain_lock
from app.models.article import Article, ArticleSection, ArticleContent
from app.services.medcomm.generator import generate_section_stream

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CreateArticleRequest(BaseModel):
    content_format: str = "article"
    topic: str = ""
    platform: str = "wechat"
    target_audience: str = "public"
    reading_level: str | None = None
    specialty: str = ""
    template_id: int | None = None
    default_model: str | None = None


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
    db: AsyncSession = Depends(get_db),
):
    """新建文章"""
    lock = get_domain_lock("articles")
    async with lock:
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
            status="draft",
            current_stage="outline",
        )
        db.add(article)
        await db.flush()

        # 创建默认章节（按形式由 format_router 定义，此处简化为首章）
        from app.services.format_router import get_format_sections

        sections = get_format_sections(req.content_format) or ["intro"]
        for i, st in enumerate(sections):
            if isinstance(st, dict):
                section_type = st.get("section_type", st.get("id", f"section_{i+1}"))
                title = st.get("title", section_type)
            else:
                section_type = str(st)
                title = section_type
            sec = ArticleSection(
                article_id=article.id,
                section_type=section_type,
                title=title,
                order_num=i + 1,
                status="pending",
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
    db: AsyncSession = Depends(get_db),
):
    """导出前检查：数据占位符、绝对化表述、孤儿引用，有未处理警告时需用户确认"""
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
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/articles/{article_id}/export")
async def export_article_route(
    article_id: int,
    fmt: str = Query("html", alias="format", description="html / docx / md / pdf / txt"),
    platform: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """导出文章：html/docx/md/txt 走稳定合并导出；pdf 走 WeasyPrint 等形式路由。"""
    from app.services.export.router import export_article as do_export
    from app.services.export.utils import (
        load_article_sections,
        prepend_export_title_markdown,
        prepend_export_title_plain,
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
                lines.append(f"[{i}] {CitationFormatter(p).format('apa')}")

        ext_result = await db.execute(
            select(ArticleExternalReference)
            .where(ArticleExternalReference.article_id == article_id)
            .order_by(ArticleExternalReference.id.asc())
        )
        ext_refs = ext_result.scalars().all()
        offset = len(lines)
        for j, r in enumerate(ext_refs, 1):
            authors = ""
            try:
                arr = json.loads(r.authors) if isinstance(r.authors, str) else (r.authors or [])
                names = [a.get("name", "") for a in (arr or []) if isinstance(a, dict)]
                authors = "; ".join([n for n in names if n]) if names else ""
            except Exception:
                authors = ""
            year = r.year or ""
            journal = r.journal or ""
            doi = (r.doi or "").strip()
            tail = f" DOI:{doi}" if doi else ""
            base = " · ".join([x for x in [authors, journal, str(year) if year else ""] if x])
            lines.append(f"[{offset + j}] {r.title}{(' — ' + base) if base else ''}{tail}")
        if not lines:
            return ""
        return "\n\n## 参考文献\n\n" + "\n".join(lines)

    def _merged_export(article, parts, export_fmt: str, refs_text: str = "") -> tuple[bytes, str, str]:
        """各章节合并后的通用导出（与 HtmlDocxExporter 主路径一致，绕过形式路由差异）"""
        base_name = (article.topic or "article").replace("/", "-")
        body = "\n\n".join(f"## {t}\n\n{b}" for t, b, _ in parts) + (refs_text or "")
        full_text = body
        if export_fmt == "html":
            html = html_docx.to_html(article, full_text)
            return html.encode("utf-8"), "text/html; charset=utf-8", f"{base_name}.html"
        if export_fmt == "docx":
            try:
                docx_parts = [(p[0], p[1]) for p in parts]
                if refs_text:
                    docx_parts.append(("参考文献", refs_text.replace("## 参考文献", "").strip()))
                buf, fn = html_docx.to_docx(article, docx_parts)
                return buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", fn
            except Exception:
                fallback_body = "\n\n".join(f"## {t}\n\n{b}" for t, b, _ in parts) + (refs_text or "")
                txt = prepend_export_title_plain(article, fallback_body)
                return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"
        if export_fmt == "md":
            asset_block = (
                "\n\n---\n\n## 配图与资源说明\n\n"
                "- 正文中的插图若在软件内为本地或 `medcomm-image` 链接，发布到公众号/知乎/小红书前请重新上传图片并替换为平台图片地址。\n"
            )
            full_md = prepend_export_title_markdown(article, body) + asset_block
            return full_md.encode("utf-8"), "text/markdown; charset=utf-8", f"{base_name}.md"
        txt = prepend_export_title_plain(article, body)
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"

    normalized = (fmt or "html").strip().lower()
    if normalized not in ("html", "docx", "md", "pdf", "txt"):
        normalized = "txt"

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
    d["sections"] = [{"id": s.id, "section_type": s.section_type, "title": s.title, "order_num": s.order_num} for s in sections]
    return d


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
    "hook": ("00:00", "00:03"),
    "body_1": ("00:03", "00:15"),
    "body_2": ("00:15", "00:30"),
    "body_3": ("00:30", "00:45"),
    "summary": ("00:45", "00:55"),
    "cta": ("00:55", "01:00"),
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
            meta = {"panel_index": idx, "total_panels": len(panel_types) or 6}
        except ValueError:
            meta = {"panel_index": section.order_num or 1, "total_panels": 6}
    elif cf == "oral_script" and not meta.get("start_time"):
        start, end = _ORAL_TIME_MAP.get(st, ("00:00", "01:00"))
        body_idx = None
        if st.startswith("body_"):
            try:
                body_idx = int(st.replace("body_", ""))
            except ValueError:
                body_idx = 1
        meta["start_time"] = start
        meta["end_time"] = end
        if body_idx:
            meta["segment_number"] = body_idx
            meta["total_segments"] = sum(1 for t in types_list if t.startswith("body_")) or 3
    elif cf == "storyboard" and st.startswith("frame_"):
        if not meta.get("frame_index"):
            try:
                idx = int(st.replace("frame_", ""))
                meta["frame_index"] = idx
                meta["total_frames"] = len([t for t in types_list if t.startswith("frame_")]) or 6
                meta["duration"] = "10s"
            except ValueError:
                meta["frame_index"] = section.order_num or 1
                meta["total_frames"] = 6
    elif cf == "drama_script" and (st.startswith("scene_") or st == "ending"):
        if not meta.get("scene_index"):
            meta["scene_index"] = 4 if st == "ending" else (int(st.replace("scene_", "")) if st.replace("scene_", "").isdigit() else 1)
    elif cf == "audio_script" and not meta.get("duration_sec"):
        # 默认每段约 2-3 分钟
        meta["duration_sec"] = 150
        meta["start_time"] = 0
        meta["end_time"] = 2.5
    elif cf == "card_series" and st.startswith("card_"):
        if not meta.get("card_index"):
            try:
                idx = int(st.replace("card_", ""))
                card_types = [t for t in types_list if t.startswith("card_")]
                meta["card_index"] = idx
                meta["total_cards"] = len(card_types) or 5
                meta.setdefault("color_scheme", "blue")
            except ValueError:
                meta["card_index"] = section.order_num or 1
                meta["total_cards"] = 5
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
        if st == "planner":
            pass  # planner 不需 format_meta
        elif st.startswith("page_"):
            if not meta.get("page_index"):
                try:
                    idx = int(st.replace("page_", ""))
                    page_types = [t for t in types_list if t.startswith("page_")]
                    meta["page_index"] = idx
                    meta["total_pages"] = len(page_types) or 5
                except ValueError:
                    meta["page_index"] = section.order_num or 1
                    meta["total_pages"] = 5

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
    return await _get_section_text(db, article_id, "scene_setup", platform)


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


_PLANNER_FORMATS = {"storyboard", "comic_strip", "picture_book", "long_image"}


async def _get_planner_context(db: AsyncSession, article_id: int, platform: str) -> dict:
    """读取 planner 章节的 JSON 内容，解析为 dict 供 format_meta 合并"""
    text = await _get_section_text(db, article_id, "planner", platform)
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
    if cf == "drama_script" and (st.startswith("scene_") or st == "ending"):
        scene_setup_context = await _get_scene_setup_context(db, article.id, pf)

    if cf in _PLANNER_FORMATS and st != "planner":
        planner_data = await _get_planner_context(db, article.id, pf)
        if planner_data:
            format_meta.setdefault("planner_json", planner_data)
            for key in ("story_arc", "story_type", "total_panels", "total_pages",
                        "total_sections", "main_character", "core_message",
                        "story_title", "color_theme", "layout_style", "story_line"):
                if key in planner_data and key not in format_meta:
                    format_meta[key] = planner_data[key]
            panels_or_pages = planner_data.get("panels") or planner_data.get("pages") or planner_data.get("sections") or []
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

    a_id, s_id = article.id, section.id
    cf = article.content_format or "article"
    st = section.section_type or "intro"
    pf = article.platform or "wechat"

    format_meta = _build_format_meta(section, article)
    scene_setup_context = ""
    if cf == "drama_script" and (st.startswith("scene_") or st == "ending"):
        scene_setup_context = await _get_scene_setup_context(db, article.id, pf)

    if cf in _PLANNER_FORMATS and st != "planner":
        planner_data = await _get_planner_context(db, article.id, pf)
        if planner_data:
            format_meta.setdefault("planner_json", planner_data)
            for key in ("story_arc", "story_type", "total_panels", "total_pages",
                        "total_sections", "main_character", "core_message",
                        "story_title", "color_theme", "layout_style", "story_line"):
                if key in planner_data and key not in format_meta:
                    format_meta[key] = planner_data[key]
            panels_or_pages = planner_data.get("panels") or planner_data.get("pages") or planner_data.get("sections") or []
            format_meta.setdefault("planner_items", panels_or_pages)

    async def event_stream():
        last_verify_report = None
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
        ):
            if evt.get("type") == "verify_report" and evt.get("report") is not None:
                last_verify_report = evt["report"]
            if evt.get("type") == "done" and evt.get("content"):
                from app.services.content_version import save_node
                from app.services.med_claim_marks import apply_med_claim_marks_to_doc
                lock = get_domain_lock("articles")
                async with lock:
                    async with AsyncSessionLocal() as sess:
                        para = {"type": "paragraph", "content": [{"type": "text", "text": evt["content"]}]}
                        doc = {"type": "doc", "content": [para]}
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
                        await sess.commit()
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
        "specialty": a.specialty,
        "status": a.status,
        "current_stage": a.current_stage,
        "image_stage": a.image_stage,
        "word_count": a.word_count,
        "visual_continuity_prompt": a.visual_continuity_prompt or "",
        "image_series_seed_base": a.image_series_seed_base,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }

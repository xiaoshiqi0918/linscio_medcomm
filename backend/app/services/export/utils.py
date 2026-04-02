"""导出工具函数"""
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.article import Article, ArticleSection, ArticleContent, ArticleLiteratureBinding


def article_export_title_display(article: Any) -> str:
    """篇首标题：优先已保存的 title，否则回退 topic"""
    t = (getattr(article, "title", None) or "").strip()
    return t if t else (getattr(article, "topic", None) or "未命名").strip()


def export_meta_separator_block(article: Any) -> str:
    return (
        f"*主题：{getattr(article, 'topic', None) or '-'} · 形式：{getattr(article, 'content_format', None) or '-'} · "
        f"平台：{getattr(article, 'platform', None) or '-'}*\n\n---\n\n"
    )


def prepend_export_title_markdown(article: Any, body: str) -> str:
    td = article_export_title_display(article)
    return f"# {td}\n\n{export_meta_separator_block(article)}" + body


def prepend_export_title_plain(article: Any, body: str) -> str:
    td = article_export_title_display(article)
    return f"{td}\n\n{export_meta_separator_block(article)}" + body


def _collect_citation_refs(node: dict, out: list[dict]) -> None:
    """递归收集 citationRef 标记及 paperId，追加到 out"""
    if not isinstance(node, dict):
        return
    if node.get("type") == "text":
        for m in node.get("marks") or []:
            if m.get("type") == "citationRef":
                attrs = m.get("attrs") or {}
                pid = attrs.get("paperId")
                if pid is not None:
                    out.append({"paper_id": pid, "text": node.get("text", ""), "index": attrs.get("index")})
                return
    for c in node.get("content") or []:
        _collect_citation_refs(c, out)


def _extract_text(node: dict) -> str:
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    if node.get("type") == "image":
        src = node.get("attrs", {}).get("src", "")
        alt = node.get("attrs", {}).get("alt", "")
        if src:
            return f"\n![{alt}]({src})\n"
        return ""
    return "".join(_extract_text(c) for c in node.get("content", []))


async def load_article_sections(article_id: int, db: AsyncSession) -> tuple[Article, list[tuple[str, str, str]]]:
    """加载文章及章节内容，返回 (article, [(title, body, section_type), ...])"""
    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise ValueError("Article not found")
    sec_result = await db.execute(
        select(ArticleSection).where(ArticleSection.article_id == article_id).order_by(ArticleSection.order_num)
    )
    sections = sec_result.scalars().all()
    parts = []
    platform = article.platform or "wechat"
    for sec in sections:
        cont_result = await db.execute(
            select(ArticleContent).where(
                ArticleContent.section_id == sec.id,
                ArticleContent.is_current == True,
            )
        )
        candidates = cont_result.scalars().all()
        c = next((x for x in candidates if x.platform == platform), None) or next((x for x in candidates if x.platform is None), candidates[0] if candidates else None)
        text = ""
        if c and c.content_json:
            try:
                doc = json.loads(c.content_json)
                text = _extract_text(doc)
            except Exception:
                pass
        parts.append((sec.title or sec.section_type, text, sec.section_type))
    if not parts:
        parts = [(s.title or s.section_type, "", s.section_type) for s in sections]
    return article, parts


async def collect_orphan_citations(
    article_id: int,
    db: AsyncSession,
) -> tuple[list[dict], set[int]]:
    """
    检测正文中引用但未绑定的文献（孤儿引用）。
    返回 (orphans, valid_paper_ids)
    orphans: [{ section_id, section_title, text, paper_id, index }, ...]
    """
    art_result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = art_result.scalar_one_or_none()
    platform = (article.platform or "wechat") if article else "wechat"

    bind_result = await db.execute(
        select(ArticleLiteratureBinding.paper_id).where(
            ArticleLiteratureBinding.article_id == article_id
        )
    )
    valid_paper_ids = {r[0] for r in bind_result.fetchall()}

    sec_result = await db.execute(
        select(ArticleSection).where(ArticleSection.article_id == article_id).order_by(ArticleSection.order_num)
    )
    sections = sec_result.scalars().all()
    orphans = []
    for sec in sections:
        cont_result = await db.execute(
            select(ArticleContent).where(
                ArticleContent.section_id == sec.id,
                ArticleContent.is_current == True,
            )
        )
        candidates = cont_result.scalars().all()
        c = next((x for x in candidates if x.platform == platform), None) or next((x for x in candidates if x.platform is None), candidates[0] if candidates else None)
        if not c or not c.content_json:
            continue
        try:
            doc = json.loads(c.content_json)
        except Exception:
            continue
        refs = []
        _collect_citation_refs(doc, refs)
        for r in refs:
            pid = r.get("paper_id")
            if pid is not None and pid not in valid_paper_ids:
                orphans.append({
                    "section_id": sec.id,
                    "section_title": sec.title or sec.section_type,
                    "text": r.get("text", ""),
                    "paper_id": pid,
                    "index": r.get("index"),
                })
    return orphans, valid_paper_ids

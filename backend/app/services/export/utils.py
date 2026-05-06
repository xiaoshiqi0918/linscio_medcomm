"""导出工具函数"""
import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.article import Article, ArticleSection, ArticleContent, ArticleLiteratureBinding


def _short_authors_for_export(authors_raw: str | None) -> str:
    """authors 列可能为 JSON 数组或分号分隔字符串。"""
    if not authors_raw:
        return ""
    s = authors_raw.strip()
    if s.startswith("["):
        try:
            data = json.loads(s)
            if isinstance(data, list) and data:
                names: list[str] = []
                for it in data[:5]:
                    if isinstance(it, dict) and it.get("name"):
                        names.append(str(it["name"]).strip())
                    elif isinstance(it, str) and it.strip():
                        names.append(it.strip())
                if not names:
                    return ""
                return f"{names[0]} et al." if len(data) > 1 else names[0]
        except Exception:
            pass
    if ";" in s:
        a0 = s.split(";")[0].strip()
        return f"{a0} et al." if s.count(";") >= 1 else a0
    return s[:300]


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
    meta = export_meta_separator_block(article)
    meta = strip_markdown(meta)
    return f"{td}\n\n{meta}" + body


def strip_markdown(text: str) -> str:
    """去除 Markdown 格式符号，返回干净的纯文本。"""
    # ATX 标题: ## Title → Title
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 粗体: **text** → text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # 斜体: *text* → text (单星号，排除列表项)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    # 列表项前的 * 号转为 • （保留缩进）
    text = re.sub(r"^(\s*)\*\s+", r"\1• ", text, flags=re.MULTILINE)
    # 水平线 --- → 空行
    text = re.sub(r"^-{3,}\s*$", "", text, flags=re.MULTILINE)
    # 图片 ![alt](url) → [图片: alt]
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[图片: \1]", text)
    # 链接 [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 行内代码 `code` → code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 清理连续空行（3+ → 2）
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


def _extract_text(node) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_extract_text(c) for c in node)
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


def _extract_inline(nodes) -> str:
    """段落 / 标题内联 → 文本，保留 hardBreak 为换行。"""
    out: list[str] = []
    for c in nodes or []:
        if not isinstance(c, dict):
            continue
        t = c.get("type", "")
        if t == "text":
            out.append(c.get("text", ""))
        elif t == "hardBreak":
            out.append("\n")
        elif t == "image":
            src = c.get("attrs", {}).get("src", "")
            alt = c.get("attrs", {}).get("alt", "")
            if src:
                out.append(f"![{alt}]({src})")
        else:
            out.append(_extract_inline(c.get("content") or []))
    return "".join(out)


def extract_markdown(node) -> str:
    """TipTap JSON → Markdown 文本，保留段落、标题、列表、引用、换行。

    用于导出（html/md/txt）路径，避免把整篇正文压成一段。"""
    if isinstance(node, list):
        return "\n\n".join(extract_markdown(c) for c in node if c).strip("\n")
    if not isinstance(node, dict):
        return ""
    ntype = node.get("type", "")
    children = node.get("content") or []

    if ntype == "doc":
        parts = [extract_markdown(c) for c in children]
        return "\n\n".join(p for p in parts if p).strip("\n")
    if ntype == "paragraph":
        return _extract_inline(children).rstrip()
    if ntype == "heading":
        level = (node.get("attrs") or {}).get("level", 2)
        try:
            level = int(level)
        except Exception:
            level = 2
        level = max(1, min(level, 6))
        return ("#" * level) + " " + _extract_inline(children).strip()
    if ntype == "bulletList":
        items: list[str] = []
        for it in children:
            if it.get("type") != "listItem":
                continue
            inner = "\n".join(extract_markdown(c) for c in it.get("content") or [] if c).strip()
            if inner:
                items.append("- " + inner.replace("\n", "\n  "))
        return "\n".join(items)
    if ntype == "orderedList":
        items = []
        for i, it in enumerate(children, 1):
            if it.get("type") != "listItem":
                continue
            inner = "\n".join(extract_markdown(c) for c in it.get("content") or [] if c).strip()
            if inner:
                items.append(f"{i}. " + inner.replace("\n", "\n   "))
        return "\n".join(items)
    if ntype == "blockquote":
        inner = "\n\n".join(extract_markdown(c) for c in children if c).strip()
        return "\n".join("> " + ln for ln in inner.splitlines()) if inner else ""
    if ntype == "horizontalRule":
        return "---"
    if ntype in ("codeBlock", "code_block"):
        raw = "".join(c.get("text", "") for c in children if isinstance(c, dict) and c.get("type") == "text")
        return f"```\n{raw}\n```"
    if ntype == "image":
        attrs = node.get("attrs") or {}
        src = attrs.get("src", "")
        alt = attrs.get("alt", "")
        return f"![{alt}]({src})" if src else ""
    if ntype == "text":
        return node.get("text", "")
    if ntype == "hardBreak":
        return ""
    return "\n\n".join(extract_markdown(c) for c in children if c).strip("\n")


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
                text = extract_markdown(doc)
            except Exception:
                pass
        parts.append((sec.title or sec.section_type, text, sec.section_type))
    if not parts:
        parts = [(s.title or s.section_type, "", s.section_type) for s in sections]
    return article, parts


async def load_article_sections_json(
    article_id: int, db: AsyncSession
) -> tuple[Article, list[tuple[str, dict | None, str]]]:
    """加载文章及章节原始 TipTap JSON，返回 (article, [(title, content_json_dict, section_type), ...])"""
    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise ValueError("Article not found")
    sec_result = await db.execute(
        select(ArticleSection).where(ArticleSection.article_id == article_id).order_by(ArticleSection.order_num)
    )
    sections = sec_result.scalars().all()
    parts: list[tuple[str, dict | None, str]] = []
    platform = article.platform or "wechat"
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
        doc = None
        if c and c.content_json:
            try:
                doc = json.loads(c.content_json)
            except Exception:
                pass
        parts.append((sec.title or sec.section_type, doc, sec.section_type))
    return article, parts


async def load_bound_references(article_id: int, db: AsyncSession) -> list[str]:
    """加载文章绑定的参考文献，返回格式化后的引用列表"""
    from app.models.literature import LiteraturePaper
    bind_result = await db.execute(
        select(ArticleLiteratureBinding)
        .where(ArticleLiteratureBinding.article_id == article_id)
        .order_by(ArticleLiteratureBinding.priority.asc(), ArticleLiteratureBinding.id.asc())
    )
    bindings = bind_result.scalars().all()
    if not bindings:
        return []
    paper_ids = [b.paper_id for b in bindings]
    paper_result = await db.execute(select(LiteraturePaper).where(LiteraturePaper.id.in_(paper_ids)))
    papers = {p.id: p for p in paper_result.scalars().all()}
    refs = []
    for i, b in enumerate(bindings, 1):
        p = papers.get(b.paper_id)
        if not p:
            continue
        authors = _short_authors_for_export(p.authors)
        title = p.title or ""
        journal = p.journal or ""
        year = p.year or ""
        doi = p.doi or ""
        parts = [s for s in [authors, title, journal, str(year) if year else ""] if s]
        line = f"[{i}] {'. '.join(parts)}."
        if doi:
            line += f" https://doi.org/{doi}" if not doi.startswith("http") else f" {doi}"
        refs.append(line)
    return refs


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

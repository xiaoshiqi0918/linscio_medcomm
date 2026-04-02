"""
WeasyPrintExporter - 患者手册/科普海报/科普绘本 PDF
流程：Tiptap JSON → HTML 模板 → WeasyPrint → PDF
图像：medcomm-image 相对路径 → file:// 绝对路径
DPI：96 屏幕 / 300 印刷
图像缺失：虚线占位框 + "此处待配图"
附带：文章绑定文献的参考文献列表
"""
import io
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.services.export.base import BaseExporter
from app.services.export.utils import load_article_sections
from app.services.export import html_docx
from app.services.literature.citation_formatter import CitationFormatter


def resolve_image(relative_path: str | None) -> str:
    """medcomm-image 或相对路径 → file:// 绝对路径；缺失返回空触发占位"""
    if not relative_path:
        return ""
    path = relative_path
    if path.startswith("medcomm-image://"):
        path = path.replace("medcomm-image://", "")
    if ".." in path or path.startswith("/"):
        return ""
    full = Path(settings.app_data_root) / path
    if not full.exists():
        return ""
    return f"file://{full.resolve()}"


def placeholder_html() -> str:
    """图像缺失占位"""
    return '<div style="border:2px dashed #ccc;padding:2em;color:#999;text-align:center;">此处待配图</div>'


class WeasyPrintExporter(BaseExporter):
    """WeasyPrint PDF 导出"""

    async def _build_references(self) -> str:
        import json as _json
        from app.models.article import ArticleLiteratureBinding, ArticleExternalReference
        from app.models.literature import LiteraturePaper

        bind_result = await self._db.execute(
            select(ArticleLiteratureBinding.paper_id)
            .where(ArticleLiteratureBinding.article_id == self.article_id)
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
            paper_result = await self._db.execute(
                select(LiteraturePaper).where(LiteraturePaper.id.in_(paper_ids))
            )
            papers = {p.id: p for p in paper_result.scalars().all()}
            for i, pid in enumerate(paper_ids, 1):
                p = papers.get(pid)
                if not p:
                    continue
                lines.append(f"[{i}] {CitationFormatter(p).format('apa')}")

        ext_result = await self._db.execute(
            select(ArticleExternalReference)
            .where(ArticleExternalReference.article_id == self.article_id)
            .order_by(ArticleExternalReference.id.asc())
        )
        ext_refs = ext_result.scalars().all()
        offset = len(lines)
        for j, r in enumerate(ext_refs, 1):
            authors = ""
            try:
                arr = _json.loads(r.authors) if isinstance(r.authors, str) else (r.authors or [])
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

    async def export(self, fmt: str = "pdf", dpi: int = 96) -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        refs = await self._build_references()
        full_text = "\n\n".join(f"## {t}\n\n{b}" for t, b, _ in parts) + (refs or "")

        try:
            from weasyprint import HTML
            from weasyprint.text.fonts import FontConfiguration
        except ImportError as e:
            raise ValueError("WeasyPrint 未安装，无法导出 PDF") from e

        html_str = html_docx.to_html(article, full_text)
        font_config = FontConfiguration()
        html_doc = HTML(string=html_str, base_url=settings.app_data_root)
        buf = io.BytesIO()
        html_doc.write_pdf(buf, font_config=font_config)
        buf.seek(0)
        return buf.getvalue(), "application/pdf", f"{base_name}.pdf"

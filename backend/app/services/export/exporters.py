"""导出器实现 - 按形式路由"""
from app.services.export.base import BaseExporter
from app.services.export import html_docx, script
from app.services.export.utils import (
    load_article_sections,
    prepend_export_title_markdown,
    prepend_export_title_plain,
)


class HtmlDocxExporter(BaseExporter):
    """叙事类：HTML（微信）/ DOCX（期刊）/ Markdown（通用）"""

    async def export(self, fmt: str = "html") -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        body = "\n\n".join(f"## {t}\n\n{b}" for t, b, _ in parts)

        if fmt == "html":
            html = html_docx.to_html(article, body)
            return html.encode("utf-8"), "text/html; charset=utf-8", f"{base_name}.html"
        if fmt == "docx":
            try:
                buf, fn = html_docx.to_docx(article, [(p[0], p[1]) for p in parts])
                return buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", fn
            except ImportError:
                txt = prepend_export_title_plain(article, body)
                return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"
        if fmt == "md":
            md = prepend_export_title_markdown(article, body)
            return md.encode("utf-8"), "text/markdown; charset=utf-8", f"{base_name}.md"
        txt = prepend_export_title_plain(article, body)
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"


class ScriptExporter(BaseExporter):
    """脚本类：TXT 带时间戳/角色标注"""

    async def export(self, fmt: str = "txt") -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        txt = script.to_script_txt(parts, article=article)
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"


class StoryboardExporter(BaseExporter):
    """分镜类：DOCX 分镜表格 / TXT"""

    async def export(self, fmt: str = "docx") -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        txt = script.to_storyboard_txt(parts, article=article)
        if fmt == "docx":
            try:
                buf, fn = html_docx.to_docx(article, [(f"镜头{i}", b) for i, (_, b, _) in enumerate(parts, 1)])
                return buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", fn
            except ImportError:
                pass
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"


class ComicExporter(BaseExporter):
    """条漫：TXT 画面描述集合 / PDF 占位"""

    async def export(self, fmt: str = "txt") -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        txt = script.to_comic_txt(parts, article=article)
        if fmt == "pdf":
            from app.services.export.weasyprint_exporter import WeasyPrintExporter
            exp = WeasyPrintExporter(self.article_id, self.platform, self._db)
            return await exp.export(fmt="pdf", dpi=96)
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"


class CardExporter(BaseExporter):
    """知识卡片：TXT 每卡描述"""

    async def export(self, fmt: str = "txt") -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        title_display = (article.title or article.topic or "").strip()
        header = f"{title_display}\n\n" if title_display else ""
        lines = [f"卡片{i}\n{b}\n" for i, (_, b, _) in enumerate(parts, 1)]
        txt = header + "\n".join(lines)
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"


class LongImageExporter(BaseExporter):
    """竖版长图：HTML 预览 + TXT prompt 集合"""

    async def export(self, fmt: str = "txt") -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        title_display = (article.title or article.topic or "").strip()
        header = f"{title_display}\n\n" if title_display else ""
        labels = ["封面", "板块1", "板块2", "板块3", "页脚"]
        lines = []
        for i, (_, body, _) in enumerate(parts):
            label = labels[i] if i < len(labels) else f"板块{i+1}"
            lines.append(f"{label}\n{body}\n")
        txt = header + "\n".join(lines)
        if fmt == "html":
            full_text = "\n\n".join(f"## {t}\n\n{b}" for t, b, _ in parts)
            html = html_docx.to_html(article, full_text)
            return html.encode("utf-8"), "text/html; charset=utf-8", f"{base_name}.html"
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"


class TxtExporter(BaseExporter):
    """H5 大纲等：TXT"""

    async def export(self, fmt: str = "txt") -> tuple[bytes, str, str]:
        article, parts = await load_article_sections(self.article_id, self._db)
        base_name = (article.topic or "article").replace("/", "-")
        body = "\n".join(f"## {t or st}\n\n{b}\n" for t, b, st in parts)
        txt = prepend_export_title_plain(article, body)
        return txt.encode("utf-8"), "text/plain; charset=utf-8", f"{base_name}.txt"


EXPORTER_CLASSES = {
    "HtmlDocxExporter": HtmlDocxExporter,
    "ScriptExporter": ScriptExporter,
    "StoryboardExporter": StoryboardExporter,
    "ComicExporter": ComicExporter,
    "CardExporter": CardExporter,
    "LongImageExporter": LongImageExporter,
    "TxtExporter": TxtExporter,
    "PdfExporter": None,
}

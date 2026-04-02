"""按形式路由导出 - exporter_cls(article_id, platform).export()"""
from app.services.format_router import FORMAT_CONFIG
from app.services.export.exporters import EXPORTER_CLASSES
from app.services.export.weasyprint_exporter import WeasyPrintExporter


def _get_exporter_class(content_format: str):
    """根据 content_format 获取导出器类"""
    cfg = FORMAT_CONFIG.get(content_format, {})
    name = cfg.get("exporter", "HtmlDocxExporter")
    if name == "PdfExporter":
        return WeasyPrintExporter
    return EXPORTER_CLASSES.get(name) or EXPORTER_CLASSES["HtmlDocxExporter"]


async def export_article(
    article_id: int,
    fmt: str,
    platform: str = "wechat",
    db=None,
) -> tuple[bytes, str, str]:
    """
    按 content_format 路由到对应导出器
    返回 (content_bytes, media_type, filename)
    """
    from sqlalchemy import select
    from app.models.article import Article

    result = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = result.scalar_one_or_none()
    if not article:
        raise ValueError("Article not found")

    cf = article.content_format or "article"
    platform = platform or article.platform or "wechat"
    exporter_cls = _get_exporter_class(cf)
    exporter = exporter_cls(article_id, platform, db)

    if fmt == "pdf":
        pdf_exp = WeasyPrintExporter(article_id, platform, db)
        return await pdf_exp.export(fmt="pdf", dpi=96)

    return await exporter.export(fmt=fmt if fmt in ("html", "docx", "md") else "txt")

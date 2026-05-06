"""海报模式导出（HTML / PDF）。

5 个预设模板（参赛、临床、公众号、小红书、知乎）通过 Jinja2 渲染，
HTML 直接返回；PDF 通过 Playwright 的 Chromium 打印输出。
"""
from app.services.export.poster.renderer import (
    POSTER_TEMPLATES,
    list_templates,
    render_html,
    render_pdf,
    render_docx,
    PosterRenderError,
)

__all__ = [
    "POSTER_TEMPLATES",
    "list_templates",
    "render_html",
    "render_pdf",
    "render_docx",
    "PosterRenderError",
]

"""RFC 5987 Content-Disposition，避免中文文件名触发 ASGI latin-1 头编码错误"""
from __future__ import annotations

from urllib.parse import quote


def attachment_content_disposition(filename: str) -> str:
    """
    返回 latin-1 安全的 Content-Disposition，同时带 filename*=UTF-8'' 供现代浏览器显示中文名。
    """
    fn = (filename or "download").strip().replace("\r", "").replace("\n", "")
    fn = fn.replace("\\", "/").split("/")[-1] or "download"

    stem, ext_suffix = fn, ""
    if "." in fn:
        stem, ext = fn.rsplit(".", 1)
        ext_suffix = "." + ext[:32] if ext else ""

    ascii_stem = "".join(
        c if ord(c) < 128 and c not in '"\\' else "_"
        for c in stem
    ).strip("._")
    if not ascii_stem:
        ascii_stem = "article"
    ascii_part = ascii_stem + ext_suffix

    star = quote(fn, safe="")
    return f"attachment; filename=\"{ascii_part}\"; filename*=UTF-8''{star}"

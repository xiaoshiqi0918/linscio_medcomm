"""脚本类导出：TXT 带格式标注"""
from typing import Any


def _title_line(article: Any | None) -> str:
    if article is None:
        return ""
    t = (getattr(article, "title", None) or "").strip()
    if not t:
        t = (getattr(article, "topic", None) or "").strip()
    return f"{t}\n\n" if t else ""


def to_script_txt(parts: list[tuple[str, str, str]], article: Any = None) -> str:
    lines = [_title_line(article)]
    for title, body, st in parts:
        prefix = "【" + (title or st) + "】" if title or st else ""
        lines.append(f"{prefix}\n{body}\n" if prefix else f"{body}\n")
    return "\n".join(lines).lstrip("\n")


def to_storyboard_txt(parts: list[tuple[str, str, str]], article: Any = None) -> str:
    lines = [_title_line(article)]
    for i, (_, body, _) in enumerate(parts, 1):
        lines.append(f"镜头{i}\n{body}\n")
    return "\n".join(lines).lstrip("\n")


def to_comic_txt(parts: list[tuple[str, str, str]], article: Any = None) -> str:
    lines = [_title_line(article)]
    for i, (_, body, _) in enumerate(parts, 1):
        lines.append(f"分格{i}\n{body}\n")
    return "\n".join(lines).lstrip("\n")

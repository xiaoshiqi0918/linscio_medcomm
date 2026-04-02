"""脚本类导出：TXT 带格式标注"""


def to_script_txt(parts: list[tuple[str, str, str]]) -> str:
    lines = []
    for title, body, st in parts:
        prefix = "【" + (title or st) + "】" if title or st else ""
        lines.append(f"{prefix}\n{body}\n" if prefix else f"{body}\n")
    return "\n".join(lines)


def to_storyboard_txt(parts: list[tuple[str, str, str]]) -> str:
    lines = []
    for i, (_, body, _) in enumerate(parts, 1):
        lines.append(f"镜头{i}\n{body}\n")
    return "\n".join(lines)


def to_comic_txt(parts: list[tuple[str, str, str]]) -> str:
    lines = []
    for i, (_, body, _) in enumerate(parts, 1):
        lines.append(f"分格{i}\n{body}\n")
    return "\n".join(lines)

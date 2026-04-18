"""
Convert LLM-generated Markdown text to TipTap/ProseMirror JSON document.

Handles: headings (##/###), paragraphs (\n\n), bold (**), and inline marks.
Does NOT attempt full Markdown parsing — only the subset LLMs actually produce.
"""
from __future__ import annotations

import re
from typing import Any


def _parse_inline(text: str) -> list[dict[str, Any]]:
    """Parse inline bold (**text**) into TipTap text nodes with marks."""
    nodes: list[dict[str, Any]] = []
    pos = 0
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        if m.start() > pos:
            nodes.append({"type": "text", "text": text[pos:m.start()]})
        nodes.append({
            "type": "text",
            "text": m.group(1),
            "marks": [{"type": "bold"}],
        })
        pos = m.end()
    if pos < len(text):
        nodes.append({"type": "text", "text": text[pos:]})
    return nodes or [{"type": "text", "text": text}]


def markdown_to_tiptap(md: str) -> dict[str, Any]:
    """Convert Markdown string to a TipTap doc JSON.

    Returns ``{"type": "doc", "content": [...]}``.
    """
    lines = md.split("\n")
    blocks: list[dict[str, Any]] = []
    buf: list[str] = []

    def flush_buf():
        text = "\n".join(buf).strip()
        buf.clear()
        if not text:
            return
        blocks.append({"type": "paragraph", "content": _parse_inline(text)})

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            flush_buf()
            level = len(heading_match.group(1))
            blocks.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": _parse_inline(heading_match.group(2).strip()),
            })
            continue

        if line.strip() == "":
            flush_buf()
            continue

        buf.append(line)

    flush_buf()

    if not blocks:
        blocks.append({"type": "paragraph", "content": [{"type": "text", "text": md or ""}]})

    return {"type": "doc", "content": blocks}

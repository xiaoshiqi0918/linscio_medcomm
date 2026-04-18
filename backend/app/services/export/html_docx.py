"""叙事类导出：HTML / DOCX（从 TipTap JSON 保留段落、换行、列表、加粗等）"""
import html as html_lib
import io
import re
from typing import Any


def _skip_article_intro(content_format: str | None, section_type: str | None) -> bool:
    return (content_format or "article") == "article" and (section_type or "") == "intro"


def _strip_reference_nodes(nodes: list[dict]) -> list[dict]:
    """Remove LLM-generated '参考文献' heading and everything after it from TipTap nodes."""
    cut_idx = None
    for i, node in enumerate(nodes):
        text = "".join(
            c.get("text", "") for c in node.get("content", []) if isinstance(c, dict)
        )
        if node.get("type") == "heading" and re.search(r"参考文献|references", text, re.IGNORECASE):
            cut_idx = i
            break
        if node.get("type") == "paragraph" and re.match(r"^\s*参考文献\s*$", text):
            cut_idx = i
            break
    if cut_idx is not None:
        nodes = nodes[:cut_idx]
        while nodes and nodes[-1].get("type") == "paragraph" and not nodes[-1].get("content"):
            nodes.pop()
    return nodes


def _add_inline_content(paragraph, nodes: list[dict] | None) -> None:
    """段落内：text（含 marks）、hardBreak。"""
    if not nodes:
        return
    from docx.enum.text import WD_BREAK

    for node in nodes:
        t = node.get("type", "")
        if t == "text":
            text = node.get("text", "")
            if not text:
                continue
            run = paragraph.add_run(text)
            for mark in node.get("marks") or []:
                mt = mark.get("type", "")
                if mt == "bold":
                    run.bold = True
                elif mt == "italic":
                    run.italic = True
                elif mt == "underline":
                    run.underline = True
                elif mt == "strike":
                    run.font.strike = True
                elif mt == "citationRef":
                    run.font.superscript = True
        elif t == "hardBreak":
            br = paragraph.add_run()
            br.add_break(WD_BREAK.LINE)


def _render_list_items_docx(doc, node: dict, bullet: bool = True) -> None:
    """bulletList / orderedList：支持 listItem 内多段落与嵌套列表。"""
    items = node.get("content") or []
    for item in items:
        if item.get("type") != "listItem":
            continue
        for child in item.get("content") or []:
            ctype = child.get("type", "")
            if ctype == "paragraph":
                style = "List Bullet" if bullet else "List Number"
                try:
                    p = doc.add_paragraph(style=style)
                except Exception:
                    p = doc.add_paragraph()
                _add_inline_content(p, child.get("content") or [])
            elif ctype in ("bulletList", "orderedList"):
                _tiptap_nodes_to_docx(doc, [child])


def _tiptap_nodes_to_docx(doc, nodes: list[dict]) -> None:
    """将 TipTap block 节点列表写入 python-docx Document。"""
    for node in nodes:
        ntype = node.get("type", "")

        if ntype == "paragraph":
            p = doc.add_paragraph()
            _add_inline_content(p, node.get("content") or [])

        elif ntype == "heading":
            tl = (node.get("attrs") or {}).get("level", 2)
            try:
                tl = int(tl)
            except (TypeError, ValueError):
                tl = 2
            lvl = min(max(tl, 1), 9)
            p = doc.add_heading("", level=lvl)
            _add_inline_content(p, node.get("content") or [])

        elif ntype == "bulletList":
            _render_list_items_docx(doc, node, bullet=True)

        elif ntype == "orderedList":
            _render_list_items_docx(doc, node, bullet=False)

        elif ntype == "blockquote":
            for child in node.get("content") or []:
                if child.get("type") == "paragraph":
                    p = doc.add_paragraph()
                    try:
                        p.style = "Quote"
                    except Exception:
                        pass
                    _add_inline_content(p, child.get("content") or [])

        elif ntype in ("codeBlock", "code_block"):
            raw = []
            for c in node.get("content") or []:
                if c.get("type") == "text":
                    raw.append(c.get("text", ""))
            p = doc.add_paragraph("".join(raw))
            try:
                p.style = "No Spacing"
            except Exception:
                pass
            for r in p.runs:
                r.font.name = "Consolas"

        elif ntype == "horizontalRule":
            doc.add_paragraph("—" * 24)

        elif ntype == "doc":
            _tiptap_nodes_to_docx(doc, node.get("content") or [])

        elif ntype == "image":
            alt = (node.get("attrs") or {}).get("alt") or "图片"
            doc.add_paragraph(f"[图片：{alt}]")

        else:
            inner = node.get("content")
            if isinstance(inner, list) and inner:
                _tiptap_nodes_to_docx(doc, inner)


def to_docx_from_json(
    article: Any,
    section_parts: list[tuple[str, dict | None, str]],
    references: list[str] | None = None,
) -> tuple[bytes, str]:
    """从 TipTap JSON 构建 DOCX。"""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    cf = getattr(article, "content_format", None)
    hide_section_headings = (cf or "article") == "article"

    title_text = article.title or article.topic or "未命名"
    doc.add_heading(title_text, level=0)

    for sec_title, content_json, section_type in section_parts:
        if _skip_article_intro(cf, section_type):
            continue
        if not content_json:
            continue
        nodes = content_json.get("content") or [] if isinstance(content_json, dict) else []
        if not nodes:
            continue
        nodes = _strip_reference_nodes(nodes)
        if not nodes:
            continue
        if not hide_section_headings:
            doc.add_heading(sec_title, level=1)
        _tiptap_nodes_to_docx(doc, nodes)

    if references:
        doc.add_heading("参考文献", level=1)
        for ref_line in references:
            p = doc.add_paragraph(ref_line)
            for run in p.runs:
                run.font.size = Pt(9)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    fn = f"{(article.topic or 'article').replace('/', '-')}.docx"
    return buf.getvalue(), fn


# ——— HTML（结构化，便于微信预览等）———


def _inline_to_html(nodes: list[dict] | None) -> str:
    if not nodes:
        return ""
    parts: list[str] = []
    for node in nodes:
        t = node.get("type", "")
        if t == "text":
            s = html_lib.escape(node.get("text", ""))
            for mark in node.get("marks") or []:
                mt = mark.get("type", "")
                if mt == "bold":
                    s = f"<strong>{s}</strong>"
                elif mt == "italic":
                    s = f"<em>{s}</em>"
                elif mt == "underline":
                    s = f"<u>{s}</u>"
                elif mt == "strike":
                    s = f"<s>{s}</s>"
                elif mt == "citationRef":
                    s = f"<sup>{s}</sup>"
            parts.append(s)
        elif t == "hardBreak":
            parts.append("<br>")
    return "".join(parts)


def _blocks_to_html(nodes: list[dict]) -> str:
    out: list[str] = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype == "paragraph":
            inner = _inline_to_html(node.get("content") or [])
            out.append(f"<p>{inner}</p>")
        elif ntype == "heading":
            tl = (node.get("attrs") or {}).get("level", 2)
            try:
                tl = int(tl)
            except (TypeError, ValueError):
                tl = 2
            tag = f"h{min(max(tl, 1), 6)}"
            inner = _inline_to_html(node.get("content") or [])
            out.append(f"<{tag}>{inner}</{tag}>")
        elif ntype == "bulletList":
            out.append("<ul>")
            for item in node.get("content") or []:
                if item.get("type") != "listItem":
                    continue
                pieces: list[str] = []
                for ch in item.get("content") or []:
                    if ch.get("type") == "paragraph":
                        pieces.append(_inline_to_html(ch.get("content") or []))
                    elif ch.get("type") in ("bulletList", "orderedList"):
                        pieces.append(_blocks_to_html([ch]))
                out.append(f"<li>{''.join(pieces)}</li>")
            out.append("</ul>")
        elif ntype == "orderedList":
            out.append("<ol>")
            for item in node.get("content") or []:
                if item.get("type") != "listItem":
                    continue
                pieces = []
                for ch in item.get("content") or []:
                    if ch.get("type") == "paragraph":
                        pieces.append(_inline_to_html(ch.get("content") or []))
                    elif ch.get("type") in ("bulletList", "orderedList"):
                        pieces.append(_blocks_to_html([ch]))
                out.append(f"<li>{''.join(pieces)}</li>")
            out.append("</ol>")
        elif ntype == "blockquote":
            inner_parts = []
            for ch in node.get("content") or []:
                if ch.get("type") == "paragraph":
                    inner_parts.append(_inline_to_html(ch.get("content") or []))
            out.append(f"<blockquote><p>{'</p><p>'.join(inner_parts)}</p></blockquote>")
        elif ntype == "horizontalRule":
            out.append("<hr>")
        elif ntype in ("codeBlock", "code_block"):
            raw = []
            for c in node.get("content") or []:
                if c.get("type") == "text":
                    raw.append(c.get("text", ""))
            out.append(f"<pre><code>{html_lib.escape(''.join(raw))}</code></pre>")
        elif ntype == "doc":
            out.append(_blocks_to_html(node.get("content") or []))
        elif ntype == "image":
            alt = html_lib.escape((node.get("attrs") or {}).get("alt") or "")
            src = html_lib.escape((node.get("attrs") or {}).get("src") or "")
            if src:
                out.append(f'<p><img src="{src}" alt="{alt}" /></p>')
            else:
                out.append(f"<p>[图片：{alt}]</p>")
        else:
            inner = node.get("content")
            if isinstance(inner, list):
                out.append(_blocks_to_html(inner))
    return "".join(out)


def to_html_from_json(article: Any, section_parts: list[tuple[str, dict | None, str]], references: list[str] | None = None) -> str:
    """从 TipTap 章节构建完整 HTML 页面。"""
    cf = getattr(article, "content_format", None)
    hide_section_headings = (cf or "article") == "article"
    title = html_lib.escape(article.title or article.topic or "未命名")
    chunks: list[str] = []
    for sec_title, content_json, section_type in section_parts:
        if _skip_article_intro(cf, section_type):
            continue
        if not content_json:
            continue
        nodes = content_json.get("content") or [] if isinstance(content_json, dict) else []
        if not nodes:
            continue
        nodes = _strip_reference_nodes(nodes)
        if not nodes:
            continue
        if not hide_section_headings:
            st = html_lib.escape(sec_title)
            chunks.append(f'<h2 class="section-title">{st}</h2>')
        chunks.append(f'<div class="section-body">{_blocks_to_html(nodes)}</div>')
    ref_block = ""
    if references:
        ref_block = '<h2>参考文献</h2><ol class="references">' + "".join(
            f"<li>{html_lib.escape(r)}</li>" for r in references
        ) + "</ol>"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 2em; line-height: 1.75; color: #1f2937; max-width: 720px; }}
h1 {{ font-size: 1.5em; margin-bottom: 1em; }}
h2 {{ font-size: 1.15em; margin-top: 1.5em; margin-bottom: 0.6em; color: #111827; }}
h3, h4, h5, h6 {{ margin-top: 1em; margin-bottom: 0.5em; }}
.section-body p {{ margin: 0.6em 0; }}
.section-body ul, .section-body ol {{ margin: 0.6em 0; padding-left: 1.4em; }}
.section-body li {{ margin: 0.25em 0; }}
blockquote {{ margin: 0.8em 0; padding-left: 1em; border-left: 3px solid #e5e7eb; color: #4b5563; }}
pre {{ background: #f3f4f6; padding: 0.75em; border-radius: 6px; overflow-x: auto; }}
.references li {{ margin: 0.4em 0; font-size: 0.92em; }}
</style>
</head>
<body>
<h1>{title}</h1>
{"".join(chunks)}
{ref_block}
</body>
</html>"""


def to_html(article, body_text: str) -> str:
    """兼容：纯文本 body（已含 ## 标题）转 HTML。"""
    esc = html_lib.escape(body_text)
    body_html = re.sub(r"\r\n|\r|\n", "<br>\n", esc)
    title = html_lib.escape(article.title or article.topic or "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 2em; line-height: 1.6; }}
h1 {{ font-size: 1.5em; }}
.content {{ margin-top: 1em; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="content">{body_html}</div>
</body>
</html>"""


def to_docx(article, parts: list[tuple[str, str]]) -> tuple[bytes, str]:
    """纯文本兜底方案"""
    from docx import Document

    doc = Document()
    doc.add_heading(article.title or article.topic or "未命名", 0)
    for title, body in parts:
        doc.add_heading(title, level=1)
        for para in body.split("\n\n"):
            if para.strip():
                doc.add_paragraph(para.strip())
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue(), f"{(article.topic or 'article').replace('/', '-')}.docx"

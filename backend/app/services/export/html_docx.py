"""叙事类导出：HTML / DOCX（从 TipTap JSON 保留段落、换行、列表、加粗等）"""
import base64
import html as html_lib
import io
import os
import re
from typing import Any


# ════════════════════════════════════════════════════════════════
#  图片资源解析（导出用）
# ════════════════════════════════════════════════════════════════

def resolve_image_abs_path(image_path: str | None) -> str | None:
    """将 slot.image_path 解析为本机绝对路径。
    支持：
      - 已是绝对路径：直接返回
      - medcomm-image://images/2026/05/xxx.png：剥离协议头后拼 app_data_root
      - 相对路径 images/2026/05/xxx.png：拼 app_data_root
    """
    if not image_path:
        return None
    p = image_path
    if p.startswith("medcomm-image://"):
        p = p[len("medcomm-image://"):]
    if os.path.isabs(p) and os.path.isfile(p):
        return p
    try:
        from app.core.config import settings
        candidate = os.path.join(settings.app_data_root, p)
        if os.path.isfile(candidate):
            return candidate
    except Exception:
        pass
    return None


_MIME_BY_EXT = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
}


def image_to_data_uri(image_path: str | None) -> str | None:
    """读取图片字节并转 base64 data: URI（用于 HTML/Markdown 内嵌图）。"""
    abs_p = resolve_image_abs_path(image_path)
    if not abs_p:
        return None
    ext = os.path.splitext(abs_p)[1].lower()
    mime = _MIME_BY_EXT.get(ext, "image/png")
    try:
        with open(abs_p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


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


def _embed_image_or_placeholder(doc, src: str, alt: str) -> None:
    """Try to embed an image from local path; fall back to text placeholder."""
    import os
    from docx.shared import Inches

    if src and os.path.isfile(src):
        try:
            p = doc.add_paragraph()
            p.alignment = 1  # center
            run = p.add_run()
            run.add_picture(src, width=Inches(5.0))
            if alt:
                cap = doc.add_paragraph(alt)
                cap.alignment = 1
                for r in cap.runs:
                    r.font.size = __import__('docx.shared', fromlist=['Pt']).Pt(9)
            return
        except Exception:
            pass
    doc.add_paragraph(f"[图片：{alt}]")


def embed_image_slot_in_docx(
    doc,
    image_path: str | None,
    intent_text: str,
    image_status: str,
    layout_preference: str | None = None,
) -> None:
    """Embed a contest image slot into a DOCX document."""
    import os
    from docx.shared import Inches, Pt

    if image_path and os.path.isfile(image_path):
        try:
            p = doc.add_paragraph()
            p.alignment = 1
            run = p.add_run()
            width = Inches(5.0)
            if layout_preference == "crop_fill":
                width = Inches(6.0)
            elif layout_preference == "letterbox":
                width = Inches(4.5)
            run.add_picture(image_path, width=width)
            if intent_text:
                cap = doc.add_paragraph(intent_text)
                cap.alignment = 1
                for r in cap.runs:
                    r.font.size = Pt(9)
            return
        except Exception:
            pass

    status_label = "已上传" if image_status == "uploaded" else "待配图"
    p = doc.add_paragraph(f"[配图·{status_label}] {intent_text}")
    for r in p.runs:
        r.font.color.rgb = __import__('docx.shared', fromlist=['RGBColor']).RGBColor(0x99, 0x99, 0x99)


_FONT_PT_RE = re.compile(r"^\s*([\d.]+)\s*(px|pt|em|rem)?\s*$", re.I)


def _font_size_to_pt(value: str | None):
    """把 CSS / TipTap fontSize（'14px' / '12pt' / '1.1em'）转换为 docx Pt 数值。
    返回 None 表示无法解析或留空。"""
    if not value:
        return None
    m = _FONT_PT_RE.match(str(value))
    if not m:
        return None
    try:
        n = float(m.group(1))
    except Exception:
        return None
    unit = (m.group(2) or "px").lower()
    # 16px ≈ 12pt（CSS 默认 1em=16px=12pt）
    if unit == "px":
        return n * 0.75
    if unit == "pt":
        return n
    if unit in ("em", "rem"):
        return n * 12.0
    return None


def _font_family_primary(value: str | None) -> str | None:
    """从 CSS font-family 列表里挑首选项，剥引号。"""
    if not value:
        return None
    first = value.split(",")[0].strip()
    if (first.startswith('"') and first.endswith('"')) or (first.startswith("'") and first.endswith("'")):
        first = first[1:-1].strip()
    return first or None


def _apply_run_marks(run, marks: list[dict] | None) -> None:
    """把 TipTap mark 列表里的样式应用到 docx run 上。"""
    if not marks:
        return
    from docx.shared import Pt
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    for mark in marks:
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
        elif mt == "textStyle":
            attrs = mark.get("attrs") or {}
            font_name = _font_family_primary(attrs.get("fontFamily"))
            if font_name:
                run.font.name = font_name
                rpr = run._element.get_or_add_rPr()
                rfonts = rpr.find(qn("w:rFonts"))
                if rfonts is None:
                    rfonts = OxmlElement("w:rFonts")
                    rpr.insert(0, rfonts)
                rfonts.set(qn("w:eastAsia"), font_name)
            pt = _font_size_to_pt(attrs.get("fontSize"))
            if pt:
                run.font.size = Pt(pt)


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
            _apply_run_marks(run, node.get("marks") or [])
        elif t == "hardBreak":
            br = paragraph.add_run()
            br.add_break(WD_BREAK.LINE)


_TEXT_ALIGN_MAP_LAZY = None


def _text_align_value(align: str | None):
    """TipTap textAlign('left'/'center'/'right'/'justify') → python-docx WD_PARAGRAPH_ALIGNMENT。"""
    global _TEXT_ALIGN_MAP_LAZY
    if not align:
        return None
    if _TEXT_ALIGN_MAP_LAZY is None:
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT as _WPA
        _TEXT_ALIGN_MAP_LAZY = {
            "left": _WPA.LEFT,
            "center": _WPA.CENTER,
            "right": _WPA.RIGHT,
            "justify": _WPA.JUSTIFY,
        }
    return _TEXT_ALIGN_MAP_LAZY.get(align.lower())


def _apply_paragraph_attrs(paragraph, attrs: dict | None, *, default_indent: bool = False) -> None:
    """把 TipTap paragraph/heading attrs（indent / textAlign）映射到 docx 段落格式。

    indent 三态：
      - True  → 强制首行缩进 ≈ 2 个汉字（24pt）
      - False → 强制不缩进
      - None  → 沿用 default_indent（叙事类正文默认缩进），但
                center / right 对齐段落自动抑制默认缩进，避免视觉怪异
    """
    from docx.shared import Pt
    if not attrs:
        attrs = {}

    align_raw = attrs.get("textAlign") or ""
    align_enum = _text_align_value(align_raw)
    if align_enum is not None:
        paragraph.alignment = align_enum

    indent = attrs.get("indent")
    if indent is True:
        paragraph.paragraph_format.first_line_indent = Pt(24)
    elif indent is False:
        paragraph.paragraph_format.first_line_indent = Pt(0)
    elif default_indent and align_raw.lower() not in ("center", "right"):
        paragraph.paragraph_format.first_line_indent = Pt(24)


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
                _apply_paragraph_attrs(p, child.get("attrs") or {}, default_indent=False)
                _add_inline_content(p, child.get("content") or [])
            elif ctype in ("bulletList", "orderedList"):
                _tiptap_nodes_to_docx(doc, [child])


def _tiptap_nodes_to_docx(doc, nodes: list[dict], *, default_indent: bool = False) -> None:
    """将 TipTap block 节点列表写入 python-docx Document。

    default_indent: 当段落本身没有显式 attrs.indent 时，是否给正文段落首行缩进。
                    叙事类（article / contest_article 等）建议 True，
                    脚本 / 列表卡片类建议 False。
    """
    for node in nodes:
        ntype = node.get("type", "")

        if ntype == "paragraph":
            p = doc.add_paragraph()
            _apply_paragraph_attrs(
                p, node.get("attrs") or {}, default_indent=default_indent
            )
            _add_inline_content(p, node.get("content") or [])

        elif ntype == "heading":
            tl = (node.get("attrs") or {}).get("level", 2)
            try:
                tl = int(tl)
            except (TypeError, ValueError):
                tl = 2
            lvl = min(max(tl, 1), 9)
            p = doc.add_heading("", level=lvl)
            # 标题默认不缩进，仅在 attrs 显式 indent=True 时缩进
            _apply_paragraph_attrs(p, node.get("attrs") or {}, default_indent=False)
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
                    _apply_paragraph_attrs(p, child.get("attrs") or {}, default_indent=False)
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
            _tiptap_nodes_to_docx(doc, node.get("content") or [], default_indent=default_indent)

        elif ntype == "image":
            alt = (node.get("attrs") or {}).get("alt") or "图片"
            src = (node.get("attrs") or {}).get("src") or ""
            _embed_image_or_placeholder(doc, src, alt)

        else:
            inner = node.get("content")
            if isinstance(inner, list) and inner:
                _tiptap_nodes_to_docx(doc, inner, default_indent=default_indent)


def to_docx_from_json(
    article: Any,
    section_parts: list[tuple[str, dict | None, str]],
    references: list[str] | None = None,
    *,
    image_slots_by_section_id: dict[int, list] | None = None,
    section_id_to_type: dict[int, str] | None = None,
    font_config: dict | None = None,
    layout_preference: str | None = None,
    trailing_paragraphs: list[str] | None = None,
    hide_section_headings: bool | None = None,
    base_name: str | None = None,
) -> tuple[bytes, str]:
    """从 TipTap JSON 构建 DOCX，保留段落/标题/列表/加粗等格式。

    可选参数：
    - image_slots_by_section_id: {section_id: [slot, ...]}，按章节嵌入配图（slot 需带 image_path / intent_text / image_status）
    - section_id_to_type: {section_id: section_type}，配合 image_slots 找到对应章节
    - font_config: {"font_name": str, "pt_size": float}，赛制字体要求
    - layout_preference: 配图裁切偏好（影响图片宽度）
    - trailing_paragraphs: 文末追加段落（如 AI 创作声明、免责声明），按 \\n\\n 分段
    - hide_section_headings: 显式控制是否隐藏章节标题（默认按 content_format == 'article' 判定）
    - base_name: 文件名前缀（不含扩展名）
    """
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    cf = getattr(article, "content_format", None)
    if hide_section_headings is None:
        hide_section_headings = (cf or "article") == "article"

    # 叙事类（article / contest_article / story / debunk / qa_article / research_read）
    # 没有显式 indent attr 时，正文段落默认首行缩进 2 字。
    narrative_default_indent = (cf or "article") in (
        "article", "contest_article", "story", "debunk", "qa_article",
        "research_read", "patient_handbook", "quiz_article",
    )

    title_text = article.title or article.topic or "未命名"
    doc.add_heading(title_text, level=0)

    type_to_slots: dict[str, list] = {}
    sid_to_type: dict[int, str] = section_id_to_type or {}
    if image_slots_by_section_id:
        for sid, slots in image_slots_by_section_id.items():
            stype = sid_to_type.get(sid, "")
            if stype:
                type_to_slots.setdefault(stype, []).extend(slots or [])

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
        _tiptap_nodes_to_docx(doc, nodes, default_indent=narrative_default_indent)

        for sl in type_to_slots.get(section_type or "", []):
            embed_image_slot_in_docx(
                doc,
                image_path=resolve_image_abs_path(getattr(sl, "image_path", None)),
                intent_text=getattr(sl, "intent_text", "") or "",
                image_status=getattr(sl, "image_status", "") or "",
                layout_preference=layout_preference,
            )

    if trailing_paragraphs:
        for block in trailing_paragraphs:
            if not block:
                continue
            for para in str(block).split("\n\n"):
                stripped = para.strip()
                if not stripped:
                    continue
                if stripped == "---":
                    continue
                doc.add_paragraph(stripped)

    if references:
        doc.add_heading("参考文献", level=1)
        for ref_line in references:
            p = doc.add_paragraph(ref_line)
            for run in p.runs:
                run.font.size = Pt(9)

    if font_config:
        _apply_font_config(doc, font_config)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    name = base_name or (article.topic or "article").replace("/", "-")
    fn = f"{name}.docx"
    return buf.getvalue(), fn


# ——— HTML（结构化，便于微信预览等）———


def _block_style_attr(attrs: dict | None) -> str:
    """根据 paragraph/heading attrs 生成行内 style（text-indent / text-align）。"""
    if not attrs:
        return ""
    parts: list[str] = []
    indent = attrs.get("indent")
    if indent is True:
        parts.append("text-indent:2em")
    elif indent is False:
        parts.append("text-indent:0")
    align = attrs.get("textAlign")
    if isinstance(align, str) and align in ("left", "center", "right", "justify"):
        parts.append(f"text-align:{align}")
    if not parts:
        return ""
    return f' style="{";".join(parts)}"'


def _textstyle_style_attr(attrs: dict | None) -> str:
    """根据 textStyle mark attrs 生成行内 style（font-family / font-size）。"""
    if not attrs:
        return ""
    parts: list[str] = []
    ff = attrs.get("fontFamily")
    if isinstance(ff, str) and ff.strip():
        parts.append(f"font-family:{ff.strip()}")
    fs = attrs.get("fontSize")
    if isinstance(fs, str) and fs.strip():
        parts.append(f"font-size:{fs.strip()}")
    if not parts:
        return ""
    return f' style="{";".join(parts)}"'


def _inline_to_html(nodes: list[dict] | None) -> str:
    if not nodes:
        return ""
    parts: list[str] = []
    for node in nodes:
        t = node.get("type", "")
        if t == "text":
            s = html_lib.escape(node.get("text", ""))
            ts_style = ""
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
                elif mt == "textStyle":
                    ts_style = _textstyle_style_attr(mark.get("attrs") or {})
            if ts_style:
                s = f"<span{ts_style}>{s}</span>"
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
            style_attr = _block_style_attr(node.get("attrs") or {})
            out.append(f"<p{style_attr}>{inner}</p>")
        elif ntype == "heading":
            tl = (node.get("attrs") or {}).get("level", 2)
            try:
                tl = int(tl)
            except (TypeError, ValueError):
                tl = 2
            tag = f"h{min(max(tl, 1), 6)}"
            inner = _inline_to_html(node.get("content") or [])
            style_attr = _block_style_attr(node.get("attrs") or {})
            out.append(f"<{tag}{style_attr}>{inner}</{tag}>")
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
    narrative_default_indent = (cf or "article") in (
        "article", "contest_article", "story", "debunk", "qa_article",
        "research_read", "patient_handbook", "quiz_article",
    )
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
    body_indent_css = (
        ".section-body p { text-indent: 2em; }\n"
        ".section-body p:first-child,\n"
        ".section-body p[style*=\"text-indent:0\"],\n"
        ".section-body p[style*=\"text-align:center\"],\n"
        ".section-body p:has(strong:only-child) { text-indent: 0; }"
    ) if narrative_default_indent else ".section-body p { text-indent: 0; }"
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
{body_indent_css}
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


def _md_body_to_html(md_body: str) -> str:
    """轻量 Markdown→HTML：保留 ![alt](data:...) 图片、## 标题、段落、加粗/斜体。

    专为导出场景设计，不依赖外部库；其它 Markdown 元素均按普通文本处理。
    """
    out_lines: list[str] = []
    paragraph_buf: list[str] = []

    def _flush_paragraph():
        if not paragraph_buf:
            return
        text = "\n".join(paragraph_buf).strip()
        paragraph_buf.clear()
        if not text:
            return
        # 段落内允许：图片 / 粗体 / 斜体 / 链接；其它字符做 HTML 转义
        rendered = _render_inline_markdown(text)
        out_lines.append(f'<p>{rendered}</p>')

    def _render_inline_markdown(s: str) -> str:
        # 1. 先把图片 ![alt](url) 占位成 sentinel
        images: list[tuple[str, str]] = []
        def _img_sub(m: re.Match) -> str:
            alt = m.group(1)
            url = m.group(2)
            images.append((alt, url))
            return f"\u0000IMG{len(images) - 1}\u0000"
        s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _img_sub, s)
        # 2. 链接 [text](url) → <a>
        links: list[tuple[str, str]] = []
        def _link_sub(m: re.Match) -> str:
            text = m.group(1)
            url = m.group(2)
            links.append((text, url))
            return f"\u0000LNK{len(links) - 1}\u0000"
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_sub, s)
        # 3. 转义剩余文本
        s = html_lib.escape(s)
        # 4. 加粗 / 斜体（在转义之后做，因为不会引入新尖括号）
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
        # 5. 还原链接 / 图片
        for i, (text, url) in enumerate(links):
            safe_text = html_lib.escape(text)
            safe_url = html_lib.escape(url, quote=True)
            s = s.replace(f"\u0000LNK{i}\u0000", f'<a href="{safe_url}">{safe_text}</a>')
        for i, (alt, url) in enumerate(images):
            safe_alt = html_lib.escape(alt, quote=True)
            # data URI 不再做 HTML escape — 对 base64 内容会破坏字符；仅 escape 双引号已够
            safe_url = url.replace('"', "&quot;")
            s = s.replace(
                f"\u0000IMG{i}\u0000",
                f'<figure class="figure"><img src="{safe_url}" alt="{safe_alt}" />'
                + (f'<figcaption>图：{html_lib.escape(alt)}</figcaption>' if alt else "")
                + '</figure>',
            )
        # 6. 行内换行
        s = s.replace("\n", "<br/>")
        return s

    for line in md_body.splitlines():
        stripped = line.strip()
        if not stripped:
            _flush_paragraph()
            continue
        if stripped.startswith("## "):
            _flush_paragraph()
            out_lines.append(f'<h2>{html_lib.escape(stripped[3:].strip())}</h2>')
            continue
        if stripped.startswith("# "):
            _flush_paragraph()
            out_lines.append(f'<h1>{html_lib.escape(stripped[2:].strip())}</h1>')
            continue
        # 图片单独成段（更美观）
        if re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped):
            _flush_paragraph()
            out_lines.append(_render_inline_markdown(stripped))
            continue
        paragraph_buf.append(line)
    _flush_paragraph()
    return "\n".join(out_lines)


def to_html_with_images(article, md_body: str) -> str:
    """带图片嵌入的 HTML 导出：md_body 中的 ![alt](data:...) 会被渲染为 <img>。"""
    title = html_lib.escape(article.title or article.topic or "")
    body_html = _md_body_to_html(md_body)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 2em auto; line-height: 1.75; color: #1f2937; max-width: 720px; padding: 0 1em; }}
h1 {{ font-size: 1.6em; margin-bottom: 0.8em; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.4em; }}
h2 {{ font-size: 1.2em; margin-top: 1.5em; margin-bottom: 0.6em; color: #111827; }}
p {{ margin: 0.75em 0; }}
strong {{ color: #111827; }}
a {{ color: #2563eb; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.figure {{ margin: 1.5em auto; text-align: center; }}
.figure img {{ max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.figure figcaption {{ font-size: 0.9em; color: #6b7280; margin-top: 0.5em; font-style: italic; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="content">{body_html}</div>
</body>
</html>"""


def to_docx(
    article,
    parts: list[tuple[str, str]],
    font_config: dict | None = None,
    image_slots: dict | None = None,
    section_id_to_type: dict | None = None,
    layout_preference: str | None = None,
) -> tuple[bytes, str]:
    """纯文本兜底方案，可选 font_config, image_slots (section_id -> slot list)"""
    from docx import Document
    from docx.shared import Pt

    type_to_section_id: dict[str, int] = {}
    if section_id_to_type:
        for sid, stype in section_id_to_type.items():
            type_to_section_id.setdefault(stype, sid)

    doc = Document()
    doc.add_heading(article.title or article.topic or "未命名", 0)
    for idx, (title, body) in enumerate(parts):
        if title:
            doc.add_heading(title, level=1)
        for para in body.split("\n\n"):
            stripped = para.strip()
            if not stripped:
                continue
            if stripped.startswith("[配图·"):
                continue
            doc.add_paragraph(stripped)

        if image_slots:
            for sid, slots in image_slots.items():
                for sl in slots:
                    embed_image_slot_in_docx(
                        doc,
                        image_path=getattr(sl, 'image_path', None),
                        intent_text=getattr(sl, 'intent_text', '') or '',
                        image_status=getattr(sl, 'image_status', '') or '',
                        layout_preference=layout_preference,
                    )
            image_slots = None

    if font_config:
        _apply_font_config(doc, font_config)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue(), f"{(article.topic or 'article').replace('/', '-')}.docx"


def _apply_font_config(doc: Any, font_config: dict) -> None:
    """Apply contest font requirements to all body paragraphs in a DOCX document."""
    from docx.shared import Pt
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    font_name = font_config.get("font_name")
    pt_size = font_config.get("pt_size")
    if not font_name and not pt_size:
        return
    for para in doc.paragraphs:
        if para.style and para.style.name and para.style.name.startswith("Heading"):
            continue
        for run in para.runs:
            if font_name:
                run.font.name = font_name
                rpr = run._element.get_or_add_rPr()
                rfonts = rpr.find(qn("w:rFonts"))
                if rfonts is None:
                    rfonts = OxmlElement("w:rFonts")
                    rpr.insert(0, rfonts)
                rfonts.set(qn("w:eastAsia"), font_name)
            if pt_size:
                run.font.size = Pt(pt_size)

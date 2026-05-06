"""海报模式渲染器：Jinja2 模板 → HTML → (可选) PDF via Playwright。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app.services.export.html_docx import (
    _strip_reference_nodes,
    image_to_data_uri,
    resolve_image_abs_path,
)


class PosterRenderError(RuntimeError):
    """渲染失败专用异常。"""


@dataclass(frozen=True)
class PosterTemplate:
    """海报模板元信息。"""

    id: str
    name: str
    description: str
    aspect_hint: str  # "magazine" / "card" / "long" — 仅作 UI 提示
    accent_color: str  # 模板主色，前端做色卡预览
    cover_style: str  # "hero_image" / "color_block" / "minimal"


POSTER_TEMPLATES: tuple[PosterTemplate, ...] = (
    PosterTemplate(
        id="contest_pro",
        name="参赛推作",
        description="正式、严谨、突出作者与单位，适合参赛作品",
        aspect_hint="magazine",
        accent_color="#0f3a8b",
        cover_style="hero_image",
    ),
    PosterTemplate(
        id="clinical_strict",
        name="临床严谨",
        description="衬线字体、克制配色、引用规范，适合医学类正式发布",
        aspect_hint="long",
        accent_color="#1f4e79",
        cover_style="minimal",
    ),
    PosterTemplate(
        id="wechat_warm",
        name="公众号跨型",
        description="柔和色调、图文交错、亲切阅读感，适合公众号头条",
        aspect_hint="magazine",
        accent_color="#c2410c",
        cover_style="hero_image",
    ),
    PosterTemplate(
        id="xhs_card",
        name="小红书图卡",
        description="鲜亮色块、强标题、信息卡片化，适合小红书 / 朋友圈封面",
        aspect_hint="card",
        accent_color="#db2777",
        cover_style="color_block",
    ),
    PosterTemplate(
        id="zhihu_long",
        name="知乎长文",
        description="极简留白、聚焦正文、引用突出，适合知乎专栏",
        aspect_hint="long",
        accent_color="#0284c7",
        cover_style="minimal",
    ),
    PosterTemplate(
        id="card_image_left",
        name="卡片·左图右文",
        description="每节图文左右排版，主图在左、文字在右，节奏感强；多图时取首图为主图",
        aspect_hint="card",
        accent_color="#2563eb",
        cover_style="hero_image",
    ),
    PosterTemplate(
        id="card_image_right",
        name="卡片·左文右图",
        description="每节图文左右排版，文字在左、主图在右，更适合先讲内容再展示视觉",
        aspect_hint="card",
        accent_color="#2563eb",
        cover_style="hero_image",
    ),
)


def list_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "aspect_hint": t.aspect_hint,
            "accent_color": t.accent_color,
            "cover_style": t.cover_style,
        }
        for t in POSTER_TEMPLATES
    ]


def _get_template(template_id: str) -> PosterTemplate:
    for t in POSTER_TEMPLATES:
        if t.id == template_id:
            return t
    raise PosterRenderError(f"未知模板：{template_id}")


# ════════════════════════════════════════════════════════════════
#  TipTap JSON → 段落数据
# ════════════════════════════════════════════════════════════════

def _node_inline_text(node: dict) -> str:
    """从单个 inline 节点抽 text。"""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "") or ""
    children = node.get("content") or []
    return "".join(_node_inline_text(c) for c in children)


def _node_to_html_inline(node: dict) -> str:
    """单段内的 inline 渲染：保留 bold / italic / underline / strike / link / textStyle。"""
    import html as html_lib

    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        text = html_lib.escape(node.get("text", "") or "")
        marks = node.get("marks") or []
        ts_style = ""
        for mk in marks:
            mt = mk.get("type")
            if mt == "bold":
                text = f"<strong>{text}</strong>"
            elif mt == "italic":
                text = f"<em>{text}</em>"
            elif mt == "underline":
                text = f"<u>{text}</u>"
            elif mt == "strike":
                text = f"<s>{text}</s>"
            elif mt == "link":
                href = (mk.get("attrs") or {}).get("href", "")
                if href:
                    safe_href = html_lib.escape(href, quote=True)
                    text = f'<a href="{safe_href}">{text}</a>'
            elif mt == "textStyle":
                attrs = mk.get("attrs") or {}
                style_parts: list[str] = []
                ff = attrs.get("fontFamily")
                if isinstance(ff, str) and ff.strip():
                    style_parts.append(f"font-family:{ff.strip()}")
                fs = attrs.get("fontSize")
                if isinstance(fs, str) and fs.strip():
                    style_parts.append(f"font-size:{fs.strip()}")
                if style_parts:
                    ts_style = f' style="{";".join(style_parts)}"'
        if ts_style:
            text = f"<span{ts_style}>{text}</span>"
        return text
    if node.get("type") == "hardBreak":
        return "<br/>"
    children = node.get("content") or []
    return "".join(_node_to_html_inline(c) for c in children)


def _paragraph_style_attr(attrs: dict | None) -> str:
    """根据 paragraph/heading attrs 生成行内 style 字符串（含起始空格）。"""
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


def _block_to_html(node: dict) -> str:
    """块级节点 → HTML（段落 / 标题 / 列表 / 引用）。"""
    if not isinstance(node, dict):
        return ""
    t = node.get("type", "")
    children = node.get("content") or []
    if t == "paragraph":
        inner = "".join(_node_to_html_inline(c) for c in children)
        if not inner.strip():
            return ""
        style_attr = _paragraph_style_attr(node.get("attrs") or {})
        return f"<p{style_attr}>{inner}</p>"
    if t == "heading":
        level = int((node.get("attrs") or {}).get("level", 2)) or 2
        level = min(max(level, 2), 4)
        inner = "".join(_node_to_html_inline(c) for c in children)
        if not inner.strip():
            return ""
        style_attr = _paragraph_style_attr(node.get("attrs") or {})
        return f"<h{level}{style_attr}>{inner}</h{level}>"
    if t == "bulletList":
        items = "".join(
            f"<li>{''.join(_block_to_html(cc) for cc in (c.get('content') or []))}</li>"
            for c in children if isinstance(c, dict)
        )
        return f"<ul>{items}</ul>"
    if t == "orderedList":
        items = "".join(
            f"<li>{''.join(_block_to_html(cc) for cc in (c.get('content') or []))}</li>"
            for c in children if isinstance(c, dict)
        )
        return f"<ol>{items}</ol>"
    if t == "blockquote":
        inner = "".join(_block_to_html(c) for c in children)
        return f"<blockquote>{inner}</blockquote>"
    # 兜底：抽 text
    return "<p>" + "".join(_node_inline_text(c) for c in children) + "</p>"


def _content_json_to_html(content_json: Any) -> str:
    if not content_json:
        return ""
    try:
        if isinstance(content_json, str):
            content_json = json.loads(content_json)
    except Exception:
        return ""
    if not isinstance(content_json, dict):
        return ""
    nodes = content_json.get("content") or []
    nodes = _strip_reference_nodes(nodes)
    parts = [_block_to_html(n) for n in nodes if isinstance(n, dict)]
    return "\n".join(p for p in parts if p)


# ════════════════════════════════════════════════════════════════
#  数据组装
# ════════════════════════════════════════════════════════════════

def _slot_lookup(image_slots: Iterable[Any] | None) -> dict[int, list]:
    out: dict[int, list] = {}
    for sl in image_slots or []:
        sid = getattr(sl, "section_id", None) or 0
        out.setdefault(sid, []).append(sl)
    return out


def _slot_to_view(slot: Any, section_type: str = "") -> dict[str, Any]:
    """slot ORM → 模板可用 dict（含已嵌入的 data URI）。"""
    image_path = getattr(slot, "image_path", None)
    data_uri = image_to_data_uri(image_path)
    return {
        "id": getattr(slot, "id", None),
        "section_id": getattr(slot, "section_id", None),
        "section_type": section_type or "",
        "image_path": image_path,
        "image_data_uri": data_uri,
        "image_status": getattr(slot, "image_status", "") or "",
        "intent_text": (getattr(slot, "intent_text", "") or "").strip(),
        "aspect_ratio": getattr(slot, "aspect_ratio", "16:9") or "16:9",
        "image_provider": getattr(slot, "image_provider", "") or "",
    }


def _hero_slot(slot_views_by_section: dict[int, list[dict]]) -> dict | None:
    """题图选取规则：最早 order 的章节中的第一张已上传图片。"""
    for sid, slots in slot_views_by_section.items():
        for sv in slots:
            if sv.get("image_data_uri"):
                return sv
    return None


def _author_meta(article: Any) -> dict[str, Any]:
    """从 article 收集作者 / 单位 / 日期等元信息。

    数据库当前未必有这些字段，缺失时模板自动隐藏。
    """
    return {
        "title": getattr(article, "title", None) or getattr(article, "topic", None) or "未命名作品",
        "subtitle": getattr(article, "subtitle", None) or "",
        "author": getattr(article, "author_name", None) or getattr(article, "author", None) or "",
        "affiliation": getattr(article, "affiliation", None) or "",
        "date": (
            getattr(article, "published_at", None)
            or getattr(article, "updated_at", None)
            or datetime.utcnow()
        ).strftime("%Y-%m-%d") if hasattr(article, "updated_at") else datetime.utcnow().strftime("%Y-%m-%d"),
        "specialty": getattr(article, "specialty", None) or "",
        "topic": getattr(article, "topic", None) or "",
        "ai_declaration": getattr(article, "ai_declaration", None) or "",
    }


def _build_authors_list(
    first_author: str | None,
    second_author: str | None,
    corresponding_author: str | None,
) -> list[dict[str, str]]:
    """根据三个独立输入构建带角色 label 的作者列表（供模板按"label · 姓名"渲染）。

    输入留空的角色会被跳过。`姓名 *` 等冗余标记不在此处处理（前端原样传）。
    """
    out: list[dict[str, str]] = []
    pairs = [
        ("第一作者", first_author),
        ("第二作者", second_author),
        ("通讯作者", corresponding_author),
    ]
    for label, raw in pairs:
        name = (raw or "").strip()
        if not name:
            continue
        out.append({"label": label, "name": name})
    return out


def _apply_overrides(ctx: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    """把前端传来的 overrides 覆盖到 ctx，仅本次渲染生效。

    支持的 overrides 字段（均可选）：
      - title / subtitle / affiliation: 字符串覆盖 meta.*
      - authors: [{label, name}] 整体替换 meta.authors（同时刷新 meta.author）
      - references: 整体替换 ctx['references']（已 include_references=False 则忽略）
      - section_title_overrides: {section_type: title_str} 改各节标题
      - section_body_overrides: {section_type: body_html_str} 改各节正文 HTML
      - section_hidden: [section_type, ...] 整节隐藏
      - section_order: [section_type, ...] 自定义节顺序
      - slot_overrides: {str(slot_id): {hidden?: bool, caption?: str, order?: int}}
      - hero_hidden: bool — 隐藏题图（封面仍在，只是不放图片）
    """
    if not overrides or not isinstance(overrides, dict):
        return ctx

    meta = ctx.setdefault("meta", {})
    if isinstance(overrides.get("title"), str):
        meta["title"] = overrides["title"].strip() or meta.get("title", "")
    if isinstance(overrides.get("subtitle"), str):
        meta["subtitle"] = overrides["subtitle"].strip()
    if isinstance(overrides.get("affiliation"), str):
        meta["affiliation"] = overrides["affiliation"].strip()
    if isinstance(overrides.get("authors"), list):
        cleaned = []
        for a in overrides["authors"]:
            if not isinstance(a, dict):
                continue
            name = (a.get("name") or "").strip()
            label = (a.get("label") or "").strip()
            if name:
                cleaned.append({"label": label or "作者", "name": name})
        if cleaned:
            meta["authors"] = cleaned
            meta["author"] = cleaned[0]["name"]
        else:
            meta.pop("authors", None)

    if isinstance(overrides.get("references"), list):
        ctx["references"] = [str(x) for x in overrides["references"] if str(x).strip()]

    sections: list[dict[str, Any]] = ctx.get("sections") or []
    title_overrides = overrides.get("section_title_overrides") or {}
    body_overrides = overrides.get("section_body_overrides") or {}
    hidden_types = set(overrides.get("section_hidden") or [])
    for sec in sections:
        st = sec.get("section_type") or ""
        if st in title_overrides and isinstance(title_overrides[st], str):
            sec["title"] = title_overrides[st]
        if st in body_overrides and isinstance(body_overrides[st], str):
            sec["body_html"] = body_overrides[st]
    sections = [s for s in sections if (s.get("section_type") or "") not in hidden_types]

    order = overrides.get("section_order")
    if isinstance(order, list) and order:
        order_index = {st: i for i, st in enumerate(order)}
        sections.sort(key=lambda s: order_index.get(s.get("section_type") or "", 10_000))
    ctx["sections"] = sections

    slot_ovr = overrides.get("slot_overrides") or {}
    if isinstance(slot_ovr, dict) and slot_ovr:
        for sec in ctx["sections"]:
            slots = sec.get("slots") or []
            new_slots: list[dict[str, Any]] = []
            for sv in slots:
                sid = str(sv.get("id") or "")
                ovr = slot_ovr.get(sid) or slot_ovr.get(int(sid)) if sid.isdigit() else slot_ovr.get(sid)
                if not ovr or not isinstance(ovr, dict):
                    new_slots.append(sv)
                    continue
                if ovr.get("hidden"):
                    continue
                if isinstance(ovr.get("caption"), str):
                    sv = {**sv, "caption_override": ovr["caption"].strip()}
                if isinstance(ovr.get("order"), (int, float)):
                    sv = {**sv, "_ovr_order": int(ovr["order"])}
                new_slots.append(sv)
            new_slots.sort(key=lambda x: x.get("_ovr_order", 0))
            sec["slots"] = new_slots

    if overrides.get("hero_hidden") and ctx.get("hero"):
        # 保留 hero dict 但清掉图，模板里 image_data_uri 为空就不显示
        h = dict(ctx["hero"])
        h["image_data_uri"] = ""
        h["image_path"] = ""
        ctx["hero"] = h

    return ctx


def build_render_context(
    article: Any,
    section_parts: list[tuple[str, dict | None, str]],
    image_slots: Iterable[Any] | None = None,
    references: list[str] | None = None,
    template_id: str = "contest_pro",
    *,
    first_author: str | None = None,
    second_author: str | None = None,
    corresponding_author: str | None = None,
    affiliation_override: str | None = None,
    include_references: bool = True,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """组装 Jinja 渲染上下文。

    section_parts: [(section_title, content_json, section_type)]
    """
    template = _get_template(template_id)

    # section_id 不在 section_parts 里，所以按 section_type 关联（同 _merged_export 套路）
    # 这里 section_parts 没有 section_id 信息，需要从 article.sections 里查
    section_meta: list[dict[str, Any]] = []
    sections = getattr(article, "sections", None) or []
    type_to_section_id: dict[str, int] = {}
    for s in sections:
        st = getattr(s, "section_type", None)
        if st and st not in type_to_section_id:
            type_to_section_id[st] = getattr(s, "id", 0)

    sid_to_section_type: dict[int, str] = {
        getattr(s, "id", 0): getattr(s, "section_type", "") or ""
        for s in sections
    }
    slots_by_section_id = _slot_lookup(image_slots)
    slot_views_by_sid: dict[int, list[dict]] = {
        sid: [_slot_to_view(s, sid_to_section_type.get(sid, "")) for s in lst]
        for sid, lst in slots_by_section_id.items()
    }

    cf = getattr(article, "content_format", "article") or "article"
    hide_section_headings = cf == "article"

    consumed_section_ids: set[int] = set()
    for idx, (sec_title, content_json, section_type) in enumerate(section_parts):
        if (cf == "article") and (section_type == "intro"):
            # legacy 'intro' 在 article 模式跳过
            continue
        section_id = type_to_section_id.get(section_type or "") or 0
        body_html = _content_json_to_html(content_json)
        sec_slots = slot_views_by_sid.get(section_id, [])
        # 既无正文又无图 → 跳过；只要其一存在就保留容器
        if not body_html and not sec_slots:
            continue
        section_meta.append({
            "index": idx,
            "title": sec_title or "",
            "section_type": section_type or "",
            "body_html": body_html,
            "show_heading": not hide_section_headings,
            "slots": sec_slots,
        })
        if section_id:
            consumed_section_ids.add(section_id)

    # ── 兜底：仍可能有 slot 的 section_id 在前面循环未被消费
    #    （例如 section_parts 缺失某节、或 section_type 与 sections 表对不齐）
    # 这里按 ArticleSection 顺序补出 image-only section，保证"6 张图导出 6 张图"。
    sid_to_section_obj = {getattr(s, "id", 0): s for s in sections}
    next_index = len(section_parts)
    for sid in slot_views_by_sid.keys():
        if not sid or sid in consumed_section_ids:
            continue
        sec_obj = sid_to_section_obj.get(sid)
        if not sec_obj:
            continue
        section_meta.append({
            "index": next_index,
            "title": (getattr(sec_obj, "title", None)
                      or getattr(sec_obj, "section_type", None) or ""),
            "section_type": getattr(sec_obj, "section_type", "") or "",
            "body_html": "",
            "show_heading": not hide_section_headings,
            "slots": slot_views_by_sid.get(sid, []),
        })
        next_index += 1

    hero = _hero_slot(slot_views_by_sid)

    # ★ 一张图在一篇文章里只能用一次：被选作题图（hero）的图，从正文章节里剔除，
    #   避免它既出现在标题栏背景，又重复出现在导言/第一节。
    if hero and hero.get("image_path"):
        hero_path = hero["image_path"]
        for sec in section_meta:
            slots = sec.get("slots") or []
            if slots:
                sec["slots"] = [sv for sv in slots if sv.get("image_path") != hero_path]

    # 移除"补出来的 image-only 章节"中所有图都被剔除（仅剩 hero 占位）的空块
    section_meta = [
        sec for sec in section_meta
        if (sec.get("body_html") or sec.get("slots"))
    ]

    meta = _author_meta(article)

    # 用户在导出对话框里手填的「带角色的多作者」+ 单位优先覆盖到 meta
    authors_list = _build_authors_list(first_author, second_author, corresponding_author)
    if authors_list:
        meta["authors"] = authors_list
        # 留一个 fallback：第一位作者的姓名同步进 meta.author（旧模板兼容）
        meta["author"] = authors_list[0]["name"]
    if affiliation_override is not None and affiliation_override.strip():
        meta["affiliation"] = affiliation_override.strip()

    ctx: dict[str, Any] = {
        "meta": meta,
        "sections": section_meta,
        "references": (references or []) if include_references else [],
        "hero": hero,
        "template": {
            "id": template.id,
            "name": template.name,
            "accent_color": template.accent_color,
            "cover_style": template.cover_style,
        },
        "editable": False,
    }
    return _apply_overrides(ctx, overrides)


# ════════════════════════════════════════════════════════════════
#  HTML 渲染
# ════════════════════════════════════════════════════════════════

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _jinja_env():
    """Lazy 创建 Jinja2 环境。"""
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError as e:
        raise PosterRenderError(
            "缺少 jinja2 包。请在 backend 环境执行 pip install jinja2"
        ) from e
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(
    article: Any,
    section_parts: list[tuple[str, dict | None, str]],
    image_slots: Iterable[Any] | None = None,
    references: list[str] | None = None,
    template_id: str = "contest_pro",
    *,
    first_author: str | None = None,
    second_author: str | None = None,
    corresponding_author: str | None = None,
    affiliation_override: str | None = None,
    include_references: bool = True,
    overrides: dict[str, Any] | None = None,
    editable: bool = False,
) -> str:
    template = _get_template(template_id)
    ctx = build_render_context(
        article, section_parts, image_slots, references, template_id,
        first_author=first_author,
        second_author=second_author,
        corresponding_author=corresponding_author,
        affiliation_override=affiliation_override,
        include_references=include_references,
        overrides=overrides,
    )
    ctx["editable"] = bool(editable)
    env = _jinja_env()
    try:
        tpl = env.get_template(f"{template.id}.html")
    except Exception as e:
        raise PosterRenderError(f"模板 {template.id}.html 加载失败：{e}") from e
    return tpl.render(**ctx)


# ════════════════════════════════════════════════════════════════
#  PDF 渲染（Playwright Chromium）
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
#  DOCX 渲染（用于"导出 Word"二次编辑）
# ════════════════════════════════════════════════════════════════

def _docx_set_paragraph_align(para: Any, align: str | None) -> None:
    if not align:
        return
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    mapping = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    if align in mapping:
        para.alignment = mapping[align]


_INLINE_TAGS = {"strong", "b", "em", "i", "u", "s", "del", "strike", "sup", "sub", "a", "span"}
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "div"}


def _docx_apply_inline_stack(run: Any, inline_stack: list[str]) -> None:
    """根据当前 inline tag 栈把样式应用到 run。"""
    tags = set(inline_stack)
    if tags & {"strong", "b"}:
        run.bold = True
    if tags & {"em", "i"}:
        run.italic = True
    if "u" in tags:
        run.underline = True
    if tags & {"s", "del", "strike"}:
        run.font.strike = True
    if "sup" in tags:
        run.font.superscript = True
    if "sub" in tags:
        run.font.subscript = True


def _docx_html_to_paragraphs(doc: Any, body_html: str, *, default_indent: bool = True) -> None:
    """把 HTML 串（来自 _content_json_to_html / overrides 的 section_body）写入 docx。

    用 stdlib html.parser 实现，不引入 BeautifulSoup 新依赖。
    支持的块级元素：h2~h4 / p / ul / ol / blockquote / div / li。
    inline：strong/em/u/s/sup/sub/br/a/span。
    """
    if not body_html:
        return
    from html.parser import HTMLParser
    from docx.shared import Inches

    class _Builder(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.inline_stack: list[str] = []
            self.current_para: Any = None
            self.current_para_indent: bool = False
            # 记录祖先块栈，用于决定是否处于列表 / 引用等
            self.list_stack: list[str] = []  # "ul" / "ol"
            self.in_blockquote: int = 0

        def _ensure_paragraph(self, *, indent: bool) -> Any:
            if self.current_para is None:
                p = doc.add_paragraph()
                if indent and not self.list_stack and not self.in_blockquote:
                    p.paragraph_format.first_line_indent = Inches(0.3)
                if self.in_blockquote:
                    p.paragraph_format.left_indent = Inches(0.3)
                self.current_para = p
                self.current_para_indent = indent
            return self.current_para

        def _close_paragraph(self) -> None:
            self.current_para = None
            self.current_para_indent = False

        def _attr_align(self, attrs: list[tuple[str, str | None]]) -> str | None:
            for k, v in attrs:
                if (k or "").lower() == "style" and v:
                    for part in v.split(";"):
                        kv = part.split(":")
                        if len(kv) == 2 and kv[0].strip().lower() == "text-align":
                            return kv[1].strip().lower()
            return None

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag == "br":
                if self.current_para is not None:
                    self.current_para.add_run().add_break()
                return
            if tag in _INLINE_TAGS:
                self.inline_stack.append(tag)
                return
            # 块级
            if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                self._close_paragraph()
                level = max(2, min(int(tag[1:]), 4))
                heading = doc.add_heading(level=level)
                _docx_set_paragraph_align(heading, self._attr_align(attrs))
                self.current_para = heading
                self.current_para_indent = False
                return
            if tag == "p":
                self._close_paragraph()
                p = doc.add_paragraph()
                if default_indent and not self.list_stack and not self.in_blockquote:
                    p.paragraph_format.first_line_indent = Inches(0.3)
                if self.in_blockquote:
                    p.paragraph_format.left_indent = Inches(0.3)
                _docx_set_paragraph_align(p, self._attr_align(attrs))
                self.current_para = p
                return
            if tag in {"ul", "ol"}:
                self._close_paragraph()
                self.list_stack.append(tag)
                return
            if tag == "li":
                self._close_paragraph()
                style = "List Bullet"
                if self.list_stack and self.list_stack[-1] == "ol":
                    style = "List Number"
                try:
                    p = doc.add_paragraph(style=style)
                except Exception:
                    p = doc.add_paragraph()
                self.current_para = p
                return
            if tag == "blockquote":
                self._close_paragraph()
                self.in_blockquote += 1
                return
            if tag == "div":
                self._close_paragraph()
                return
            # 其他未知标签（如 figure/img）忽略，仅按 inline 兜底
            self.inline_stack.append(tag)

        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag == "br":
                return
            if tag in _INLINE_TAGS:
                if self.inline_stack and self.inline_stack[-1] == tag:
                    self.inline_stack.pop()
                else:
                    # 不匹配时尽量找到并移除
                    for i in range(len(self.inline_stack) - 1, -1, -1):
                        if self.inline_stack[i] == tag:
                            self.inline_stack.pop(i)
                            break
                return
            if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p"}:
                self._close_paragraph()
                return
            if tag in {"ul", "ol"}:
                if self.list_stack and self.list_stack[-1] == tag:
                    self.list_stack.pop()
                return
            if tag == "li":
                self._close_paragraph()
                return
            if tag == "blockquote":
                self.in_blockquote = max(0, self.in_blockquote - 1)
                return
            if tag == "div":
                self._close_paragraph()
                return
            # 未知 inline 兜底
            if self.inline_stack and self.inline_stack[-1] == tag:
                self.inline_stack.pop()

        def handle_data(self, data):
            if not data:
                return
            # 只在段落里写文本；忽略列表 / 块外的纯空白
            if self.current_para is None:
                if not data.strip():
                    return
                self._ensure_paragraph(indent=default_indent)
            run = self.current_para.add_run(data)
            _docx_apply_inline_stack(run, self.inline_stack)

    builder = _Builder()
    builder.feed(body_html)
    builder.close()


def render_docx(
    article: Any,
    section_parts: list[tuple[str, dict | None, str]],
    image_slots: Iterable[Any] | None = None,
    references: list[str] | None = None,
    template_id: str = "contest_pro",
    *,
    first_author: str | None = None,
    second_author: str | None = None,
    corresponding_author: str | None = None,
    affiliation_override: str | None = None,
    include_references: bool = True,
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """把海报渲染上下文转成 DOCX 字节，便于用户在 Word 里二次编辑。

    实现策略：直接复用 build_render_context（已应用 overrides），按 ctx 中的
    meta / hero / sections / references 顺序写入 docx，章节正文走 body_html
    → BeautifulSoup → 段落的转换，inline 样式（粗斜体/上下标）尽量保留。
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError as e:
        raise PosterRenderError(
            "缺少 python-docx 包。请在 backend 环境执行 pip install python-docx"
        ) from e

    ctx = build_render_context(
        article, section_parts, image_slots, references, template_id,
        first_author=first_author,
        second_author=second_author,
        corresponding_author=corresponding_author,
        affiliation_override=affiliation_override,
        include_references=include_references,
        overrides=overrides,
    )

    meta = ctx.get("meta") or {}
    sections = ctx.get("sections") or []
    refs = ctx.get("references") or []
    hero = ctx.get("hero") or None

    doc = Document()

    title = (meta.get("title") or "").strip() or "未命名作品"
    doc.add_heading(title, level=0)

    subtitle = (meta.get("subtitle") or "").strip()
    if subtitle:
        sp = doc.add_paragraph()
        sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = sp.add_run(subtitle)
        run.font.size = Pt(13)
        run.italic = True

    authors = meta.get("authors") or []
    if authors:
        ap = doc.add_paragraph()
        ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        author_text = "  ".join(
            f"{(a.get('label') or '').strip()} · {(a.get('name') or '').strip()}".lstrip(" ·")
            for a in authors if isinstance(a, dict)
        )
        run = ap.add_run(author_text)
        run.font.size = Pt(11)
    elif (meta.get("author") or "").strip():
        ap = doc.add_paragraph()
        ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = ap.add_run(str(meta["author"]).strip())
        run.font.size = Pt(11)

    affiliation = (meta.get("affiliation") or "").strip()
    if affiliation:
        afp = doc.add_paragraph()
        afp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = afp.add_run(affiliation)
        run.font.size = Pt(10)

    if hero and hero.get("image_path"):
        hero_abs = resolve_image_abs_path(hero.get("image_path"))
        if hero_abs:
            try:
                hp = doc.add_paragraph()
                hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                hp.add_run().add_picture(hero_abs, width=Inches(5.5))
            except Exception:
                pass

    cf = getattr(article, "content_format", "article") or "article"
    default_indent = cf in {
        "article", "contest_article", "story", "debunk", "qa_article",
        "research_read", "patient_handbook", "quiz_article",
    }

    for sec in sections:
        sec_title = (sec.get("title") or "").strip()
        body_html = sec.get("body_html") or ""
        slots = sec.get("slots") or []
        show_heading = bool(sec.get("show_heading", True))
        if show_heading and sec_title:
            doc.add_heading(sec_title, level=1)
        if body_html:
            _docx_html_to_paragraphs(doc, body_html, default_indent=default_indent)
        for sv in slots:
            sv_path = sv.get("image_path")
            abs_p = resolve_image_abs_path(sv_path) if sv_path else None
            if abs_p:
                try:
                    pp = doc.add_paragraph()
                    pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    pp.add_run().add_picture(abs_p, width=Inches(5.0))
                except Exception:
                    pass
            caption = (sv.get("caption_override") or sv.get("intent_text") or "").strip()
            if caption:
                cap = doc.add_paragraph(caption)
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in cap.runs:
                    run.font.size = Pt(9)
                    run.italic = True

    if refs:
        doc.add_heading("参考文献", level=1)
        for ref in refs:
            rp = doc.add_paragraph(str(ref))
            for run in rp.runs:
                run.font.size = Pt(9)

    import io as _io
    buf = _io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


async def render_pdf(
    article: Any,
    section_parts: list[tuple[str, dict | None, str]],
    image_slots: Iterable[Any] | None = None,
    references: list[str] | None = None,
    template_id: str = "contest_pro",
    page_format: str = "A4",  # 保留参数以兼容旧调用，但默认走"单长页"
    margin: str = "12mm",     # 保留参数（同上）
    *,
    first_author: str | None = None,
    second_author: str | None = None,
    corresponding_author: str | None = None,
    affiliation_override: str | None = None,
    include_references: bool = True,
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """通过 Playwright Chromium 渲染 PDF。

    海报模式默认输出"宽度按 A4（210mm），高度按内容自适应"的连续单长页 PDF —
    避免窄卡片版式（小红书/公众号/知乎等）在 A4 多页打印时被切成断片。
    """
    html = render_html(
        article, section_parts, image_slots, references, template_id,
        first_author=first_author,
        second_author=second_author,
        corresponding_author=corresponding_author,
        affiliation_override=affiliation_override,
        include_references=include_references,
        overrides=overrides,
        editable=False,  # PDF 永不带编辑器外观
    )
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise PosterRenderError(
            "缺少 playwright 包。请执行：\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium\n"
        ) from e
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                # 设置一个合理的视口宽度（≈ A4 宽度），让 CSS 媒体查询和宽度计算稳定
                page = await browser.new_page(viewport={"width": 794, "height": 1123})
                await page.set_content(html, wait_until="networkidle")

                # 让浏览器使用 print 媒体规则（与 @media print 一致）
                await page.emulate_media(media="print")

                # 按页面实际渲染高度生成"宽度固定 / 高度连续"的单长页 PDF
                page_height_px = await page.evaluate(
                    "Math.ceil(document.documentElement.scrollHeight)"
                )
                # 高度上限保护（极端长文章避免内存爆掉）：~120 个 A4 页
                page_height_px = min(max(page_height_px, 1123), 1123 * 120)

                pdf_bytes = await page.pdf(
                    width="794px",
                    height=f"{page_height_px}px",
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    print_background=True,
                )
                return pdf_bytes
            finally:
                await browser.close()
    except Exception as e:
        msg = str(e)
        if "Executable doesn't exist" in msg or "browserType.launch" in msg:
            raise PosterRenderError(
                "Chromium 未安装。请执行：python -m playwright install chromium"
            ) from e
        raise PosterRenderError(f"PDF 渲染失败：{msg}") from e

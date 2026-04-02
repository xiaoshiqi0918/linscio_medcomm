"""
将 verify_report.claims.verified 映射为 Tiptap/ProseMirror JSON 中的 medClaim 标记。
仅处理「单段落、根下仅文本节点」的常见生成结果，避免破坏已有复杂结构。
"""
from __future__ import annotations

from typing import Any


def _paragraph_plain_and_text_nodes(paragraph: dict) -> tuple[str, list[dict]] | None:
    inner = paragraph.get("content")
    if not isinstance(inner, list) or not inner:
        return None
    parts: list[str] = []
    text_nodes: list[dict] = []
    for n in inner:
        if not isinstance(n, dict) or n.get("type") != "text" or not isinstance(n.get("text"), str):
            return None
        parts.append(n["text"])
        text_nodes.append(n)
    return "".join(parts), text_nodes


def _claim_mark_attrs(row: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    pid = row.get("paper_id")
    if pid is not None:
        try:
            attrs["paperId"] = int(pid)
        except (TypeError, ValueError):
            pass
    snip = row.get("evidence_snippet")
    if snip:
        attrs["evidenceSnippet"] = str(snip)[:4000]
    src = row.get("evidence_source")
    if src:
        s = str(src)[:800]
        attrs["evidenceSource"] = s
        attrs["source"] = s
    cid = row.get("chunk_id")
    if cid is not None and str(cid).strip():
        attrs["chunkId"] = str(cid)
    return attrs


def _find_spans(plain: str, verified: list[dict[str, Any]]) -> list[tuple[int, int, dict[str, Any]]]:
    spans: list[tuple[int, int, dict[str, Any]]] = []
    for row in verified:
        if not isinstance(row, dict):
            continue
        mt = (row.get("match_text") or row.get("text") or "").strip()
        if not mt:
            continue
        if mt.endswith("…"):
            mt = mt[:-1].strip()
        if not mt:
            continue
        idx = plain.find(mt)
        if idx < 0:
            continue
        spans.append((idx, idx + len(mt), row))
    spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    chosen: list[tuple[int, int, dict[str, Any]]] = []
    cur_end = -1
    for start, end, row in spans:
        if start < cur_end:
            continue
        chosen.append((start, end, row))
        cur_end = end
    chosen.sort(key=lambda x: x[0])
    return chosen


def _build_paragraph_content(plain: str, spans: list[tuple[int, int, dict[str, Any]]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    pos = 0
    for start, end, row in spans:
        if start > pos:
            nodes.append({"type": "text", "text": plain[pos:start]})
        attrs = _claim_mark_attrs(row)
        nodes.append(
            {
                "type": "text",
                "text": plain[start:end],
                "marks": [{"type": "medClaim", "attrs": attrs}],
            }
        )
        pos = end
    if pos < len(plain):
        nodes.append({"type": "text", "text": plain[pos:]})
    return nodes if nodes else [{"type": "text", "text": plain}]


def apply_med_claim_marks_to_doc(doc: dict[str, Any], verify_report: dict[str, Any] | None) -> dict[str, Any]:
    if not verify_report or not isinstance(doc, dict):
        return doc
    claims = verify_report.get("claims")
    if not isinstance(claims, dict) or claims.get("skipped"):
        return doc
    verified = claims.get("verified")
    if not isinstance(verified, list) or not verified:
        return doc
    content = doc.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return doc
    para = content[0]
    if not isinstance(para, dict) or para.get("type") != "paragraph":
        return doc
    parsed = _paragraph_plain_and_text_nodes(para)
    if not parsed:
        return doc
    plain, _nodes = parsed
    spans = _find_spans(plain, verified)
    if not spans:
        return doc
    new_inner = _build_paragraph_content(plain, spans)
    return {"type": "doc", "content": [{**para, "content": new_inner}]}

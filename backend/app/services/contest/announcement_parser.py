"""
公告轻量解析 — 上传赛事公告，通过大模型抽取关键参数

v0.3 定位：不追求 100% 自动，目标是把用户填表负担从"几十个字段"降到"确认/修改十几个字段"
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

EXTRACTION_FIELDS = [
    {"key": "name", "label": "赛事名称", "type": "text"},
    {"key": "organizer", "label": "主办单位", "type": "text"},
    {"key": "word_limit", "label": "字数上限", "type": "number"},
    {"key": "font", "label": "字体要求", "type": "text"},
    {"key": "file_format", "label": "提交文件格式", "type": "text"},
    {"key": "naming_template", "label": "文件命名模板", "type": "text"},
    {"key": "image_format", "label": "配图格式", "type": "text"},
    {"key": "deadline", "label": "截止日期", "type": "date"},
    {"key": "ai_disclosure", "label": "AI 使用声明要求", "type": "text"},
    {"key": "layout_preference", "label": "版式偏好", "type": "text"},
    {"key": "other_requirements", "label": "其他要求", "type": "text"},
]


async def parse_contest_announcement(content: bytes, filename: str) -> dict:
    """
    解析赛事公告文件，抽取关键参数

    Returns:
        {
            "fields": [
                {"key": str, "label": str, "value": str|null, "detected": bool},
                ...
            ],
            "raw_text": str,  # 提取的原始文本（供前端显示）
        }
    """
    text = _extract_text(content, filename)

    if not text.strip():
        return {
            "fields": [
                {"key": f["key"], "label": f["label"], "value": None, "detected": False}
                for f in EXTRACTION_FIELDS
            ],
            "raw_text": "",
        }

    try:
        return await _parse_via_llm(text)
    except Exception as e:
        logger.warning("LLM announcement parsing failed: %s, falling back to regex", e)
        return _parse_via_regex(text)


def _extract_text(content: bytes, filename: str) -> str:
    """从文件中提取纯文本"""
    lower = filename.lower()

    if lower.endswith(".txt"):
        for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
            try:
                return content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return content.decode("utf-8", errors="replace")

    if lower.endswith(".pdf"):
        try:
            import io
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return content.decode("utf-8", errors="replace")

    if lower.endswith((".docx", ".doc")):
        try:
            import io
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(para.text for para in doc.paragraphs)
        except Exception:
            return content.decode("utf-8", errors="replace")

    # Fallback: treat as plain text
    return content.decode("utf-8", errors="replace")


async def _parse_via_llm(text: str) -> dict:
    """通过 LLM 抽取公告中的赛制参数"""
    from app.services.llm.manager import get_llm_manager
    import json

    mgr = get_llm_manager()
    system_prompt = (
        "你是一个健康科普赛事公告解析助手。请从以下公告文本中提取赛事参数。\n"
        "以 JSON 对象输出，包含以下字段（无法识别的字段值设为 null）：\n"
        "name（赛事名称）、organizer（主办单位）、word_limit（字数上限，数字）、"
        "font（字体要求）、file_format（提交文件格式如 docx/pdf）、"
        "naming_template（文件命名模板）、image_format（配图格式如 jpg/png）、"
        "deadline（截止日期，YYYY-MM-DD 格式）、"
        "ai_disclosure（AI 使用声明要求：required/recommended/none）、"
        "layout_preference（版式偏好）、other_requirements（其他要求）。\n"
        "只输出纯 JSON，不要其他文字。"
    )

    response = await mgr.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text[:8000]},
        ],
        temperature=0.1,
        max_tokens=1000,
    )

    result_text = response.get("content", "").strip()
    if result_text.startswith("```"):
        lines = result_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        result_text = "\n".join(lines).strip()

    parsed = json.loads(result_text)

    fields = []
    for f in EXTRACTION_FIELDS:
        val = parsed.get(f["key"])
        detected = val is not None and str(val).strip() != ""
        fields.append({
            "key": f["key"],
            "label": f["label"],
            "value": str(val) if val is not None else None,
            "detected": detected,
        })

    return {"fields": fields, "raw_text": text[:3000]}


def _parse_via_regex(text: str) -> dict:
    """正则兜底解析"""
    import re

    results: dict[str, str | None] = {f["key"]: None for f in EXTRACTION_FIELDS}

    word_match = re.search(r"(?:字数|篇幅)[^\d]*(\d{3,5})\s*字", text)
    if word_match:
        results["word_limit"] = word_match.group(1)

    date_match = re.search(r"(?:截止|截至|deadline)[^\d]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", text, re.IGNORECASE)
    if date_match:
        results["deadline"] = date_match.group(1)

    if re.search(r"(?:仿宋|宋体|黑体|楷体|微软雅黑)", text):
        font_match = re.search(r"(仿宋|宋体|黑体|楷体|微软雅黑)(?:.*?(\d+)\s*号)?", text)
        if font_match:
            results["font"] = font_match.group(0).strip()

    format_match = re.search(r"(?:提交|上传|投递).*?(docx|doc|pdf|word)", text, re.IGNORECASE)
    if format_match:
        results["file_format"] = format_match.group(1).lower()

    if re.search(r"(?:jpg|jpeg|png)", text, re.IGNORECASE):
        results["image_format"] = "jpg"

    if re.search(r"AI|人工智能|智能生成", text):
        if re.search(r"(?:必须|应当|须).*?(?:声明|标注|注明).*?AI", text):
            results["ai_disclosure"] = "required"
        elif re.search(r"(?:建议|鼓励).*?(?:声明|标注)", text):
            results["ai_disclosure"] = "recommended"

    fields = []
    for f in EXTRACTION_FIELDS:
        val = results.get(f["key"])
        fields.append({
            "key": f["key"],
            "label": f["label"],
            "value": val,
            "detected": val is not None,
        })

    return {"fields": fields, "raw_text": text[:3000]}

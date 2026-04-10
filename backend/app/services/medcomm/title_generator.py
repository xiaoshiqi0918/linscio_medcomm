"""全文完成后，根据合并正文总结文章标题（用于导出篇首与发布）"""
from __future__ import annotations

import re

from app.services.llm.manager import resolve_model_for_task, TaskTier
from app.services.llm.openai_client import chat_completion


def _clean_title(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    s = s.split("\n")[0].strip()
    s = re.sub(r"^#+\s*", "", s)
    s = s.strip('《》「」""\'" ')
    if len(s) > 100:
        s = s[:100].rstrip()
    return s


def _build_body_excerpt(parts: list[tuple[str, str, str]], max_total: int = 14000) -> str:
    """parts: (section_title, body, section_type)"""
    blocks: list[str] = []
    for sec_title, body, _st in parts:
        b = (body or "").strip()
        if not b:
            continue
        chunk = f"【{sec_title}】\n{b}"
        if len(chunk) > 6000:
            chunk = chunk[:6000] + "\n…"
        blocks.append(chunk)
    combined = "\n\n".join(blocks)
    if len(combined) > max_total:
        combined = combined[: max_total - 20] + "\n\n（后文已省略）"
    return combined


async def generate_article_title(
    *,
    article_id: int,
    topic: str,
    content_format: str,
    platform: str,
    target_audience: str,
    parts: list[tuple[str, str, str]],
    article_default_model: str | None = None,
) -> str:
    body = _build_body_excerpt(parts)
    if not body.strip():
        return ""

    model = await resolve_model_for_task(
        task=TaskTier.FAST,
        article_id=article_id,
        article_default_model=article_default_model,
    )
    system = (
        "你是医学科普编辑。根据用户提供的全文草稿与元数据，生成一个适合发布的文章标题。"
        "要求：准确反映核心信息；通俗可读；避免恐吓式营销；"
        "长度建议 8～30 个汉字（或相当长度）；不要书名号、引号、换行、序号前缀；"
        "只输出一行标题，不要解释。"
    )
    user = (
        f"主题线索：{topic or '（未填）'}\n"
        f"写作形式：{content_format}\n"
        f"目标平台：{platform}\n"
        f"受众：{target_audience}\n\n"
        f"全文草稿：\n{body}"
    )
    raw = await chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
        stream=False,
    )
    return _clean_title(raw or "")

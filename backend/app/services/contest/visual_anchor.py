"""视觉锚点服务 — 全文角色卡 + 风格锁 + Seed 锁

核心目标：保证一篇文章中所有 AI 生成配图的人物外貌、画风、配色一致性。

工作流：
1. extract_visual_anchor_for_article(): LLM 扫描全文 → 抽取核心角色（≤5）+ 风格基调
2. extract_visual_anchor_from_image(): GPT-4o vision 看图识别角色 + 风格（可单图，也可"首图"）
3. get_or_create_anchor(): 获取 / 创建文章的锚点配置
4. inject_anchor_to_intent(): 把角色卡 + 风格锁注入到画意 prompt 顶部
5. update_anchor_image_path(): 首张图生成后自动设为锚点图
"""
from __future__ import annotations

import hashlib
import json as _json
import logging
import random
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Article, ArticleSection, ArticleContent, ArticleVisualAnchor,
)
from app.models.article_image_slot import ArticleImageSlot

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
#  System Prompt for character / style extraction
# ════════════════════════════════════════════════════════════════

_VISUAL_ANCHOR_SYSTEM_PROMPT = """你是医学科普图像导演。请扫描下面这篇文章，抽取需要在多张配图中重复出现的核心视觉元素。

═══ 你的任务 ═══

1. **抽取核心角色**（最多 5 个，按重要度排序）
   - 只抽取文中明确提到或暗示需要画面化的角色（医生、患者、家属、儿童、动画化拟人体等）
   - 给每个角色一份"统一的视觉描述"：年龄、性别、族裔（亚洲）、外貌、服装、配饰、姿态、标志物
   - 不要捏造文中没提的角色
   - 每个角色描述控制在 60-120 字
   - 如果文章是纯讲解型（无具体角色），输出 1 个"叙事者"角色（如"温和讲解员"）

2. **抽取整体风格基调**
   - color_palette：主色调（如"暖橙 + 浅蓝 + 米白"或"冷蓝 + 银灰"）
   - lighting：主光源 + 氛围（如"左上 45° 暖光，柔和阴影"）
   - art_style_extra：补充画风词（如"现代医学扁平插画，圆角设计，无锋利对比"）

═══ 你不能做的事 ═══

- 不能输出 JSON 之外的任何文字
- 不能加血腥、露骨、识别真实人物面孔的描述
- 不能加品牌 logo、药品名称
- 不能编造文中没提到的角色（如文章只讲机制不讲人物，就只输出叙事者）

═══ 输出格式（严格 JSON） ═══

{
  "characters": [
    {
      "id": "A",
      "role": "主治医生",
      "description": "40岁亚洲女性，圆脸短发齐耳，无框眼镜，白大褂内搭浅蓝衬衫，胸前挂听诊器，温和微笑",
      "importance": 5
    },
    {
      "id": "B",
      "role": "老年高血压患者",
      "description": "65岁男性，灰白头发，黑框眼镜，深蓝色毛衣，手持就诊单",
      "importance": 4
    }
  ],
  "style_lock": {
    "color_palette": "暖橙 + 浅蓝 + 米白",
    "lighting": "左上 45° 暖光，柔和阴影",
    "art_style_extra": "现代医学扁平插画，圆角设计，无锋利对比"
  }
}

importance 取 1-5，5 最重要。最多 5 个角色，最少 1 个。"""


# 进程内缓存：1h 内同文章不重复抽取
_EXTRACT_CACHE: dict[str, tuple[float, dict]] = {}
_EXTRACT_TTL_SEC = 60 * 60


def _hash_article_content(article_id: int, plain_text: str) -> str:
    return hashlib.sha256(
        f"{article_id}||{plain_text[:5000]}".encode("utf-8")
    ).hexdigest()


def _cache_get(key: str) -> dict | None:
    entry = _EXTRACT_CACHE.get(key)
    if not entry:
        return None
    expire_at, value = entry
    if expire_at < time.time():
        _EXTRACT_CACHE.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: dict) -> None:
    if len(_EXTRACT_CACHE) >= 200:
        # 清掉一半最早的
        oldest = sorted(_EXTRACT_CACHE.items(), key=lambda kv: kv[1][0])[:100]
        for k, _ in oldest:
            _EXTRACT_CACHE.pop(k, None)
    _EXTRACT_CACHE[key] = (time.time() + _EXTRACT_TTL_SEC, value)


# ════════════════════════════════════════════════════════════════
#  全文聚合
# ════════════════════════════════════════════════════════════════


async def _gather_article_text(article_id: int, db: AsyncSession) -> tuple[str, str]:
    """聚合一篇文章的所有章节正文为纯文本。返回 (topic, full_text)。"""
    art = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()
    if not art:
        return "", ""

    sections = (
        (
            await db.execute(
                select(ArticleSection)
                .where(ArticleSection.article_id == article_id)
                .order_by(ArticleSection.order_num)
            )
        )
        .scalars()
        .all()
    )

    section_ids = [s.id for s in sections]
    contents = (
        (
            await db.execute(
                select(ArticleContent).where(ArticleContent.section_id.in_(section_ids))
            )
        )
        .scalars()
        .all()
    )
    content_by_sec: dict[int, ArticleContent] = {c.section_id: c for c in contents}

    parts: list[str] = []
    if art.topic:
        parts.append(f"主题：{art.topic}")
    for s in sections:
        c = content_by_sec.get(s.id)
        if not c:
            continue
        plain = (c.content_text or "").strip()
        if not plain:
            # 兜底：从 content_json 抽
            try:
                if c.content_json:
                    plain = _strip_json_to_plain(c.content_json)
            except Exception:
                plain = ""
        if plain:
            title = s.title or s.section_type or ""
            parts.append(f"\n## {title}\n{plain[:1500]}")

    return art.topic or "", "\n".join(parts)


def _strip_json_to_plain(content_json: Any) -> str:
    """从 TipTap JSON 中粗暴抽取所有 text 节点。"""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text" and isinstance(node.get("text"), str):
                out.append(node["text"])
            for child in node.get("content") or []:
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(content_json)
    return " ".join(out).strip()


# ════════════════════════════════════════════════════════════════
#  LLM 抽取
# ════════════════════════════════════════════════════════════════


async def extract_visual_anchor_for_article(
    article_id: int, db: AsyncSession, *, force: bool = False
) -> dict:
    """LLM 扫描全文，抽取核心角色 + 风格基调。

    Args:
        article_id: 文章 ID
        db: AsyncSession
        force: 强制重抽（绕过缓存）

    Returns:
        {
            "status": "ok" | "error",
            "characters": [...],
            "style_lock": {...},
            "from_cache": bool,
            "reason": str | None,
        }
    """
    topic, full_text = await _gather_article_text(article_id, db)

    # 阈值放宽：参赛科普图文每节常 < 200 字、整篇也常 < 1000 字。
    # < 30 字则不调用 LLM（基本是空文章），但仍允许"无文本兜底" —— 用主题作锚。
    has_topic = bool((topic or "").strip())
    text_len = len((full_text or "").strip())
    if text_len < 30:
        if has_topic:
            # 兜底：仅靠主题让 LLM 推断一个温和的"叙事者"角色
            full_text = f"{topic}\n（正文尚未生成，按主题推断默认叙事者与风格基调即可。）"
        else:
            return {
                "status": "error",
                "reason": "文章主题与正文均为空，请先输入主题或生成至少一节正文",
                "characters": [],
                "style_lock": {},
                "from_cache": False,
            }

    cache_key = _hash_article_content(article_id, full_text)
    if not force:
        cached = _cache_get(cache_key)
        if cached:
            result = dict(cached)
            result["from_cache"] = True
            return result

    user_msg = f"<topic>{topic[:200]}</topic>\n<article>{full_text[:8000]}</article>"

    try:
        from app.services.llm.openai_client import chat_completion
        from app.services.llm.manager import TaskTier

        raw = await chat_completion(
            messages=[
                {"role": "system", "content": _VISUAL_ANCHOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            task=TaskTier.BALANCED,
            temperature=0.6,
            _log_task_type="contest_visual_anchor_extract",
        )

        text = (raw if isinstance(raw, str) else "").strip()
        if text.startswith("```"):
            lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = _json.loads(text)
        except Exception:
            return {
                "status": "error",
                "reason": "LLM 返回格式无法解析，请手动配置角色",
                "characters": [],
                "style_lock": {},
                "from_cache": False,
            }

        characters = _normalize_characters(data.get("characters") or [])
        style_lock = _normalize_style_lock(data.get("style_lock") or {})

        result = {
            "status": "ok",
            "characters": characters,
            "style_lock": style_lock,
            "from_cache": False,
        }
        _cache_put(cache_key, result)
        return result

    except Exception as e:
        logger.error("visual anchor extract failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "reason": f"抽取失败：{e}",
            "characters": [],
            "style_lock": {},
            "from_cache": False,
        }


# ════════════════════════════════════════════════════════════════
#  Vision 抽取（看图识人）
# ════════════════════════════════════════════════════════════════

_VISUAL_ANCHOR_VISION_SYSTEM_PROMPT = """你是医学科普图像设计师。请仔细观察这张配图，识别图中"需要在后续配图中重复出现"的核心人物，并提取整体画面风格基调。

═══ 你的任务 ═══

1. **识别图中所有清晰可见的人物角色**（最多 5 个，按视觉显眼度 / 戏份排序）
   - 给每个角色一份"统一视觉描述"，让其他生图模型可以复刻同一形象
   - 描述要素：年龄段、性别、族裔（亚洲/欧美/混合等）、外貌（脸型/发型/发色/肤色）、服装（颜色 + 款式）、配饰（眼镜/听诊器/工牌等）、姿态、标志物
   - 每个角色 60-150 字，纯中文描述
   - 不要描述真实人脸细节（不输出"长得像 XX"），只描述显著外观特征
   - 如果图里没有人物（比如是机制图、数据图），输出 1 个"叙事者"角色（如"温和讲解员"）

2. **抽取整体风格基调**（Visual Style）
   - color_palette：主色调（如"暖橙 + 浅蓝 + 米白"或"冷蓝 + 银灰渐变"）
   - lighting：主光源 + 氛围（如"左上 45° 暖光，柔和阴影"或"环境光均匀，无强对比"）
   - art_style_extra：补充画风词（如"现代医学扁平插画，圆角设计"或"水彩晕染 + 工笔线条"）

═══ 你不能做的事 ═══

- 不能输出 JSON 之外的任何文字
- 不能描述血腥、伤口特写、暴露身体、可识别的真人面孔
- 不能识别图中的真实品牌 logo、药品名称
- 不能生成超过 5 个角色

═══ 输出格式（严格 JSON） ═══

{
  "characters": [
    {
      "id": "A",
      "role": "主治医生",
      "description": "40 岁亚洲女性，圆脸短发齐耳，无框眼镜，白大褂内搭浅蓝衬衫，胸前挂听诊器，温和微笑，身姿挺拔",
      "importance": 5
    }
  ],
  "style_lock": {
    "color_palette": "暖橙 + 浅蓝 + 米白",
    "lighting": "左上 45° 暖光，柔和阴影",
    "art_style_extra": "现代医学扁平插画，圆角设计，无锋利对比"
  }
}

importance 取 1-5，5 最重要。"""


async def _resolve_anchor_image_for_article(
    article_id: int, db: AsyncSession, image_path_override: str | None = None
) -> str | None:
    """决定用哪张图来 vision 抽取。

    优先级：
    1. 调用方显式传入 image_path_override
    2. anchor.anchor_image_path（已固化的锚点图）
    3. 文章内任意一张已生成的 ArticleImageSlot.image_path（按 order_num 取首张）
    """
    if image_path_override and image_path_override.strip():
        return image_path_override.strip()

    res = await db.execute(
        select(ArticleVisualAnchor).where(ArticleVisualAnchor.article_id == article_id)
    )
    anchor = res.scalar_one_or_none()
    if anchor and (anchor.anchor_image_path or "").strip():
        return anchor.anchor_image_path.strip()

    # 找文章内最早一张已生成的图
    rows = (
        await db.execute(
            select(ArticleImageSlot, ArticleSection.order_num)
            .join(ArticleSection, ArticleSection.id == ArticleImageSlot.section_id, isouter=True)
            .where(
                ArticleImageSlot.article_id == article_id,
                ArticleImageSlot.image_path.isnot(None),
            )
            .order_by(ArticleSection.order_num.asc().nullslast(), ArticleImageSlot.id.asc())
        )
    ).all()
    for slot, _order in rows:
        if slot.image_path and slot.image_path.strip():
            return slot.image_path.strip()
    return None


def _image_path_to_data_uri(image_path: str) -> str | None:
    """把 image_path（绝对/相对/medcomm-image://）转成 base64 data URI。

    复用 export.html_docx 的解析逻辑，避免重复实现。
    """
    try:
        from app.services.export.html_docx import image_to_data_uri
        return image_to_data_uri(image_path)
    except Exception as e:
        logger.warning("image_to_data_uri failed for %s: %s", image_path, e)
        return None


async def extract_visual_anchor_from_image(
    article_id: int,
    db: AsyncSession,
    *,
    image_path: str | None = None,
) -> dict:
    """用 GPT-4o（或同等 vision LLM）从一张已生成的图片识别角色 + 风格。

    返回结构与 extract_visual_anchor_for_article 一致：
        {
            "status": "ok" | "error",
            "characters": [...],
            "style_lock": {...},
            "from_cache": False,
            "image_path": str,
            "reason": str | None,
        }
    Vision 路径不走文本缓存。
    """
    resolved_path = await _resolve_anchor_image_for_article(
        article_id, db, image_path_override=image_path
    )
    if not resolved_path:
        return {
            "status": "error",
            "reason": "文章尚无任何已生成图片，请先在「全章配图概览」生成至少一张配图",
            "characters": [],
            "style_lock": {},
            "from_cache": False,
            "image_path": None,
        }

    data_uri = _image_path_to_data_uri(resolved_path)
    if not data_uri:
        return {
            "status": "error",
            "reason": f"无法读取图片：{resolved_path}",
            "characters": [],
            "style_lock": {},
            "from_cache": False,
            "image_path": resolved_path,
        }

    # vision 调用必须使用支持图像输入的模型
    # 优先 gpt-4o（QUALITY 路由会落到这一档），失败则报错
    try:
        from app.services.llm.openai_client import chat_completion
        from app.services.llm.manager import TaskTier

        topic = ""
        try:
            art = (
                await db.execute(select(Article).where(Article.id == article_id))
            ).scalar_one_or_none()
            topic = (art.topic or "") if art else ""
        except Exception:
            topic = ""

        text_part = (
            f"<topic>{topic[:200]}</topic>\n"
            "请按 system 指令观察这张配图，输出严格 JSON。"
        )

        messages = [
            {"role": "system", "content": _VISUAL_ANCHOR_VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_part},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ]

        raw = await chat_completion(
            messages=messages,
            task=TaskTier.QUALITY,  # gpt-4o / gpt-4.1 等支持 vision
            temperature=0.5,
            _log_task_type="contest_visual_anchor_extract_vision",
        )

        text = (raw if isinstance(raw, str) else "").strip()
        if text.startswith("```"):
            lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = _json.loads(text)
        except Exception:
            return {
                "status": "error",
                "reason": "Vision LLM 返回格式无法解析，请手动配置角色或换张图重试",
                "characters": [],
                "style_lock": {},
                "from_cache": False,
                "image_path": resolved_path,
            }

        characters = _normalize_characters(data.get("characters") or [])
        style_lock = _normalize_style_lock(data.get("style_lock") or {})

        return {
            "status": "ok",
            "characters": characters,
            "style_lock": style_lock,
            "from_cache": False,
            "image_path": resolved_path,
        }

    except Exception as e:
        logger.error("visual anchor vision extract failed: %s", e, exc_info=True)
        msg = str(e)
        # 给前端一个更友好的解释
        if "vision" in msg.lower() or "image" in msg.lower() or "multimodal" in msg.lower():
            reason = "当前模型不支持图像输入，请确认已配置 gpt-4o 等 vision 模型的 API Key"
        else:
            reason = f"vision 抽取失败：{msg}"
        return {
            "status": "error",
            "reason": reason,
            "characters": [],
            "style_lock": {},
            "from_cache": False,
            "image_path": resolved_path,
        }


# ════════════════════════════════════════════════════════════════
#  共用：解析 / 归一化
# ════════════════════════════════════════════════════════════════


def _normalize_characters(characters_raw: Any) -> list[dict]:
    """把 LLM 返回的 characters 数组归一化成内部格式。"""
    if not isinstance(characters_raw, list):
        return []
    out: list[dict] = []
    for idx, ch in enumerate(characters_raw[:5]):
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or chr(ord("A") + idx))[:4]
        role = str(ch.get("role") or "").strip()[:30]
        desc = str(ch.get("description") or "").strip()
        if len(desc) > 200:
            desc = desc[:200].rstrip() + "…"
        try:
            imp = int(ch.get("importance") or (5 - idx))
        except Exception:
            imp = 5 - idx
        imp = max(1, min(5, imp))
        if not role or not desc:
            continue
        out.append({"id": cid, "role": role, "description": desc, "importance": imp})
    return out


def _normalize_style_lock(style_raw: Any) -> dict:
    if not isinstance(style_raw, dict):
        return {"color_palette": "", "lighting": "", "art_style_extra": ""}
    return {
        "color_palette": str(style_raw.get("color_palette", ""))[:80],
        "lighting": str(style_raw.get("lighting", ""))[:80],
        "art_style_extra": str(style_raw.get("art_style_extra", ""))[:120],
    }


def merge_characters(
    existing: list[dict] | None,
    new_chars: list[dict],
    *,
    mode: str = "replace",
) -> list[dict]:
    """合并新旧角色卡。

    mode='replace'：直接用新角色覆盖
    mode='append' ：在原有角色后追加，按 role 去重；总数 ≤ 5；id 自动重新分配 A~E
    """
    if mode != "append":
        return new_chars[:5]
    base = list(existing or [])
    used_roles = {(c.get("role") or "").strip() for c in base}
    for ch in new_chars:
        if len(base) >= 5:
            break
        role = (ch.get("role") or "").strip()
        if not role or role in used_roles:
            continue
        base.append({**ch})
        used_roles.add(role)
    # 重新分配 id A~E，保持 description 与 importance
    out: list[dict] = []
    for idx, ch in enumerate(base[:5]):
        out.append(
            {
                "id": chr(ord("A") + idx),
                "role": ch.get("role") or "",
                "description": ch.get("description") or "",
                "importance": ch.get("importance") or (5 - idx),
            }
        )
    return out


# ════════════════════════════════════════════════════════════════
#  锚点 CRUD
# ════════════════════════════════════════════════════════════════


def _generate_seed() -> int:
    """生成一个 0~2^31-1 范围内的种子（多数 provider 接受 32-bit 整数）。"""
    return random.randint(1, 2_147_483_647)


async def get_or_create_anchor(
    article_id: int, db: AsyncSession
) -> ArticleVisualAnchor:
    """获取或创建文章的视觉锚点（不自动抽取）。"""
    res = await db.execute(
        select(ArticleVisualAnchor).where(
            ArticleVisualAnchor.article_id == article_id
        )
    )
    anchor = res.scalar_one_or_none()
    if anchor:
        return anchor

    anchor = ArticleVisualAnchor(
        article_id=article_id,
        characters=[],
        style_lock={},
        base_seed=_generate_seed(),
        anchor_image_path=None,
        anchor_source="auto_first",
        last_modified_by=None,
    )
    db.add(anchor)
    await db.commit()
    await db.refresh(anchor)
    return anchor


async def update_anchor_image_path(
    article_id: int,
    image_path: str,
    db: AsyncSession,
    *,
    only_if_empty: bool = True,
) -> None:
    """生图成功后调用，把首图设为锚点图（仅当 anchor_source=auto_first 且当前为空）。"""
    res = await db.execute(
        select(ArticleVisualAnchor).where(
            ArticleVisualAnchor.article_id == article_id
        )
    )
    anchor = res.scalar_one_or_none()
    if not anchor:
        return
    if (anchor.anchor_source or "auto_first") != "auto_first":
        return
    if only_if_empty and anchor.anchor_image_path:
        return
    anchor.anchor_image_path = image_path
    await db.commit()


# ════════════════════════════════════════════════════════════════
#  Prompt 注入
# ════════════════════════════════════════════════════════════════


def _format_characters_block(characters: list[dict]) -> str:
    if not characters:
        return ""
    lines = []
    for ch in sorted(characters, key=lambda x: -int(x.get("importance") or 0)):
        cid = ch.get("id") or "?"
        role = ch.get("role") or ""
        desc = ch.get("description") or ""
        if not desc:
            continue
        lines.append(f"  · {cid} 「{role}」: {desc}")
    if not lines:
        return ""
    return "【角色一致性 · 全文统一外貌】\n" + "\n".join(lines)


def _format_style_block(style_lock: dict) -> str:
    if not style_lock:
        return ""
    parts = []
    if style_lock.get("color_palette"):
        parts.append(f"  · 配色：{style_lock['color_palette']}")
    if style_lock.get("lighting"):
        parts.append(f"  · 光影：{style_lock['lighting']}")
    if style_lock.get("art_style_extra"):
        parts.append(f"  · 画风：{style_lock['art_style_extra']}")
    if not parts:
        return ""
    return "【风格锁 · 全文统一画面基调】\n" + "\n".join(parts)


def inject_anchor_to_intent(
    intent_text: str,
    anchor: ArticleVisualAnchor | None,
) -> str:
    """把视觉锚点（角色卡 + 风格锁）拼到画意前面，作为 prompt 的统一前缀。

    返回的 intent_text 会被传给 generate_dual_prompt，让最终 prompt 自带角色描述。
    如果 anchor 为空或无内容，返回原 intent_text。
    """
    if not anchor:
        return intent_text
    chars_block = _format_characters_block(anchor.characters or [])
    style_block = _format_style_block(anchor.style_lock or {})
    blocks = [b for b in (chars_block, style_block) if b]
    if not blocks:
        return intent_text
    prefix = "\n\n".join(blocks)
    return f"{prefix}\n\n【本节画面】\n{intent_text}"


def anchor_to_dict(anchor: ArticleVisualAnchor | None) -> dict | None:
    if not anchor:
        return None
    return {
        "id": anchor.id,
        "article_id": anchor.article_id,
        "characters": anchor.characters or [],
        "style_lock": anchor.style_lock or {},
        "base_seed": anchor.base_seed,
        "anchor_image_path": anchor.anchor_image_path,
        "anchor_source": anchor.anchor_source or "auto_first",
        "auto_extracted_at": anchor.auto_extracted_at.isoformat() if anchor.auto_extracted_at else None,
        "last_modified_by": anchor.last_modified_by,
        # ⚠ 注意：判断 "已配置" 必须看 value 是否非空，
        # 不能直接 bool(style_lock) — 因为 {"color_palette":"","lighting":"","art_style_extra":""}
        # 这种"key 在但 value 全空"的字典 bool 为 True，会让"已清除"看起来仍是"已配置"。
        "is_configured": has_meaningful_anchor(anchor),
    }


def has_meaningful_anchor(anchor: ArticleVisualAnchor | None) -> bool:
    """判断锚点是否真的有内容（非空 characters 或 style_lock）。"""
    if not anchor:
        return False
    if anchor.characters:
        return True
    style = anchor.style_lock or {}
    return any(style.get(k) for k in ("color_palette", "lighting", "art_style_extra"))

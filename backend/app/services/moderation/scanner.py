"""
内容审核扫描器 — 三层审核（入口/生成后/导出）
每层均过三级敏感词，按最高命中级别决定动作。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.moderation.wordlists import load_custom_wordlists

logger = logging.getLogger(__name__)

LEVEL_BLOCK = "block"
LEVEL_WARN = "warn"
LEVEL_INFO = "info"

Stage = Literal["input", "generation", "export"]


@dataclass
class MatchedItem:
    word: str
    level: str          # block / warn / info
    snippet: str        # 命中上下文片段（脱敏截断）
    rule_name: str      # 规则分类名


@dataclass
class ScanResult:
    passed: bool = True
    highest_level: str = LEVEL_INFO
    matches: list[MatchedItem] = field(default_factory=list)
    action: str = "pass"  # pass / blocked / passed_with_warning
    message: str = ""

    @property
    def has_block(self) -> bool:
        return any(m.level == LEVEL_BLOCK for m in self.matches)

    @property
    def has_warn(self) -> bool:
        return any(m.level == LEVEL_WARN for m in self.matches)


def _extract_snippet(text: str, word: str, context_chars: int = 30) -> str:
    """提取命中词周围的上下文片段（脱敏用）"""
    idx = text.find(word)
    if idx == -1:
        return word
    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(word) + context_chars)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def scan_text(text: str) -> ScanResult:
    """扫描文本，返回三级敏感词命中结果"""
    if not text or not text.strip():
        return ScanResult()

    block_words, warn_words, info_words = load_custom_wordlists()
    result = ScanResult()
    text_lower = text.lower()

    for word in block_words:
        if word.lower() in text_lower:
            result.matches.append(MatchedItem(
                word=word,
                level=LEVEL_BLOCK,
                snippet=_extract_snippet(text, word),
                rule_name="绝对禁止",
            ))

    for word in warn_words:
        if word.lower() in text_lower:
            result.matches.append(MatchedItem(
                word=word,
                level=LEVEL_WARN,
                snippet=_extract_snippet(text, word),
                rule_name="医疗高敏",
            ))

    for word in info_words:
        if word.lower() in text_lower:
            result.matches.append(MatchedItem(
                word=word,
                level=LEVEL_INFO,
                snippet=_extract_snippet(text, word),
                rule_name="平台风控",
            ))

    if not result.matches:
        return result

    if result.has_block:
        result.passed = False
        result.highest_level = LEVEL_BLOCK
        result.action = "blocked"
        result.message = f"内容包含 {len([m for m in result.matches if m.level == LEVEL_BLOCK])} 处违禁内容，已阻断"
    elif result.has_warn:
        result.passed = True
        result.highest_level = LEVEL_WARN
        result.action = "passed_with_warning"
        result.message = f"内容包含 {len([m for m in result.matches if m.level == LEVEL_WARN])} 处医疗高敏内容，请确认免责声明"
    else:
        result.passed = True
        result.highest_level = LEVEL_INFO
        result.action = "pass"
        result.message = f"检测到 {len(result.matches)} 处风控提示"

    return result


async def _log_moderation(
    db: AsyncSession,
    user_id: int,
    stage: Stage,
    scan_result: ScanResult,
    article_id: int | None = None,
    section_id: int | None = None,
) -> None:
    """将审核结果写入 content_moderation_logs"""
    if not scan_result.matches:
        return
    try:
        from app.models.billing import ContentModerationLog
        for match in scan_result.matches:
            db.add(ContentModerationLog(
                user_id=user_id,
                article_id=article_id,
                section_id=section_id,
                stage=stage,
                rule_level=match.level,
                matched_rule=match.rule_name,
                snippet=match.snippet[:500],
                action_taken=scan_result.action,
                meta={"word": match.word},
            ))
        await db.commit()
    except Exception as exc:
        logger.error("审核日志写入失败: %s", exc)
        try:
            await db.rollback()
        except Exception:
            pass

    if scan_result.has_block:
        try:
            from app.services.observability import send_alert
            await send_alert("content_moderation_block", {
                "user_id": user_id,
                "article_id": article_id,
                "stage": stage,
                "blocked_words": [m.word for m in scan_result.matches if m.level == LEVEL_BLOCK],
            })
        except Exception:
            pass


async def scan_input(
    text: str,
    user_id: int,
    db: AsyncSession,
    article_id: int | None = None,
) -> ScanResult:
    """
    入口审核：扫描用户输入的主题/受众描述/PDF文件名等。
    命中 block 级别时抛出异常阻断生成。
    """
    result = scan_text(text)
    if result.matches:
        await _log_moderation(db, user_id, "input", result, article_id=article_id)
    return result


async def scan_generation_output(
    text: str,
    user_id: int,
    db: AsyncSession,
    article_id: int | None = None,
    section_id: int | None = None,
) -> ScanResult:
    """
    生成中审核：LLM 输出后扫描全文。
    命中时标记内容，提示用户人工审阅，但不阻断保存。
    """
    result = scan_text(text)
    if result.matches:
        if result.has_block:
            result.action = "passed_with_warning"
            result.message = "生成内容包含敏感词，已标记待人工审阅"
        await _log_moderation(db, user_id, "generation", result,
                              article_id=article_id, section_id=section_id)
    return result


async def scan_export(
    text: str,
    user_id: int,
    db: AsyncSession,
    article_id: int | None = None,
) -> ScanResult:
    """
    出口审核：导出/分享前二次扫描。
    命中 block 或 warn 级别内容时阻断导出。
    """
    result = scan_text(text)
    if result.matches:
        if result.has_block or result.has_warn:
            result.passed = False
            result.action = "blocked"
            block_count = len([m for m in result.matches if m.level in (LEVEL_BLOCK, LEVEL_WARN)])
            result.message = f"导出被阻断：内容包含 {block_count} 处高敏/违禁内容，请修改后再导出"
        await _log_moderation(db, user_id, "export", result, article_id=article_id)
    return result

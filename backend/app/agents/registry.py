"""
Agent 注册表 - 按 content_format + section_type 路由到形式族 Agent 或 FormatAgent
"""
from typing import Optional

from app.agents.base import BaseAgent
from app.agents.medcomm.format_agent import FormatAgent
from app.agents.comic.comic_agent import ComicPanelWriter
from app.agents.card.card_agent import CardSeriesWriter
from app.agents.poster.poster_agent import PosterWriter
from app.agents.picture_book.picture_book_agent import PictureBookWriter
from app.agents.long_image.long_image_agent import LongImageWriter
from app.agents.oral_script.oral_script_agent import OralScriptWriter
from app.agents.drama.drama_agent import DramaScriptWriter
from app.agents.storyboard.storyboard_agent import StoryboardWriter
from app.agents.handbook.handbook_agent import HandbookSectionAgent
FORMAT_AGENT_MAP = {
    "debunk": FormatAgent,
    "oral_script": OralScriptWriter,
    "drama_script": DramaScriptWriter,
    "comic_strip": ComicPanelWriter,
    "card_series": CardSeriesWriter,
    "poster": PosterWriter,
    "picture_book": PictureBookWriter,
    "long_image": LongImageWriter,
    "storyboard": StoryboardWriter,
    "patient_handbook": HandbookSectionAgent,
}

# 形式 → 是否跳过医学声明核实 / 阅读难度（v2.1：补全 long_image、h5_outline）
# 竖版长图/H5大纲：文案极简+配图描述英文或配合交互，两种验证均不适用
SKIP_VERIFY_FORMATS = {"comic_strip", "card_series", "poster", "picture_book", "storyboard", "long_image", "h5_outline", "oral_script", "drama_script"}
SKIP_LEVEL_FORMATS = {
    "oral_script", "drama_script", "storyboard", "audio_script",
    "comic_strip", "card_series", "poster", "h5_outline", "long_image",
}

# ── 去 AI 化改写与 AIGC 检测 — 独立维度的开关 ────────────────────
# 历史上"是否做去 AI 改写"和"是否做 AI 痕迹检测"被 piggyback 到 SKIP_LEVEL_FORMATS
# 上，把"阅读难度检查""verification""AIGC 检测""deai 改写"四件事绑成一个 if/else。
# 现在解耦：每件事一个独立开关，按形式特性精准控制。
#
# 设计原则：
#  - 脚本类（oral/drama/audio/storyboard）的 dialogue 是纯字符串台词，AI 味最重，
#    既要做检测也要做改写
#  - 图示类（comic/card/poster/long_image）文案极短、与画面绑定，做检测但不做改写
#  - 大纲类（h5_outline）是结构骨架，两者都不做

# 不参与去 AI 化改写的形式（文案与画面强绑定 / 大纲性质 / 多字段 JSON 改写易破坏结构）
SKIP_DEAI_REWRITE_FORMATS = {
    "comic_strip", "card_series", "poster", "long_image", "h5_outline",
}

# 不做 AIGC 痕迹检测的形式（仅 h5 大纲性质，无成文文本可检）
SKIP_AI_DETECTION_FORMATS = {
    "h5_outline",
}


def get_agent_for_section(content_format: str, section_type: str) -> BaseAgent:
    """根据形式与章节类型返回 Agent"""
    agent_cls = FORMAT_AGENT_MAP.get(content_format)
    if agent_cls:
        if agent_cls is FormatAgent:
            return FormatAgent(content_format, section_type or "intro")
        return agent_cls(section_type or "intro")
    return FormatAgent(content_format, section_type or "intro")


def get_skip_flags(content_format: str) -> tuple[bool, bool]:
    """返回 (skip_verify, skip_level)"""
    return (
        content_format in SKIP_VERIFY_FORMATS,
        content_format in SKIP_LEVEL_FORMATS,
    )


def should_run_deai_rewrite(content_format: str) -> bool:
    """是否对该形式执行去 AI 化改写。"""
    return content_format not in SKIP_DEAI_REWRITE_FORMATS


def should_detect_ai_patterns(content_format: str) -> bool:
    """是否对该形式跑 AIGC 痕迹检测（detect_ai_patterns）。"""
    return content_format not in SKIP_AI_DETECTION_FORMATS

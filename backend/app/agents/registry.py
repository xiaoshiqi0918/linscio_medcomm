"""
Agent 注册表 - 按 content_format + section_type 路由到形式族 Agent 或 FormatAgent
"""
from typing import Optional

from app.agents.base import BaseAgent
from app.agents.medcomm.format_agent import FormatAgent
from app.agents.comic.comic_agent import ComicPanelWriter
from app.agents.handbook.handbook_agent import HandbookSectionAgent
# 形式族 → Agent 类（debunk 改用 FormatAgent 以使用 task_prompts 详细提示词）
FORMAT_AGENT_MAP = {
    "debunk": FormatAgent,
    "oral_script": FormatAgent,
    "drama_script": FormatAgent,  # 情景剧用 FormatAgent + drama_script prompts
    "comic_strip": ComicPanelWriter,
    "patient_handbook": HandbookSectionAgent,
}

# 形式 → 是否跳过医学声明核实 / 阅读难度（v2.1：补全 long_image、h5_outline）
# 竖版长图/H5大纲：文案极简+配图描述英文或配合交互，两种验证均不适用
SKIP_VERIFY_FORMATS = {"comic_strip", "card_series", "poster", "picture_book", "storyboard", "long_image", "h5_outline"}
SKIP_LEVEL_FORMATS = {
    "oral_script", "drama_script", "storyboard", "audio_script",
    "comic_strip", "card_series", "poster", "h5_outline", "long_image",
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

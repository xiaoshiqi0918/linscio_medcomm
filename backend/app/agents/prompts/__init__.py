"""
LinScio MedComm 提示词体系
Layer 0: 系统级 | Layer 1: 防编造 | Layer 2: 增强注入 | Layer 3: 任务提示词

Layer 0/1 优先从 prompt-example/prompts/ 加载（作为同步代码层的基础）
"""
from app.agents.prompts.system import MEDCOMM_SYSTEM_PROMPT
from app.agents.prompts.anti_hallucination import MEDCOMM_ANTI_HALLUCINATION, get_format_specific_rules
from app.agents.prompts.audiences import AUDIENCE_PROFILES, CHILDREN_AUDIENCE_PATCH
from app.agents.prompts.format_section import FORMAT_SECTION_PROMPTS, DEFAULT_PROMPT
from app.agents.prompts.loader import PROMPT_VERSIONS, load_writing_sop

MEDCOMM_WRITING_SOP = load_writing_sop() or ""

__all__ = [
    "MEDCOMM_SYSTEM_PROMPT",
    "MEDCOMM_ANTI_HALLUCINATION",
    "MEDCOMM_WRITING_SOP",
    "AUDIENCE_PROFILES",
    "CHILDREN_AUDIENCE_PATCH",
    "get_format_specific_rules",
    "FORMAT_SECTION_PROMPTS",
    "DEFAULT_PROMPT",
    "PROMPT_VERSIONS",
]

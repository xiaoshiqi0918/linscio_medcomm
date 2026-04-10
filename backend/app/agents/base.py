"""
BaseAgent - 所有形式 Agent 的基类
四层 Prompt 架构：Layer 0-1 (System) → Part 1 (能力增强) → Part 2 (事实来源) → Part 3 (任务)
"""
from abc import ABC, abstractmethod
from app.services.enhancement.prompt_builder import build_enhanced_prompt
from app.services.verification.pipeline import run_verification
from app.agents.prompts import (
    MEDCOMM_SYSTEM_PROMPT,
    CHILDREN_AUDIENCE_PATCH,
)
from app.agents.prompts.anti_hallucination import get_format_specific_rules


def _build_system_prompt(content_format: str = "") -> str:
    """System message = 精简「宪法层」+ 形式族专属规则。
    所有核心规则（事实溯源、证据语言、安全红线、输出格式）已内置于 MEDCOMM_SYSTEM_PROMPT，
    17 条规则 ~800 token，每条均为可执行判断标准。"""
    format_rules = get_format_specific_rules(content_format)
    parts = [MEDCOMM_SYSTEM_PROMPT]
    if format_rules:
        parts.append(format_rules)
    return "\n\n".join(parts)


class BaseAgent(ABC):
    """BaseAgent - 子类只需实现 get_base_prompt()"""

    module: str = "base"

    @abstractmethod
    def get_base_prompt(self, state: dict) -> str:
        """返回该 Agent 的基础提示词"""
        pass

    async def run(
        self,
        state: dict,
        rag_context: list | None = None,
        skip_verify: bool = False,
        skip_level: bool = False,
    ) -> tuple[str, dict]:
        """
        执行生成：三层增强 → LLM 调用 → 防编造验证
        返回 (content, verify_report)
        """
        from app.services.llm.openai_client import chat_completion
        from app.services.llm.manager import resolve_model_for_task, TaskTier

        base_prompt = self.get_base_prompt(state)
        if state.get("target_audience") == "children":
            base_prompt = CHILDREN_AUDIENCE_PATCH + "\n\n" + base_prompt
        enhanced_prompt, _ = await build_enhanced_prompt(
            base_prompt=base_prompt,
            topic=state.get("topic", ""),
            section_type=state.get("section_type", ""),
            content_format=state.get("content_format", "article"),
            target_audience=state.get("target_audience", "public"),
            platform=state.get("platform", "wechat"),
            specialty=state.get("specialty"),
            article_id=state.get("article_id"),
            rag_context=state.get("rag_context"),
            examples=state.get("examples"),
            domain_terms=state.get("domain_terms"),
            prior_sections_context=state.get("prior_sections_context", ""),
            user_id=state.get("user_id") or 1,
            target_word_count=state.get("target_word_count"),
        )
        model = await resolve_model_for_task(
            task=TaskTier.QUALITY,
            article_id=state.get("article_id"),
            article_default_model=state.get("article_default_model"),
        )
        system_prompt = _build_system_prompt(state.get("content_format", ""))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": enhanced_prompt},
        ]
        content = await chat_completion(messages, model=model, stream=False)
        content = content or "[生成失败，请检查 API Key]"
        content, report = await run_verification(
            content=content,
            article_id=state.get("article_id"),
            rag_context=rag_context or [],
            target_audience=state.get("target_audience", "public"),
            skip_verify=skip_verify,
            skip_level=skip_level,
        )
        return content, report

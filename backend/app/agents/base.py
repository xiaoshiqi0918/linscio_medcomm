"""
BaseAgent - 所有形式 Agent 的基类
继承即获得三层增强（RAG + Few-shot + 术语注入）+ 防编造
"""
from abc import ABC, abstractmethod
from app.services.enhancement.prompt_builder import build_enhanced_prompt
from app.services.verification.pipeline import run_verification
from app.agents.prompts import (
    MEDCOMM_SYSTEM_PROMPT,
    MEDCOMM_ANTI_HALLUCINATION,
    MEDCOMM_WRITING_SOP,
    CHILDREN_AUDIENCE_PATCH,
)
from app.agents.prompts.anti_hallucination import get_format_specific_rules, MEDCOMM_EVIDENCE_LANGUAGE


def _build_system_prompt(content_format: str = "") -> str:
    """Layer 0 + Layer 0.5(SOP) + Layer 1 + 形式族专属规则"""
    format_rules = get_format_specific_rules(content_format)
    parts = [MEDCOMM_SYSTEM_PROMPT]
    if MEDCOMM_WRITING_SOP:
        parts.append(MEDCOMM_WRITING_SOP)
    parts.append(MEDCOMM_ANTI_HALLUCINATION)
    parts.append(MEDCOMM_EVIDENCE_LANGUAGE)
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
        from app.services.llm.manager import resolve_model

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
        )
        model = await resolve_model(
            article_id=state.get("article_id"),
            article_default_model=state.get("article_default_model"),
            model_hint=state.get("model_hint", "default"),
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

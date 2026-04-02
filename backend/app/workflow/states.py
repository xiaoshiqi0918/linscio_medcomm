"""工作流 State 定义"""
from typing import TypedDict, Any


class ImageGenState(TypedDict, total=False):
    scene_desc: str
    prompt: str
    negative_prompt: str
    user_positive_prompt: str
    user_negative_prompt: str
    style: str
    content_format: str
    image_type: str
    specialty: str
    target_audience: str
    width: int
    height: int
    batch_count: int
    seed: int
    steps: int
    cfg_scale: float
    sampler_name: str
    preferred_provider: str
    siliconflow_image_model: str
    comfy_workflow_path: str
    comfy_mode: str
    comfy_base_url: str
    comfy_prompt_node_id: str
    comfy_prompt_input_key: str
    comfy_negative_node_id: str
    comfy_negative_input_key: str
    comfy_ksampler_node_id: str
    urls: list[str]
    is_fallback: bool
    used_seeds: list[int]
    visual_continuity_prompt: str
    seed_base: int
    panel_index: int
    article_id: int
    error: str | None


class MedCommSectionState(TypedDict, total=False):
    user_id: int
    article_id: int
    section_id: int
    section_type: str
    content_format: str
    topic: str
    specialty: str
    target_audience: str
    reading_level: str
    platform: str
    language: str
    format_meta: dict
    generate_mode: str  # new | continue
    model_hint: str
    active_agent: str
    skip_verify: bool
    skip_level: bool

    rag_context: list[dict]
    examples: list[dict]
    domain_terms: list[dict]

    generated_content: str
    verified_content: str
    verify_report: dict[str, Any]
    quality_report: dict[str, Any]
    reading_level_report: dict
    image_suggestions: list[dict]

    retry_count: int
    next: str
    is_complete: bool
    error: str | None

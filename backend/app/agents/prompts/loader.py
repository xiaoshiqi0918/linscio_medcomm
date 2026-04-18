"""
提示词加载器
优先从 prompt-example 文件夹加载，作为同步代码层的基础。

目录约定（prompt-example/prompts/）：
  layer0/     — Layer 0 系统级
  layer1/     — Layer 1 防编造与补丁
  part1/      — Part 1 能力增强（auxiliary、完整 SOP 等）
  part2/      — Part 2 占位说明（运行时动态拼装为主）
  part3/      — Part 3 任务与形式简版（task/、format_section*）
  literature/ — 文献分析 system 提示词
  deai/       — 去 AI 化改写模板
  verification/、imagegen/、comic/、handbook/、polish/ 等 — 支撑模块

兼容：若新路径不存在，自动回退到迁移前的旧路径（根目录同名文件）。
"""
from pathlib import Path
import json

# 项目根目录：backend/app/agents/prompts/loader.py -> ../../../.. -> 项目根（含 prompt-example）
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_PROMPT_EXAMPLE_DIR = _PROJECT_ROOT / "prompt-example"
_PROMPTS_DIR = _PROMPT_EXAMPLE_DIR / "prompts"


def _load_file(path: Path) -> str | None:
    """读取文本文件，失败返回 None"""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None


def _first_available_string(paths: list[Path]) -> str | None:
    """按顺序尝试路径，返回首个成功读取的非空字符串。"""
    for p in paths:
        content = _load_file(p)
        if content:
            return content
    return None


def _first_available_json(paths: list[Path]) -> dict | list | None:
    for p in paths:
        content = _load_file(p)
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
    return None


def _load_json(path: Path) -> dict | list | None:
    content = _load_file(path)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return None


def load_prompt_versions() -> dict:
    """加载 PROMPT_VERSIONS（优先 backend/prompts/PROMPT_VERSIONS.json）"""
    backend_versions = Path(__file__).parent / "PROMPT_VERSIONS.json"
    if backend_versions.exists():
        content = _load_file(backend_versions)
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
    versions_path = _PROMPT_EXAMPLE_DIR / "PROMPT_VERSIONS.json"
    content = _load_file(versions_path)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return {}


def load_layer0_system() -> str | None:
    """Layer 0 系统提示词：prompts/layer0/system.txt（旧：layer0_system.txt）"""
    return _first_available_string(
        [
            _PROMPTS_DIR / "layer0" / "system.txt",
            _PROMPTS_DIR / "layer0_system.txt",
        ]
    )


def load_writing_sop() -> str | None:
    """精简版写作 SOP 核心原则（layer0/writing_sop_core.txt）。"""
    return _first_available_string(
        [
            _PROMPTS_DIR / "layer0" / "writing_sop_core.txt",
            _PROMPTS_DIR / "writing_sop_core.txt",
        ]
    )


def load_full_writing_sop_document() -> str | None:
    """完整版写作 SOP 文本（part1/writing_sop.txt），供人工阅读或未来接入。"""
    return _first_available_string(
        [
            _PROMPTS_DIR / "part1" / "writing_sop.txt",
            _PROMPTS_DIR / "writing_sop.txt",
        ]
    )


def load_layer1_anti_hallucination() -> str | None:
    return _first_available_string(
        [
            _PROMPTS_DIR / "layer1" / "anti_hallucination.txt",
            _PROMPTS_DIR / "layer1_anti_hallucination.txt",
        ]
    )


def load_layer1_visual_anti() -> str | None:
    return _first_available_string(
        [
            _PROMPTS_DIR / "layer1" / "visual_anti.txt",
            _PROMPTS_DIR / "layer1_visual_anti.txt",
        ]
    )


def load_layer1_script_anti() -> str | None:
    return _first_available_string(
        [
            _PROMPTS_DIR / "layer1" / "script_anti.txt",
            _PROMPTS_DIR / "layer1_script_anti.txt",
        ]
    )


def load_children_audience_patch() -> str | None:
    return _first_available_string(
        [
            _PROMPTS_DIR / "layer1" / "children_audience_patch.txt",
            _PROMPTS_DIR / "children_audience_patch.txt",
        ]
    )


def load_verification(name: str) -> str | None:
    """加载验证类提示词：claim_verify, fact_verify, reading_level, suggest_images, analogy_anti_examples"""
    return _load_file(_PROMPTS_DIR / "verification" / f"{name}.txt")


def load_format_section() -> dict | None:
    return _first_available_json(
        [
            _PROMPTS_DIR / "part3" / "format_section.json",
            _PROMPTS_DIR / "format_section.json",
        ]
    )


def load_format_section_default() -> str | None:
    return _first_available_string(
        [
            _PROMPTS_DIR / "part3" / "format_section_default.txt",
            _PROMPTS_DIR / "format_section_default.txt",
        ]
    )


def load_comic(name: str) -> str | None:
    """加载条漫提示词模板（已弃用为基础提示词替换）。返回 None。"""
    return None


def load_comic_guideline(name: str) -> str | None:
    """加载条漫写作规范：prompts/comic/{name}.txt"""
    return _load_file(_PROMPTS_DIR / "comic" / f"{name}.txt")


def load_handbook(name: str) -> str | None:
    """加载患者手册提示词模板（已弃用为基础提示词替换）。返回 None。"""
    return None


def load_handbook_guideline(name: str) -> str | None:
    """加载患者手册写作规范：prompts/handbook/{name}.txt"""
    return _load_file(_PROMPTS_DIR / "handbook" / f"{name}.txt")


def load_polish(name: str) -> str | None:
    """加载润色提示词。

    json_output_system 仍正常加载（系统级指令）；
    language_polish 和 platform_adapt 返回 None，改由 Python fallback 提供完整上下文。
    """
    if name == "json_output_system":
        return _load_file(_PROMPTS_DIR / "polish" / f"{name}.txt")
    return None


def load_convert_prompt(name: str) -> str | None:
    """加载转换相关提示词（已弃用为基础提示词替换）。返回 None。"""
    return None


def load_auxiliary(name: str) -> str | None:
    """加载辅助提示词：part1/auxiliary/{name}.txt（旧：prompts/auxiliary/）"""
    return _first_available_string(
        [
            _PROMPTS_DIR / "part1" / "auxiliary" / f"{name}.txt",
            _PROMPTS_DIR / "auxiliary" / f"{name}.txt",
        ]
    )


def load_imagegen_style_system() -> dict | None:
    """加载 imagegen/style_system.json"""
    return _load_json(_PROMPTS_DIR / "imagegen" / "style_system.json")


def load_imagegen_quality_suffix() -> str | None:
    return _load_file(_PROMPTS_DIR / "imagegen" / "quality_suffix.txt")


def load_imagegen_safety_negative() -> str | None:
    return _load_file(_PROMPTS_DIR / "imagegen" / "safety_negative.txt")


def load_imagegen_type_templates() -> dict | None:
    return _load_json(_PROMPTS_DIR / "imagegen" / "image_type_templates.json")


def load_imagegen_translate_system() -> str | None:
    """加载 imagegen 中译英翻译的 system prompt：imagegen/translate_system.txt"""
    return _load_file(_PROMPTS_DIR / "imagegen" / "translate_system.txt")


def load_task(name: str) -> str | None:
    """加载任务提示词模板（已弃用为基础提示词替换）。

    外部 .txt 模板现在仅通过 load_task_guideline() 作为写作规范参考
    注入增强层，不再替换 Python 代码中的基础提示词。返回 None
    使所有 task_prompts.py 函数始终走包含完整上下文注入的 fallback 路径。
    """
    return None


def load_task_guideline(name: str) -> str | None:
    """外部写作规范模板：part3/task/{name}.txt（旧：prompts/task/）。"""
    return _first_available_string(
        [
            _PROMPTS_DIR / "part3" / "task" / f"{name}.txt",
            _PROMPTS_DIR / "task" / f"{name}.txt",
        ]
    )


def load_platform_config() -> dict | None:
    return _first_available_json(
        [
            _PROMPTS_DIR / "part3" / "task" / "platform_config.json",
            _PROMPTS_DIR / "task" / "platform_config.json",
        ]
    )


# ── 文献分析（runtime 优先读文件，见 literature/analyzer.py 回退常量）──


def load_literature_analysis_single() -> str | None:
    """1–2 篇文献单次分析的 system prompt。"""
    return _load_file(_PROMPTS_DIR / "literature" / "analysis_single.txt")


def load_literature_per_paper() -> str | None:
    """MapReduce 单篇精读的 system prompt。"""
    return _load_file(_PROMPTS_DIR / "literature" / "per_paper.txt")


def load_literature_synthesis() -> str | None:
    """MapReduce 综合汇总的 system prompt。"""
    return _load_file(_PROMPTS_DIR / "literature" / "synthesis.txt")


# ── 去 AI 化改写 ──


def load_deai_system_override() -> str | None:
    """若文件非空，整段作为 system，替代动态 `_build_deai_system_prompt`。"""
    t = _load_file(_PROMPTS_DIR / "deai" / "system_override.txt")
    return t if t else None


def load_deai_rewrite_full_template() -> str | None:
    """全文改写 user 模板，须含 {content} 占位符。"""
    return _load_file(_PROMPTS_DIR / "deai" / "rewrite_full.txt")


def load_deai_opening_template() -> str | None:
    return _load_file(_PROMPTS_DIR / "deai" / "opening.txt")


def load_deai_ending_template() -> str | None:
    return _load_file(_PROMPTS_DIR / "deai" / "ending.txt")


def load_deai_paragraph_template() -> str | None:
    return _load_file(_PROMPTS_DIR / "deai" / "paragraph.txt")


# 导出版本号（供 A/B 测试或日志）
PROMPT_VERSIONS = load_prompt_versions()

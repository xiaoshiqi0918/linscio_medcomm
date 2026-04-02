"""
提示词加载器
优先从 prompt-example 文件夹加载，作为同步代码层的基础
prompt-example 位于项目根目录（backend 的上级）
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
    """从 prompt-example 加载 Layer 0 系统提示词"""
    return _load_file(_PROMPTS_DIR / "layer0_system.txt")


def load_writing_sop() -> str | None:
    """加载精简版写作 SOP 核心原则（用于系统消息）。

    完整版 writing_sop.txt 已移入 system-knowledge/ 目录通过 RAG 按需检索，
    系统消息中只注入核心原则摘要以节省 token。
    """
    return _load_file(_PROMPTS_DIR / "writing_sop_core.txt")


def load_layer1_anti_hallucination() -> str | None:
    """从 prompt-example 加载 Layer 1 防编造提示词"""
    return _load_file(_PROMPTS_DIR / "layer1_anti_hallucination.txt")


def load_layer1_visual_anti() -> str | None:
    """从 prompt-example 加载图示类专属防编造规则"""
    return _load_file(_PROMPTS_DIR / "layer1_visual_anti.txt")


def load_layer1_script_anti() -> str | None:
    """从 prompt-example 加载脚本类专属防编造规则"""
    return _load_file(_PROMPTS_DIR / "layer1_script_anti.txt")


def load_children_audience_patch() -> str | None:
    """从 prompt-example 加载儿童受众规范补丁"""
    return _load_file(_PROMPTS_DIR / "children_audience_patch.txt")


def _load_json(path: Path) -> dict | list | None:
    """读取 JSON 文件"""
    content = _load_file(path)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return None


def load_verification(name: str) -> str | None:
    """加载验证类提示词：claim_verify, fact_verify, reading_level, suggest_images, analogy_anti_examples"""
    return _load_file(_PROMPTS_DIR / "verification" / f"{name}.txt")


def load_format_section() -> dict | None:
    """加载 format_section.json"""
    return _load_json(_PROMPTS_DIR / "format_section.json")


def load_format_section_default() -> str | None:
    """加载 format_section_default.txt"""
    return _load_file(_PROMPTS_DIR / "format_section_default.txt")


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
    """加载辅助提示词（v2.3）：scene_desc_optimize, rag_filter, feedback_integrate, compress, term_explain"""
    return _load_file(_PROMPTS_DIR / "auxiliary" / f"{name}.txt")


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
    """加载外部写作规范模板：prompts/task/{name}.txt

    用于 prompt_builder 增强层，作为写作标准参考注入（不替换基础提示词）。
    """
    return _load_file(_PROMPTS_DIR / "task" / f"{name}.txt")


def load_platform_config() -> dict | None:
    """加载平台配置：prompts/task/platform_config.json"""
    return _load_json(_PROMPTS_DIR / "task" / "platform_config.json")


# 导出版本号（供 A/B 测试或日志）
PROMPT_VERSIONS = load_prompt_versions()

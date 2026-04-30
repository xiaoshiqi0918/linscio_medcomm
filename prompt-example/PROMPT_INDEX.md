# 提示词索引

本文档列出 `prompt-example/prompts/` 下文件与代码的对应关系。  
路径优先使用**新分层目录**；括号内为兼容回退路径。

---

## Layer 0

| 文件 | 代码 |
|------|------|
| `layer0/system.txt`（v2.0 读者向） | `system.py` → `_DEFAULT_SYSTEM_READER_FACING`（读者向版本） |
| `layer0/writing_sop_core.txt`（旧：根目录同名） | `loader.load_writing_sop` |
| `part1/writing_sop.txt`（旧：根目录同名） | `loader.load_full_writing_sop_document`（可选接入） |

---

## Layer 1

| 文件 | 代码 |
|------|------|
| `layer1/anti_hallucination.txt` | `loader.load_layer1_anti_hallucination` → `anti_hallucination.py` |
| `layer1/visual_anti.txt` | `load_layer1_visual_anti` |
| `layer1/script_anti.txt` | `load_layer1_script_anti` |
| `layer1/children_audience_patch.txt` | `load_children_audience_patch` → `audiences.py` |
| `layer1/contest_article_rules.txt` | `anti_hallucination.py` → `_DEFAULT_CONTEST_ARTICLE_RULES`（参赛图文专属 C1-C10） |
| `anti_hallucination.py` 内各形式族常量 | 其他形式专属规则仍以代码为主，可按需拆到 `layer1/formats/` 并接 loader |

---

## Part 1

| 文件 | 代码 |
|------|------|
| `part1/auxiliary/*.txt`（旧：`auxiliary/*.txt`） | `load_auxiliary` → `auxiliary_prompts.py` |
| `part1/writing_sop.txt` | 完整 SOP 文本 |

---

## Part 2

运行时以文献绑定 + `prompt_builder` 动态组装为主；见 `part2/README.md`。

---

## Part 3

| 文件 | 代码 |
|------|------|
| `part3/task/*.txt`（旧：`task/*.txt`） | `load_task_guideline` → `prompt_builder._load_writing_guideline` |
| `part3/task/platform_config.json` | `load_platform_config` |
| `part3/format_section.json` | `load_format_section` → `format_section.py` |
| `part3/format_section_default.txt` | `load_format_section_default` |

### Part 3 — 参赛图文科普（contest_article）

| 文件 | 章节 |
|------|------|
| `part3/task/contest_intro.txt` | 导言 |
| `part3/task/contest_knowledge_1.txt` | 知识点一 |
| `part3/task/contest_knowledge_2.txt` | 知识点二 |
| `part3/task/contest_knowledge_3.txt` | 知识点三 |
| `part3/task/contest_misconception.txt` | 常见误区 |
| `part3/task/contest_advice.txt` | 实用建议 |
| `part3/task/contest_conclusion.txt` | 总结 |
| `part3/contest_prior_sections.txt` | 前序章节衔接规则 |
| `part3/contest_constraints.txt` | 赛制约束模板 |
| `imagegen/contest_painting_intent.txt` | 配图画意建议 + 双语 Prompt Schema |

---

## 文献分析

| 文件 | 代码 |
|------|------|
| `literature/analysis_single.txt` | `load_literature_analysis_single` → `analyzer.py` 回退 `ANALYSIS_SYSTEM_PROMPT` |
| `literature/per_paper.txt` | `load_literature_per_paper` |
| `literature/synthesis.txt` | `load_literature_synthesis` |

---

## 去 AI 化（deai）

| 文件 | 代码 |
|------|------|
| `deai/rewrite_full.txt` | `load_deai_rewrite_full_template` → `deai_rewriter`（占位 `{content}`） |
| `deai/opening.txt`、`ending.txt`、`paragraph.txt` | 段落级改写模板 |
| `deai/system_override.txt` | **非空则整段替换**动态 system；空则使用 `_build_deai_system_prompt` |

---

## 验证 / 配图 / 其他

| 目录 | 代码 |
|------|------|
| `verification/*.txt` | `load_verification` |
| `imagegen/contest_painting_intent.txt` | `prompt_engine.py` → `_SUGGEST_INTENT_SYSTEM_PROMPT`（P1 画意建议 v2.0） |
| `imagegen/orchestrator_system.txt` | `prompt_engine.py` → `_ORCHESTRATOR_SYSTEM_PROMPT`（P5 LLM 编排器） |
| `imagegen/negative_library.yaml` | `prompt_engine.py` → `_load_negative_library`（四维分层负向词库 v1.0） |
| `imagegen/style_presets/sd_tag.yaml` | `prompt_engine.py` → `_load_style_presets("sd_tag.yaml")`（A 族 SD-tag 风格预设） |
| `imagegen/style_presets/natural_en.yaml` | `prompt_engine.py` → `_load_style_presets("natural_en.yaml")`（B 族英文风格预设） |
| `imagegen/style_presets/natural_zh.yaml` | `prompt_engine.py` → `_load_style_presets("natural_zh.yaml")`（B 族中文风格预设） |
| `imagegen/style_presets/gpt_image.yaml` | `prompt_engine.py` → `_load_style_presets("gpt_image.yaml")`（C 族 GPT Image 风格预设） |
| `imagegen/*`（其他） | `load_imagegen_*` → `imagegen/prompt_builder.py` |
| `comic/`、`handbook/`、`polish/` | `load_comic_guideline`、`load_handbook_guideline`、`load_polish` |

---

## 同步说明

- 修改 `prompt-example` 内文件后，**重启**使用这些 loader 的进程即可，无需改 Python 常量（除非回退逻辑触发）。
- 若需与代码内嵌字符串完全一致，可 periodically 用仓库脚本从 `.py` 导出到 txt（或使用当前已导出的 `literature/`、`deai/` 为基准）。

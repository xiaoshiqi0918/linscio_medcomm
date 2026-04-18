# 提示词索引

本文档列出 `prompt-example/prompts/` 下文件与代码的对应关系。  
路径优先使用**新分层目录**；括号内为兼容回退路径。

---

## Layer 0

| 文件 | 代码 |
|------|------|
| `layer0/system.txt`（旧：`layer0_system.txt`） | `loader.load_layer0_system` → `system.py` `MEDCOMM_SYSTEM_PROMPT` |
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
| `anti_hallucination.py` 内各形式族常量 | 形式专属规则仍以代码为主，可按需拆到 `layer1/formats/` 并接 loader |

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
| `imagegen/*` | `load_imagegen_*` → `imagegen/prompt_builder.py` |
| `comic/`、`handbook/`、`polish/` | `load_comic_guideline`、`load_handbook_guideline`、`load_polish` |

---

## 同步说明

- 修改 `prompt-example` 内文件后，**重启**使用这些 loader 的进程即可，无需改 Python 常量（除非回退逻辑触发）。
- 若需与代码内嵌字符串完全一致，可 periodically 用仓库脚本从 `.py` 导出到 txt（或使用当前已导出的 `literature/`、`deai/` 为基准）。

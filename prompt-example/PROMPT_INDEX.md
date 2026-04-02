# 提示词索引

本文档列出 prompt-example 中所有提示词文件及其对应的代码位置。  
**说明**：带 `(*)` 的表示代码仍从 Python 模块加载，prompt-example 中为同步副本，供维护与版本管理；后续可接入 loader 实现运行时从文件加载。

---

## Layer 0 / 1（已接入 loader）

| 文件 | 代码位置 |
|------|----------|
| prompts/layer0_system.txt | prompts/system.py |
| prompts/layer1_anti_hallucination.txt | prompts/anti_hallucination.py |

---

## 验证与核实

| 文件 | 代码位置 |
|------|----------|
| prompts/verification/claim_verify.txt | prompts/verification.py CLAIM_VERIFY_PROMPT |
| prompts/verification/fact_verify.txt | prompts/verification.py FACT_VERIFY_PROMPT |
| prompts/verification/reading_level.txt | prompts/verification.py READING_LEVEL_PROMPT |
| prompts/verification/suggest_images.txt | prompts/verification.py SUGGEST_IMAGES_PROMPT |
| prompts/verification/analogy_anti_examples.txt | 质量自评比喻检查参照（load_verification("analogy_anti_examples")） |

---

## 形式简版（Format Section Fallback）

| 文件 | 代码位置 |
|------|----------|
| prompts/format_section.json | prompts/format_section.py FORMAT_SECTION_PROMPTS |
| prompts/format_section_default.txt | prompts/format_section.py DEFAULT_PROMPT |

---

## 条漫 Agent

| 文件 | 代码位置 |
|------|----------|
| prompts/comic/planner.txt | comic/comic_agent.py _get_comic_planner_prompt |
| prompts/comic/panel.txt | comic/comic_agent.py _get_comic_panel_prompt |

---

## 患者手册 Agent

| 文件 | 代码位置 |
|------|----------|
| prompts/handbook/cover.txt | handbook/handbook_agent.py _get_cover_prompt |
| prompts/handbook/disease_intro.txt | handbook/handbook_agent.py _get_disease_intro_prompt |
| prompts/handbook/symptoms.txt | handbook/handbook_agent.py _get_symptoms_prompt |
| prompts/handbook/treatment.txt | handbook/handbook_agent.py _get_treatment_prompt |
| prompts/handbook/daily_care.txt | handbook/handbook_agent.py _get_daily_care_prompt |
| prompts/handbook/visit_tips.txt | handbook/handbook_agent.py _get_visit_tips_prompt |
| prompts/handbook/fallback.txt | handbook/handbook_agent.py get_base_prompt fallback |

---

## 润色 Agent

| 文件 | 代码位置 |
|------|----------|
| prompts/polish/language_polish.txt | polish/polish_agent.py LanguagePolishAgent |
| prompts/polish/platform_adapt.txt | polish/polish_agent.py PlatformAdaptAgent |

---

## 图像生成

| 文件 | 代码位置 |
|------|----------|
| prompts/imagegen/style_system.json | imagegen/prompt_builder.py STYLE_SYSTEM_PROMPTS |
| prompts/imagegen/quality_suffix.txt | imagegen/prompt_builder.py QUALITY_SUFFIX |
| prompts/imagegen/safety_negative.txt | imagegen/prompt_builder.py SAFETY_NEGATIVE |
| prompts/imagegen/image_type_templates.json | imagegen/prompt_builder.py IMAGE_TYPE_TEMPLATES |
| prompts/imagegen/translate_system.txt | imagegen/prompt_builder.py 翻译 system prompt |

---

## 任务提示词（Task Prompts）(*)

| 文件 | 代码位置 |
|------|----------|
| prompts/task/article_intro.txt | task_prompts.py get_article_intro |
| prompts/task/article_body.txt | task_prompts.py get_article_body |
| prompts/task/platform_config.json | task_prompts.py PLATFORM_HOOKS / PLATFORM_FORMAT / PLATFORM_WORD_GUIDE |

**说明**：task_prompts.py 中尚有 article_case, article_qa, article_summary, debunk_*, story_*, research_*, oral_*, drama_*, storyboard_*, audio_*, card_*, picture_book_*, poster_*, quiz_*, h5_* 等大量提示词。其结构类似，可在本目录下按 `task/{format}_{section}.txt` 命名逐步迁移，并接入 loader。

---

## 接入说明

- **已接入**：Layer 0/1 通过 `prompts/loader.py` 在运行时从 prompt-example 加载
- **待接入**：verification、format_section、comic、handbook、polish、imagegen、task 等需在对应模块中调用 loader 并从文件加载
- 接入时保留代码内默认值作为回退，确保 prompt-example 不存在或加载失败时系统仍可运行

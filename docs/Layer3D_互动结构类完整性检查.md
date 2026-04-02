# Layer 3D：互动/结构类 Agent 完整性检查

## 检查结论概览

| 形式 | 规范要求 | 当前实现 | 完整性 | 待办事项 |
|------|----------|----------|--------|----------|
| **患者教育手册** | 6 个专用 Agent，各节详细 prompt | HandbookSectionAgent 通用简版 | ⚠️ 部分 | 各节接入规范 prompt |
| **自测科普** | QuizQuestionAgent（JSON + format_meta） | FormatAgent + 简版 fallback | ❌ 未实现 | 题目 JSON 规范 + format_meta |
| **H5 大纲** | H5OutlineAgent（整体 JSON 一次生成） | FormatAgent + 5 分节 | ⚠️ 结构差异 | 整体 vs 分节需选型 |

---

## 8.1 患者教育手册 Agent 群

### 规范要求

| section_type | Agent | 输出/内容结构 |
|--------------|-------|----------------|
| cover_copy | HandbookCoverAgent | JSON：main_title, sub_title, tagline, cover_visual_desc, institution_placeholder, edition_note |
| disease_intro | HandbookDiseaseIntroAgent | Q1/Q2/Q3 结构，100-150 字/段 |
| symptoms | HandbookSymptomsAgent | 常见症状、⚠️ 警示框、容易忽视的症状 |
| treatment | HandbookTreatmentAgent | 治疗目标、主要治疗方式、【医嘱】结尾 |
| daily_care | HandbookDailyCareAgent | 饮食/运动/监测/生活方式，具体可操作 |
| visit_tips | HandbookVisitTipsAgent | 就诊准备、沟通清单 5 问、复诊、紧急联系 |

### 当前实现

- **HandbookSectionAgent**（`backend/app/agents/handbook/handbook_agent.py`）
  - 使用 SECTION_MAP + FORMAT_SECTION_PROMPTS 简版
  - 统一 prompt：「请为患者手册撰写「{section_desc}」部分」+ 通用格式要求
  - ❌ 无各节专属的详细结构（Q1/Q2/Q3、警示框、沟通清单等）
  - ❌ cover_copy 未要求 JSON 输出

### 建议改动

1. **方案 A**：在 HandbookSectionAgent 内按 section_type 分支，返回规范级 prompt
2. **方案 B**：将 patient_handbook 改用 FormatAgent，在 task_prompts 实现 6 个 `get_handbook_xxx` 函数

---

## 8.2 自测科普 Agent（QuizAgent）

### 规范要求

- **QuizQuestionAgent**
  - `format_meta`：question_index, question_type（误区识别/知识测试/行为评估）
  - 输出 JSON：question_text, options, correct_answer, explanation, key_learning
  - 题目设计原则、解析规范

- 规范仅覆盖**题目**（q_1～q_5），未单独定义 quiz_intro 与 summary

### 当前实现

- **quiz_article** 使用 **FormatAgent**（无专用 Agent）
- **TASK_PROMPT_FUNCS** 中无 quiz_article 条目
- format_section 仅：「请撰写题目1（含选项与解析要点）」

### 建议改动

1. **task_prompts**：实现 `get_quiz_intro`、`get_quiz_question`（支持 section_type 与 format_meta）、`get_quiz_summary`
2. **TASK_PROMPT_FUNCS**：添加 quiz_article 映射
3. **_build_format_meta**：为 q_1～q_5 填充 question_index、question_type

---

## 8.3 H5 大纲 Agent

### 规范要求

- **H5OutlineAgent**：**整体一次生成**
  - 输出 JSON：h5_title, total_pages, pages[], share_copy
  - 每页：page_type, page_title, page_content, interaction, visual_desc
  - 页数 5-8，必须有互动元素、分享引导页

### 当前实现

- **h5_outline** 使用 **FormatAgent**
- **SECTION_TYPES_BY_FORMAT**：page_cover, page_1, page_2, page_3, page_end（5 个分节）
- 规范为**整体 JSON**，当前为**分节生成**

### 设计选择

| 方案 | 说明 |
|------|------|
| **A. 整体生成** | 新增 section_type 如 `full_outline`，一次生成完整 JSON，需调整存储与前端展示 |
| **B. 保留分节** | 为 page_cover、page_1～3、page_end 补充规范级 task_prompt，导出时组装 |

建议：若产品需分页编辑，选 B；若接受一次性生成 H5 大纲，选 A。

---

## 汇总：建议实施顺序

1. **P0**：患者手册 6 节接入规范 prompt（HandbookSectionAgent 内分支或 task_prompts）
2. **P0**：自测科普实现 get_quiz_question + format_meta
3. **P1**：自测 quiz_intro、summary 补充规范
4. **P2**：H5 大纲结构选型（整体 vs 分节）

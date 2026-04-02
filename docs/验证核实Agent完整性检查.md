# 验证与核实 Agent 完整性检查

## 检查结论概览

| 模块 | 规范要求 | 当前实现 | 完整性 | 待办事项 |
|------|----------|----------|--------|----------|
| **CLAIM_VERIFY_PROMPT** | 医学声明核实，JSON 输出 | 提示词已定义 | ✅ 已实现 | pipeline 未接入 LLM |
| **FACT_VERIFY_PROMPT** | 数据占位符 + 绝对化检测 | 提示词已定义 | ✅ 已实现 | pipeline 未接入 LLM |
| **READING_LEVEL_PROMPT** | 阅读难度分析 | 提示词已定义 | ⚠️ 部分 | 缺 audience_standard 等占位符；pipeline 未接入 LLM |

---

## 11.1 医学声明核实

### 规范要求

- 提取医学声明，对照 RAG 参考资料核查
- 输出 JSON：claims（claim_text, claim_type, verification_status, supporting_source, confidence, note）、overall_assessment、review_priority

### 当前实现

- **CLAIM_VERIFY_PROMPT**：已在 `app/agents/prompts/verification.py` 中定义，与规范一致
- **pipeline._verify_claims**：使用启发式（关键词提取 + RAG 子串匹配），**未调用 LLM**，未使用 CLAIM_VERIFY_PROMPT

---

## 11.2 数据占位符检测

### 规范要求

- 识别：unverified_data、absolute_statement、specific_dosage
- 输出 JSON：data_warnings、absolute_terms

### 当前实现

- **FACT_VERIFY_PROMPT**：已定义，与规范一致
- **pipeline._verify_data_placeholders**：仅用正则匹配 `[DATA:]` 占位符
- **pipeline._detect_absolute_terms**：使用关键词列表，**未调用 LLM**，未使用 FACT_VERIFY_PROMPT

---

## 11.3 阅读难度核查

### 规范要求

- 占位符：target_audience、audience_standard、max_term_density、max_sentence_len
- 输出：passed、stats（avg_sentence_len, term_density, passive_voice_ratio, unexplained_abbreviations）、issues、suggestions

### 当前实现

- **READING_LEVEL_PROMPT**：已定义，但缺 `audience_standard`、`max_term_density`、`max_sentence_len` 等占位符的具体注入
- **pipeline._check_reading_level**：使用 jieba 估算术语密度，**未调用 LLM**，未使用 READING_LEVEL_PROMPT

---

## 汇总

| 项目 | 状态 |
|------|------|
| 提示词定义 | ✅ 三个提示词均在 verification.py |
| 流水线接入 LLM | ✅ 已接入，通过 use_llm_verification 或 USE_LLM_VERIFICATION=1 启用 |
| READING_LEVEL 占位符 | ✅ 已补充 audience_standard、max_term_density、max_sentence_len |

### 使用方式

- 默认：启发式实现（无 LLM 调用）
- 启用 LLM：`run_verification(..., use_llm_verification=True)` 或设置环境变量 `USE_LLM_VERIFICATION=1`

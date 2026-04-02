# 润色与适配 Agent 完整性检查

## 检查结论概览

| 模块 | 规范要求 | 当前实现 | 完整性 | 待办事项 |
|------|----------|----------|--------|----------|
| **LanguagePolishAgent** | 通俗化润色，Track Changes JSON | 无 | ❌ 未实现 | 新建 Agent + 接入 polish_run |
| **PlatformAdaptAgent** | 平台适配，PLATFORM_SPECS | 无 | ❌ 未实现 | 新建 Agent + 接入 polish_run |
| **polish_run API** | 调用 Agent 执行润色 | 骨架，返回「开发中」 | ❌ 未实现 | 实现执行逻辑 |
| **PolishChange 模型** | 存储 change 详情 | 有 original_text, suggested_text | ⚠️ 部分 | 可扩展 reason、change_type |

---

## 10.1 通俗化润色 Agent

### 规范要求

- **LanguagePolishAgent**
  - 输入：原文 + target_audience
  - 使用 AUDIENCE_PROFILES（词汇、句长、风格标准）
  - 输出：Track Changes 格式 JSON 数组
    - change_type: "replace"
    - original, revised, reason
  - 润色优先级：① 术语未解释 ② 句子过长 ③ 被动语态 ④ 绝对化表述 ⑤ 语气

### 当前实现

- **无 LanguagePolishAgent**
- **polish_run** 仅返回 `{"message": "润色功能开发中"}`

---

## 10.2 平台适配 Agent

### 规范要求

- **PlatformAdaptAgent**
  - PLATFORM_SPECS：wechat, xiaohongshu, douyin, bilibili, journal, offline 的字数、格式、语气、特殊要求
  - 输出 JSON：adapted_content, word_count, changes_summary, platform_tips

### 当前实现

- **无 PlatformAdaptAgent**
- polish_type 支持 "language" / "platform" / "level"，但无对应 Agent 或 prompt

---

## 数据模型

### PolishChange 当前字段

- original_text, suggested_text, status
- 规范 Track Changes 需要：change_type, original, revised, reason
- 可复用：original_text≈original, suggested_text≈revised；可扩展 JSON 列存 reason、change_type

---

## 汇总：建议实施顺序

1. **P0**：新建 `LanguagePolishAgent`、`PlatformAdaptAgent`（或合并为 PolishAgent 按 polish_type 分支）
2. **P0**：实现 `polish_run`：加载 section 内容 → 按 polish_type 调用对应 Agent → 解析 JSON → 写入 PolishChange
3. **P1**：PolishChange 增加 reason、change_type（或 format_meta JSON）
4. **P2**：前端 Track Changes 展示与采纳/拒绝交互

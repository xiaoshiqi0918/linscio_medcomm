# 提示词示例库（prompt-example）

本文件夹为 MedComm 提示词体系的**统一维护入口**。运行时由 `backend/app/agents/prompts/loader.py` 优先从此处加载；**修改 txt/json 后重启后端**即可生效（无自动监视）。

---

## 快速入口

| 文档 | 说明 |
|------|------|
| [DIAGNOSTIC_REPORT.md](./DIAGNOSTIC_REPORT.md) | **全局优化诊断报告**（系统性问题分析、优化路线图、Token 预算） |
| [CHANGELOG.md](./CHANGELOG.md) | **设计决策与变更理由**（冲突消解、新增/删除原因、跨模型加固措施） |
| [PROMPT_INDEX.md](./PROMPT_INDEX.md) | 文件与代码对照索引 |
| [PROMPT_VERSIONS.json](./PROMPT_VERSIONS.json) | 版本注册表 |

---

## 分层目录（与四层架构对应）

```
prompt-example/
├── CHANGELOG.md              # 设计决策与变更日志
├── PROMPT_VERSIONS.json      # 版本注册表
├── PROMPT_INDEX.md           # 文件与代码对照索引
├── README.md                 # 本说明
└── prompts/
    ├── layer0/               # Layer 0：系统级（身份、溯源、[N] 规则）
    ├── layer1/               # Layer 1：防编造通用 + 图示/脚本/儿童补丁
    ├── part1/                # Part 1：能力增强（auxiliary、完整 writing_sop）
    ├── part2/                # Part 2：说明占位（正文事实来源多为运行时注入）
    ├── part3/                # Part 3：task/*.txt、format_section*.json
    ├── literature/           # 文献分析 system 提示词（单次 / 单篇 / 综合）
    ├── deai/                 # 去 AI 化改写模板与可选 system 覆盖
    ├── verification/         # 输出后验证
    ├── imagegen/             # 配图与翻译
    ├── comic/、handbook/、polish/、convert/ …
    └── auxiliary/            # 兼容旧路径；新文件请写入 part1/auxiliary/
```

**兼容**：loader 对新旧路径均会尝试（例如 `layer0/system.txt` 与根目录 `layer0_system.txt`），迁移期间不会丢文件。

---

## A.1 版本管理

- **版本注册**：`PROMPT_VERSIONS.json`
- **修改规范**：每次内容变更，版本号 +0.1（如 v1.0 → v1.1）

---

## A.2 提示词优化流程

```
发现问题（用户反馈 / 质量检测）
    ↓
在 prompt-example 对应分层目录中修改
    ↓
（可选）更新 PROMPT_VERSIONS.json
    ↓
重启后端 / 客户端所连 API
    ↓
测试环境用真实场景验证
```

---

## A.3 与代码层的关系

| 分层 | 主要加载入口 |
|------|----------------|
| Layer 0–1 | `loader.load_layer0_system` 等 → `system.py` / `anti_hallucination.py` |
| Part 1–3 | `load_task_guideline`、`load_auxiliary`、`build_enhanced_prompt` |
| 文献分析 | `load_literature_*` → `literature/analyzer.py` |
| 去 AI | `load_deai_*` → `deai_rewriter.py` |

代码内仍保留**回退常量**（文件缺失或与占位符不匹配时）。

---

## A.4 Few-shot 与 system-knowledge

Few-shot 示例与长篇知识库仍在 `system-knowledge/`，按需由 RAG 检索，不与此目录的 Layer 静态文件重复。

# 提示词示例库（prompt-example）

本文件夹为 MedComm 提示词体系的**统一维护入口**，作为同步代码层的基础。

---

## A.1 版本管理

所有提示词使用版本号管理，便于 A/B 测试与回溯。

- **版本注册**：`PROMPT_VERSIONS.json`
- **修改规范**：每次内容变更，版本号 +0.1（如 v1.0 → v1.1）

---

## A.2 提示词优化流程

```
发现问题（用户反馈 / 质量检测）
    ↓
定位到具体 Agent 和提示词
    ↓
在 prompt-example 中修改提示词，版本号 +0.1
    ↓
在测试环境用 10 个真实场景验证
    ↓
与旧版本对比输出质量（人工评估）
    ↓
通过后更新版本号，同步到代码层
    ↓
记录到 PROMPT_VERSIONS.json
```

---

## A.3 Few-shot 示例数据质量要求

每条进入示例库（writing_examples）的内容需满足：

- **医学内容经过专业医生审核**：通过 `medical_reviewed` 字段标记
- **语言风格符合目标平台和受众标准**
- **通过 AUTO_QUALITY_RULES 自动检测**
- **不直接复制任何已发表文章**（原创改写，版权安全）
- **标注来源文档**：通过 `source_doc` 字段存储（内部归档，不对外展示）

---

## 目录结构

```
prompt-example/
├── PROMPT_VERSIONS.json   # 版本注册表
├── PROMPT_INDEX.md        # 提示词索引（文件与代码对照）
├── README.md              # 本说明
└── prompts/
    ├── layer0_system.txt
    ├── layer1_anti_hallucination.txt
    ├── format_section.json
    ├── format_section_default.txt
    ├── verification/
    │   ├── claim_verify.txt
    │   ├── fact_verify.txt
    │   ├── reading_level.txt
    │   └── suggest_images.txt
    ├── comic/
    │   ├── planner.txt
    │   └── panel.txt
    ├── handbook/
    │   ├── cover.txt
    │   ├── disease_intro.txt
    │   ├── symptoms.txt
    │   ├── treatment.txt
    │   ├── daily_care.txt
    │   ├── visit_tips.txt
    │   └── fallback.txt
    ├── polish/
    │   ├── language_polish.txt
    │   └── platform_adapt.txt
    ├── imagegen/
    │   ├── style_system.json
    │   ├── quality_suffix.txt
    │   ├── safety_negative.txt
    │   ├── image_type_templates.json
    │   └── translate_system.txt
    └── task/
        ├── article_intro.txt
        ├── article_body.txt
        └── platform_config.json
```

---

## 同步说明

- **静态提示词**（Layer 0/1）：直接由代码从 `prompts/*.txt` 加载
- **动态任务提示词**（Layer 3）：模板逻辑在代码层，版本号在 PROMPT_VERSIONS 中维护
- 更新后需在测试环境验证，再合并到主分支

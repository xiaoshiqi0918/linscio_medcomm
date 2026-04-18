# 全局优化诊断报告

> 基于对完整 prompt 体系的逐层分析（Layer 0 ×3 + Layer 1 ×4 + Part 1 辅助 ×5 + writing_sop 846行 + format_section + platform_config + Part 3 task ×30），本报告汇总系统性问题并给出优化路线图。

---

## 一、最严重的系统性问题：规则重复与冲突

### 1.1 同一规则在多处重复且措辞不一致

以下规则在整个体系中出现了 3 次以上，每次措辞和强度都有差异：

| 规则内容 | 出现位置（不完全列举） | 核心风险 |
|---------|---------------------|---------|
| 禁止给出具体用药剂量 | Layer 0 system ×1, writing_sop_core ×1, anti_hallucination ×1, writing_sop.txt §7 ×1, article_body ×1 | 强度不一致（"加免责" vs "绝对禁止" vs "不得推荐"） |
| 证据语言分级 | Layer 0 system（六级）, writing_sop_core（四级）, writing_sop.txt §5（四级，措辞略不同） | 三套分级体系无映射关系 |
| 禁止套话开头 | Layer 0 反AI腔调（如有）, writing_sop.txt §8, article_intro, article_body, outline, research_background | 禁止清单每处不完全相同 |
| 叙事科普方法论 | writing_sop.txt §4, article_body, outline, topic_plan | 效果数据（2.6倍/5倍）每处都重复 |
| 慢性病"知-信-行"框架 | writing_sop.txt §9.8, article_body, outline, topic_plan | "28%→82%"数据出现 4 次 |
| 中医药科普规范 | writing_sop.txt §9.9+§12.4, article_body 中医特别要求, topic_plan §5 | 大量重复，每处覆盖面略不同 |
| 受众适配 | writing_sop_core §4, writing_sop.txt §6, outline, topic_plan §4 | 受众分类每处不完全一致 |
| 待补充占位符规范 | Layer 0 system, writing_sop_core, anti_hallucination, article_body, card_content, debunk_myth | 触发条件描述每处不同 |
| 数据处理规范 | writing_sop.txt §7.13, article_body §③ | 基本一致但分散在两处 |

**风险**：模型面对 3-5 次重复但措辞不同的同一规则时，会选择最后看到的版本（recency bias）或随机选择，导致执行不稳定。

### 1.2 优化原则：单一权威来源（Single Source of Truth）

每条规则只在一个地方定义，其他地方引用或不提。具体方案：

- **Layer 0**：所有跨体裁的硬约束（安全红线、事实溯源、证据语言、反AI腔调）的唯一定义处
- **Layer 1**：仅追加该体裁特有的增量规则
- **Part 1 writing_sop.txt**：仅保留领域知识（选题方法、标题技巧、开头技巧、叙事方法论、中医/药学/临床诊断专科规范），删除所有与 Layer 0 重复的规则条目
- **Part 3 task prompt**：仅包含该章节的具体任务指令，不重复任何通用规则；如需提醒安全约束，用一句引用（"遵守系统层安全红线"）而非重新列举

---

## 二、Part 1 writing_sop.txt 的重组方案

当前 846 行文档需要拆分为两部分：

### 2.1 应删除的部分（与 Layer 0 重复）

- §1 九大原则 → 已在优化后 Layer 0 §7 统一定义
- §5 证据引用规范 → 已在 Layer 0 §2 统一定义
- §6 受众适配 → 应由风格注册表动态注入
- §7 质量红线 → 已在 Layer 0 §3 统一定义
- §7.12-18 差错防范清单中与 Layer 0 重复的条目

### 2.2 应保留的部分（真正的领域知识，Part 1 的核心价值）

| 保留内容 | 原位置 | 优化建议 |
|---------|-------|---------|
| 选题三维锚定法 | §2 | 保留，精简数据 |
| 标题心理技巧 + 科学性底线 | §3 | 保留，删除传播效果数据 |
| 开头五种技巧 | §8 | 保留 |
| 叙事科普方法论 | §4 正文规范 | 保留核心方法论，删除效果数据，全系统只保留一份 |
| 视觉设计原则 | §4 插图部分 | 保留核心指导，删除眼动研究数据 |
| 疾病科普指南框架（防-筛-诊-治-康） | §9.1-7 | 保留 |
| 慢性病管理科普规范 | §9.8 | 保留核心框架，删除重复的实证数据 |
| 中医药科普完整规范 | §9.9 + §12.4 | 合并为一份，保留 |
| 药学科普规范 | §9.12-13 | 保留 |
| 临床诊断类科普规范 | §12.6 | 保留 |
| 低质网页硬伤清单 | §12.7 | 保留，极有价值 |
| 中医科普特殊要求（中药处方/穴位/食疗/贴敷等） | §12.4 | 保留 |
| 传播形式与平台适配 | §10 | 精简，与 platform_config.json 对齐 |

### 2.3 轻量/完整注入的分界

按你的架构设计（_LIGHT_SECTIONS），建议：

- **轻量注入**（所有章节都吃）：叙事方法论核心原则、反套话清单、证据语言速查表
- **完整注入**（非轻量章节才吃）：选题方法、标题技巧、开头技巧、专科规范（中医/药学/临床诊断）、视觉设计原则、低质网页硬伤清单
- **条件注入**（按主题触发）：中医药规范（仅中医相关主题）、慢性病框架（仅慢性病主题）

---

## 三、Part 3 Task Prompt 的系统性问题

### 3.1 质量两极分化

| 质量等级 | 代表文件 | 特征 |
|---------|---------|------|
| A 级（可直接使用） | story_climax, article_summary, article_qa, qa_intro, quiz_intro, research_caution | 正反示例精准、禁止清单具体、反AI腔调到位 |
| B 级（需要小改） | article_body, article_case, debunk_myth, card_content, oral_hook, picture_book_page | 结构好但有重复规则或缺少安全衔接 |
| C 级（需要重写） | audio 全系列(5份), fallback, h5_section, storyboard_frame, drama_scene_setup | 过于简陋，缺少字数限制/禁止事项/输出格式/安全约束 |

### 3.2 C 级 prompt 的统一补齐模板

所有 C 级 task prompt 应至少包含以下要素：

```
【内容信息】（任务上下文）
【输出格式】（明确的格式要求或 JSON schema）
【内容要求】（3-5 条具体的正面指令）
【语言规范】（风格/句长/字数限制）
【禁止事项】（3-5 条具体的负面约束）
【质量示范】（至少 1 正 1 反示例）
```

### 3.3 跨章节连贯性问题

story 系列、research 系列、debunk 系列等多章节体裁，后续章节依赖"看到"前序章节的输出。当前只有 article_qa 做了显式声明（"本文的引言、正文、案例部分已经完成"）。

建议所有非首章节的 task prompt 增加统一的前序引用块：

```
【前序章节】（由系统自动注入，以下为已完成的章节内容）
{previous_sections}

【本章节任务】
在以上内容基础上，撰写……
```

### 3.4 实证数据的统一管理

以下数据在多份 task prompt 中反复出现：

| 数据 | 出现次数 | 建议处理 |
|------|---------|---------|
| 叙事科普播放量 2.6 倍 | 4+ 次 | 全系统只保留 1 处（writing_sop.txt 叙事方法论节），其他删除 |
| 标题感叹句 OR=5.36 | 3+ 次 | 只保留在标题技巧节 |
| 用药依从率 28%→82% | 4+ 次 | 只保留在慢性病框架节 |
| 眼动研究注视时间 48% | 3+ 次 | 只保留在视觉设计原则节 |
| 公众需求排序数据 | 3+ 次 | 只保留在选题规范节 |

这些数据放在 Part 1 的领域知识中是合适的（作为方法论参考），但不应该散落到 Part 3 的 task prompt 中，因为模型可能将其引用到正文。

---

## 四、Part 1 辅助模块的优化建议

| 模块 | 当前状态 | 优化建议 |
|------|---------|---------|
| compress.txt | 质量好 | 增加非儿童高安全内容的保守阈值（如急症科普用30%而非50%） |
| feedback_integrate.txt | 最出色 | feedback_type 枚举增加 "add_content" |
| rag_filter.txt | 逻辑清晰 | 将受众匹配度与主题相关度拆为两个独立维度 |
| scene_desc_optimize.txt | 实用 | 增加风格值不在预设列表中时的兜底指令；放宽 negative_prompt 字数限制 |
| term_explain.txt | 精巧 | children 受众字数放宽到 25-30 字 |

---

## 五、优化执行路线图

### Phase 1（已完成）
- [x] Layer 0 统一版重写（合并三份文档，消解所有冲突）
- [x] Layer 1 三份体裁规则优化（children / script / visual）
- [x] 变更日志

### Phase 2（建议下一步）
- [ ] writing_sop.txt 重组：删除重复规则，保留领域知识，标注轻量/完整/条件注入分界
- [ ] Part 3 C 级 task prompt 重写（audio ×5, fallback, h5_section, storyboard_frame, drama_scene_setup）
- [ ] Part 3 所有 task prompt 去重：删除与 Layer 0 重复的规则条目
- [ ] Part 3 多章节体裁增加前序引用块
- [ ] 实证数据全系统去重，统一归入 Part 1 领域知识

### Phase 3（建议后续）
- [ ] format_section.json 补齐弱体裁（audio_script, quiz_article, h5_outline）的 base_prompt
- [ ] platform_config.json 合并 PLATFORM_HOOKS 和 ORAL_HOOKS 的重复项
- [ ] Part 1 辅助模块小幅优化（compress/feedback/rag_filter/scene_desc/term_explain）
- [ ] 跨模型验证测试：用同一篇文章任务，在 GPT-4/Claude/Gemini/通义上对比优化前后的输出质量

---

## 六、Token 预算估算

当前体系的一次完整调用大致消耗：

| 层级 | 当前预估 token | 优化后预估 token | 节省 |
|------|--------------|----------------|------|
| Layer 0 (system) | ~3000-4000 | ~2500（合并去重后） | ~25% |
| Layer 1 (system) | ~500-1000 | ~400-800（去除重复声明） | ~20% |
| Part 1 writing_sop | ~8000-10000 | ~4000-5000（删除重复规则） | ~50% |
| Part 1 辅助注入 | ~1000-2000 | ~1000-2000（基本不变） | — |
| Part 2 文献 | 变量 | 变量 | — |
| Part 3 task | ~800-1500 | ~600-1200（去除重复规则） | ~20% |

总计节省约 **30-40%** 的 system+user token，主要来自 writing_sop.txt 的规则去重。这些节省的 token 可以用来注入更多文献内容或增加 few-shot 示例。

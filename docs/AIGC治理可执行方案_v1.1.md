# AIGC 治理可执行方案 v1.1

> **版本**：v1.1（2026-05-01）
> **状态**：待开工
> **范围**：医学科普 SaaS 平台的 AIGC 检测、生成层反 AI 约束、改写层兜底
> **核心目标**：在保证医学准确性的前提下，把 AIGC 主分从历史 100 分（虚高）改为有区分度的 30/74/100 分布，并阻止改写器对事实的篡改

---

## 0. 现状速览

| 维度 | 状态 |
|---|---|
| 生成层 prompt 反 AI 约束 | ✅ 已有 220+ 行（`_PARAGRAPH_RHYTHM_RULES`） |
| 文献注入 / 引用机制 | ✅ 已有四层标注（`[文献N]/[共识]/[推断:]/[[待补充:]]`） |
| AI 味检测器 | ✅ 已升级（commit `0f0fee9`），分数区分度 30/74/100 |
| 检测/改写解耦 | ✅ 已完成（commit `db56218`） |
| 改写字数硬上限 | ✅ 已完成（commit `f49adc6`） |
| **改写后医学事实一致性** | ❌ 没有任何对照机制，仅检查长度 |
| **医学空洞度检测**（信息密度量化） | ❌ 没有 |
| **风险词分级 / 合规硬过滤** | ❌ prompt 里有约束但没事后阻断 |
| **改写轮数场景化** | ❌ 全格式统一 2 轮 |
| **改写透明度（段落标记+diff）** | ❌ 后端有 `ai_patterns_before_rewrite`，前端没暴露 |
| **用户反馈数据沉淀** | ❌ 没有"AI 版 vs 用户终稿" diff 收集 |

---

## 1. 核心原则（争议时的拍板依据）

> 这五条原则**单独维护**于 [`principles/AIGC原则.md`](principles/AIGC原则.md)，作为所有 AIGC 相关 PR review 的依据。

1. **医学准确性 > AI 味降低**：宁可 AIGC 分高 10 分，不可让一个数字被改错
2. **主战场在生成层，不是改写层**：80% 的"反 AI"工作应该在 prompt 完成；改写只做兜底
3. **改写绝不动事实**：数字 / 文献号 / 药物名 / 剂量 / 适应症 / 结论方向 / 限定词强度 / 研究对象 全部锁定
4. **透明优于自动**：让用户看到"哪段被改了、改了什么"，比追求自动黑盒更重要
5. **合规硬规则前置**：法律红线（绝对化用语、处方药、剂量建议）必须事后正则硬过滤，不依赖 LLM 自觉

---

## 2. 三层架构边界

```
┌─ 生成层（80% 投入）───────────────────┐
│ prompt 反 AI 约束（已有 220+ 行）      │
│ + 信息密度强制要求                     │
│ + 信源标注约束                         │
│ + 改写禁令前置（避免生成时就出错）     │
└────────────────────────────────────────┘
            ↓ 生成完成
┌─ 检测层（独立信号，不混淆）───────────┐
│ AI 味检测（已升级到 v1.1）             │
│ + 医学空洞度检测（concreteness_score） │
│ + 风险词分级扫描（红/黄/绿）           │
│ + 周期性离线 LLM 判别器抽样            │
└────────────────────────────────────────┘
            ↓ 高风险触发
┌─ 改写层（兜底，可被关闭）─────────────┐
│ 局部段落改写（已有）                   │
│ + 改写器信息禁令（7 条硬约束）         │
│ + 医学事实一致性 gate（强 gate + 弱 gate）│
│ + 轮数按格式分级                       │
└────────────────────────────────────────┘
```

---

## 3. 实施路线图

### 🔴 P0：本周，1-2 天（消除真实风险）

#### P0-1. 改写后医学事实一致性 gate（关键模块）

**问题**：`_validate_rewrite` 只检查长度，改写器把"小鼠研究"改成"人体研究"、"15%"改成"15-20%"、丢失 `[1]` 都不会被拦。

**架构设计：双 gate 分级**

| Gate 类型 | 字段 | 不一致后果 | 容忍度 |
|---|---|---|---|
| **强 gate**（致命错误） | `study_subjects`（小鼠/大鼠/人体/儿童/孕妇/老年） | 直接回退到原文 | 0 容忍 |
| **强 gate** | `citations`（`[文献N]/[N]/[共识]/[推断:]/[[待补充:]]`） | 直接回退 | 0 容忍 |
| **强 gate** | `dosage_phrases`（剂量数字 + 单位组合） | 直接回退 | 0 容忍 |
| **弱 gate**（打分） | `numbers`（归一化后比较） | 计算 diff 比例，超阈值回退 | 允许 ±5% 误差 |
| **弱 gate** | `drugs`（黑名单逻辑识别） | 集合 diff，超阈值告警 | 允许语义等价改写 |
| **弱 gate** | `years` / `time_anchors` | 同上 | 允许"2023年" vs "去年"等价 |

**新增模块**：`backend/app/services/enhancement/fact_guard.py`

```python
def extract_medical_facts(text: str) -> dict:
    """提取医学事实指纹。"""
    return {
        "study_subjects": [...],   # 强 gate：小鼠/大鼠/人体/儿童/孕妇/老年
        "citations": [...],        # 强 gate：[文献N]/[N]/[共识]/[推断:]/[[待补充:]]
        "dosage_phrases": [...],   # 强 gate：50mg/d、每天3次、每周2次
        "numbers_normalized": [...],  # 弱 gate：归一化数值（数字 + 标准单位）
        "drug_candidates": [...],     # 弱 gate：黑名单识别"看起来像药物的字符串"
        "years": [...],               # 弱 gate
    }

def normalize_number(s: str) -> tuple[float, str]:
    """归一化：'15%' / '15 percent' / '百分之十五' → (15.0, '%')
                '5 mg' / '5毫克' / '5 milligram' → (5.0, 'mg')
                '约 15%' / '15% 左右' / '大约 15%' → (15.0, '%')
                '三分之一' → (33.33, '%')  # 中文数字归一化
    """

def identify_drug_candidates(text: str) -> set[str]:
    """黑名单逻辑：识别'看起来像药物名'的字符串，不要求白名单覆盖
    规则示例：
      - 中文 2-6 字 + 后缀（片/胶囊/注射液/口服液/缓释片/分散片）
      - 英文药名模式（结尾 -ine/-ol/-mab/-pril/-sartan 等）
      - 用药剂量上下文（"服用XX"/"注射XX"/"XX的剂量"）
    """

def validate_facts_consistency(orig: str, rewritten: str) -> dict:
    """返回:
    {
      "passed": bool,                    # 是否通过整体 gate
      "hard_gate_failures": [...],       # 致命错误，必回退
      "soft_gate_warnings": [...],       # 警告，可放过
      "blocked_categories": [...],       # 触发的类别名
    }
    """
```

**集成位置**：`deai_rewriter.py` 的 `_validate_rewrite` 增加 `_validate_medical_facts(orig, new)` 调用。强 gate 失败 → 直接 `passed=False`，回退到原文。弱 gate 仅记录到 logger，不阻断。

**踩坑提示（必读）**：

1. **数字归一化是核心**：不能字符串严格比较。"约 15%" 改成 "15% 左右" 字符串不同但事实等价，必须归一化为 `(15.0, "%")` 后比较。否则拦截率会高得离谱。

2. **drugs 用黑名单逻辑**：医学文本药物表述太多样（通用名/商品名/中英文/缩写），白名单永远不全。改为"识别看起来像药物名的字符串集合，前后必须一致"。

3. **study_subjects 是最关键的强 gate**："小鼠研究"被改成"人体研究"是医学科普 AI 工具最容易犯的致命错误，也是最容易被监管和读者抓的把柄。这一项**0 容忍**。

**回退策略（已确认）**：拦截后**直接回退到原文，不重试**。理由：如果改写器第一次就敢改事实，说明它对这段内容理解有偏差，重试很可能犯同类错误。

**监控日志（必加）**：记录哪些段落、哪种事实类型被高频拦截，作为改进 P0-2 prompt 禁令清单的数据来源。

**验收标准**：
- 单元测试：手工构造 20 组"合法改写"（句式变化但事实保留）和 20 组"非法改写"（数字/药物/文献号被动），通过率 ≥ 95% / 拦截率 100%
- 集成测试：用之前肠道菌群样例跑改写，事实 0 篡改

---

#### P0-2. 改写器信息禁令（7 条硬约束）

**问题**：当前改写器 prompt 主要说"如何改"（更口语、节奏更好），没说"不能改什么"，模型有时会自作主张补充新数据。

**做法**：在 `rewrite_to_reduce_ai` 和 `rewrite_multi_pass` 的 system message 加 7 条硬约束：

```text
【改写禁令】（违反任何一条都视为不合格输出）
1. 禁止补充原文没有的具体数字、百分比、年份、人数
2. 禁止补充原文没有的药物名、机构名、研究名
3. 禁止改变研究对象（小鼠 vs 人体、儿童 vs 成人 等）
4. 禁止改变结论方向（"有效"不能改成"可能有效"或反之）
5. 禁止删除或重排 [文献N]、[共识]、[推断:]、[[待补充:]] 标注
6. 禁止改变限定词强度
   ✗ "可能有效" → "有效"
   ✗ "少数患者" → "部分患者"
   ✗ "罕见副作用" → "常见副作用"
   ✗ "建议" → "必须"
7. 你的任务是改写句式、节奏、连接词，不是补充信息

如有违反，将被自动检测并回退到原文。
```

**额外集成（重要）**：这套禁令同时写进**生成层 prompt**（`_PARAGRAPH_RHYTHM_RULES`），不只是改写器。生成阶段的 LLM 自己就经常做这种事（尤其是用通用大模型时），事前禁止比事后修补更稳。

**验收**：单跑一次回归测试，对比改写前后 fact_guard 拦截率应大幅下降（说明模型自觉性也在提升）。

---

#### P0-3. 风险词分级硬过滤

**问题**：prompt 里写了"禁止治愈率100%/根治"，但 LLM 不一定遵守，且没有事后硬阻断。法律风险。

**架构：分类型分级触发**

| 类别 | 命中后行为 | 理由 |
|---|---|---|
| **绝对化用语**（治愈率 100%/根治/包治） | 顶部 alert + 用户必须勾选"已知晓风险" | 措辞改一下就行，不应硬阻断 |
| **不当医疗承诺**（祖传秘方/神药/特效药） | 同上（必须勾选确认） | 同上 |
| **高风险决策建议**（具体剂量/手术方案/急救处置） | **直接阻断**，要求修改后才能继续 | 放出去就是医疗事故 |
| **处方药传播**（处方药 + "推荐服用"等组合） | **直接阻断** | 法律明确禁止 |
| **其他黄色风险**（新药/罕见病/心理疾病等） | 仅 toast 提示 | 信息提醒，不影响发布 |

**新增模块**：`backend/app/services/safety/risk_words.py`

```python
RED_LIST_HARD_BLOCK = {
    # 命中后直接阻断
    "high_risk_decision": [
        r"剂量(为|是|应该是|建议是)\s*\d+\s*(mg|g|ml|片|粒|μg)",
        r"(应该|建议|可以)\s*(立即\s*)?(手术|开刀)",
        r"自行\s*(注射|输液|手术|换药)",
        r"急性\s*\w+\s*(可以|建议|应该)",  # 急救处置
    ],
    "prescription_drug": [
        # 处方药通用名 + "推荐/建议服用/可以服用"组合
    ],
}

RED_LIST_REQUIRE_CONFIRM = {
    # 命中后顶部 alert + 必须勾选才能"标记可发布"
    "absolute_claims": [
        r"治愈率\s*[19]00%", r"100%\s*(治愈|有效|安全)",
        r"根治", r"彻底治愈", r"永不复发", r"立竿见影",
        r"绝对(安全|有效|无副作用)",
    ],
    "medical_promise": [
        r"包治", r"祖传秘方", r"神药", r"特效药",
    ],
}

YELLOW_LIST_TOAST_ONLY = {
    # 仅 toast 提示
    "rare_disease": [...],
    "psychiatric": [...],
    "new_drug": [...],
}
```

**集成**：
- `medcomm/generator.py` 在生成完成 + 改写完成后扫描
- 命中红色硬阻断 → 抛 `RiskWordBlockError`，前端弹"涉及高风险医学决策，请修改后重试"
- 命中红色需确认 → `report["risk_warnings"]` 记录，前端 alert 顶部置顶
- 命中黄色 → toast 提示

**红线词典治理（关键）**：
- 这个词典**必须有医学背景人**（医生/药师）参与定，不能只靠技术团队
- 短期参考：[国家卫健委](http://www.nhc.gov.cn/)、[国家药品监督管理局](https://www.nmpa.gov.cn/) 公开的"医疗广告违规典型案例"
- 长期可考虑接入第三方合规服务（阿里云内容安全、网易易盾），他们有维护好的医疗违规词库

**前端**：
- RightPanel 顶部 `<el-alert type="error">` 显示硬阻断
- `<el-alert type="warning">` 显示需确认
- 点击展开具体命中位置 + 定位到编辑器

**验收**：
- 手工构造"治愈率100%/包治癌症/剂量为50mg"等触发样本，全部命中并按级触发
- 跑历史 100 篇正常稿，误命中 ≤ 5%

---

### 🟡 P1：下个迭代，3-5 天

#### P1-1. 医学空洞度检测（concreteness_score）

**问题**：当前 `detect_ai_patterns` 检测"AI 味"，但没检测"段落是否言之有物"。一段话满是套话但没具体信息也是 AI 文本特征。

**做法**：新增独立维度，**不混入 AI 味主分**：

```python
def detect_concreteness(content: str) -> dict:
    paragraphs = [...]
    for para in paragraphs:
        score = {
            "has_number": bool(re.search(r"\d+(\.\d+)?\s*(%|mg|ml|kg|岁|年|周|天)", para)),
            "has_proper_noun": bool(...),       # 药物通用名、机构、期刊、指南
            "has_time_anchor": bool(...),       # 2023年/近三年/2010-2020
            "has_population": bool(...),        # 5岁以下儿童/孕妇/老年男性
        }
        # 段落得分 = 4 项中命中数 / 4
    return {
        "overall_score": ...,                   # 0-100
        "empty_paragraphs": [...],              # 4 项全 0 的段落（重灾区，含 char range）
        "weak_paragraphs": [...],               # 仅 1 项命中
    }
```

**关键决策**：**不基于这个分数自动改**。如果让改写器看到"信息密度低"就去补充信息，它一定会编造数据，医学科普就完蛋了。只展示给用户做参考，让用户去补充真实信息。

**前端展示要求**：
- RightPanel 新增"信息密度"卡片（独立于 AI 味）
- 空洞段落要**直接定位到编辑器对应位置**，而不只是给个总分。否则用户拿到"信息密度 45 分"也不知道改哪
- 后端返回 `empty_paragraphs[i]` 必须带 `char_range` 或段落 index

**验收**：肠道菌群样例 → 信息密度 ≥ 80（确实有数据），通用 GPT 套话稿 → ≤ 40

---

#### P1-2. 改写轮数按格式分级

**问题**：现在所有格式都跑 `rewrite_multi_pass` 2 轮，长稿合理、短稿浪费且漂移风险高。

**修订草案**（已结合反馈调整）：

```python
DEAI_REWRITE_ROUNDS = {
    # 长稿 / 严肃 / 多章节：2 轮（全文风格统一 + 段落精修）
    "contest_article": 2,
    "research_read": 2,
    "story": 2,
    "qa_article": 2,    # ← 修正：Q&A 类 AI 味问题最严重（"首先...其次...希望以上回答对您有所帮助"），需要 2 轮
                        #    第 1 轮聚焦"打破 Q&A 模板"，第 2 轮做段落精修
    
    # 中等：1 轮（仅段落精修）
    "debunk": 1,
    
    # 脚本类：1 轮（口语化场景，事后改写边际收益低）
    "video_script": 1,
    "audio_script": 1,
    
    # 默认 1 轮
}

def get_deai_rewrite_rounds(content_format: str) -> int:
    return DEAI_REWRITE_ROUNDS.get(content_format, 1)
```

**数据驱动后续校准**：上线 P0 后，记录 2 轮改写中**第 2 轮带来的 AIGC 分下降幅度**。如果某格式第 2 轮平均只能再降 3-5 分，移到 1 轮；如果能降 ≥ 15 分，保留。这个校准应该作为 P1-2 上线后第 2 周的回顾任务。

**验收**：短稿延迟下降 30-40%（少一次 LLM 调用）；长稿行为不变。

---

#### P1-3. 段落 [AI 优化] 标记 + diff 入口（产品价值最高项，建议提速）

**优先级提示**：这一项的**产品价值远超技术价值**。机构客户（医院、药企、健康自媒体公司）有"内容审核"流程，diff 视图可以直接对接他们的审核工作流，是 to B 销售时一个非常具体的卖点。**如果前端工作量不大，可以提到 P0-3 之后立刻做**。

**做法**：

后端：`generator.py` 在 `report` 里增加 `rewritten_segments`：
```python
report["rewritten_segments"] = [
    {"index": 0, "before": "...", "after": "...", "char_range": [start, end]},
    ...
]
```

前端 RightPanel：
- 段落级 badge `<el-tag size="small" type="info">AI 优化</el-tag>`
- 点击 badge 弹出 `<el-dialog>` 显示左右对比 diff（推荐 [diff2html](https://github.com/rtfpessoa/diff2html) 或 [vue-code-diff](https://github.com/Shimada666/v-code-diff)）
- 提供"恢复改写前"按钮（单段恢复，不全文回滚）

**验收**：用户可以肉眼审查每一段被改了什么，并能选择性恢复。

---

#### P1-4. 语义一致性 gate（重新评估，优先级降低）

**成本与延迟重评**：
- 延迟：同步调用增加 3-5 秒，长稿出稿时间显著增加。在"一键成文"的产品定位下，可能影响体验
- 成本：假设日生成 10000 篇长稿 × 5K tokens × deepseek-chat 单价，**月成本 几千到一万元**，不是"几厘/篇"那么轻

**修订策略**：
1. **先做 P0-1 的纯规则 gate，跑 2-4 周看事实准确率**
2. 如果 P0-1 准确率已经 ≥ 99%，**P1-4 不做**
3. 如果准确率不够，**降级为异步抽检**：
   - 随机抽 10% 的改写后内容跑一致性检查
   - 用于持续监控（看检测器是否失效），不阻断流程
   - 异步任务，不影响生成时长

**降级方案**：

```python
# 改写完成后，10% 概率投递到异步队列
if random.random() < 0.1:
    asyncio.create_task(_async_semantic_consistency_check(orig, rewritten, content_id))

# 异步任务把不一致的样本写到数据库 + 告警通道
async def _async_semantic_consistency_check(orig, rewritten, content_id):
    result = await llm_call(SEMANTIC_CHECK_PROMPT, ...)
    if result == "no":
        logger.warning(f"semantic drift detected: {content_id}")
        await save_drift_sample(content_id, orig, rewritten)
```

---

### 🟢 P2：v2，需要业务决策

#### P2-1. 引用增强（**调研立即启动**）

**为什么要提前**：医学科普工具最大的差异化护城河是**真实指南引用**。竞品都在卷"AI 味"，如果生成内容自带真实指南引用（[1] 中华医学会 XX 指南 2023 版），用户的感知差异是数量级的。指南库接入往往周期很长（要谈授权、要做数据清洗、要建检索系统），晚启动 3 个月就晚 3 个月。

**短期 hack（在指南库接入前）**：
- 让 LLM 在生成时标注"根据 XX 指南"，但用 `[[待核实]]` 标记
- 让用户自己去查证后替换为真实引用
- 这是 hack，但能先把产品形态跑通，验证用户对"带引用"的需求

**调研重点**（业务侧）：
- 中华医学会指南库（中文权威）
- UpToDate（国际权威，付费）
- 丁香园专业版（中文付费）
- PubMed（免费，英文）
- 国家药品监督管理局药品说明书数据库

#### P2-2. 专业 / 通俗模式分流

按 `audience_type`（公众/患者/医生/学生）用不同 prompt 模板。需要业务侧确认两类用户行为差异是否显著到值得分流。

#### P2-3. 用户反馈与 diff 沉淀机制（**v1.1 新增项**）

**为什么必须加**：当前所有质量评估都是**内部指标**（检测分、事实一致率、误命中率）。但医学科普的最终质量判断者是**读者和领域专家**。

**做法**：
1. 用户最终发布或导出文章时，弹一个轻量级评价（1 个问题："这次生成质量如何？"）
2. 如果用户对某些段落做了**手动修改**，记录"AI 生成版本 vs 用户最终版本"的 diff
3. 数据存入新表 `user_edit_diffs`

**数据资产价值**：
- 分析用户最常改哪类内容（信号：AI 生成的薄弱环节，反哺 prompt 优化）
- 训练改写器（v3 改写器微调的来源）
- 做 case study 优化检测器规则

**实施成本极低，但越早开始积累价值越大。建议从 P1 阶段就开始埋点收集，不要等 P2。**

#### P2-4. 改写器"恢复 AI 原版" 全文按钮

P1-3 已经做了段落级恢复，全文级别再补一个开关。优先级低。

#### P2-5. 风险词分级升级到三级

红/黄/绿三级 + 黄色"建议人工审"弹窗。在 P0-3 红色基础上扩展。

---

### ⚫ 不做项

> 这一节单独维护于 [`decisions/不做项清单.md`](decisions/不做项清单.md)，作为新人入职第一天必读，避免重复发起已经讨论过的方案。

| 不做项 | 原因 |
|---|---|
| 7B 微调改写器 | 短期 ROI 低，需先有数据沉淀（见 P2-3） |
| 医学专用模型替换通用大模型 | 我们 RAG 模式下事实准确性反而更高，专用模型指南滞后 |
| Grammarly 半自动逐句确认形态 | 偏离医生用户"快速可发布"的核心需求 |
| 实时 PPL / LLM 判别器 | 检测层已经够准（30/74/100 分布），不值得加复杂度 |

**保留口子**：用 LLM 判别器做**周期性离线评测**（每周抽样 100 篇，用 GPT-4o 或 Claude 跑"AI vs 人"判断），作为检测器准确率的**外部基准线**。这个不影响线上性能，但能告诉你检测器有没有失效。这个**不算"做"，是定期监控**。

---

## 4. 风险与回滚预案

> 这一节单独维护于 [`runbook/AIGC回滚预案.md`](runbook/AIGC回滚预案.md)，作为运维 oncall 手册的一部分。

| 风险 | 缓解 | 回滚 |
|---|---|---|
| medical_fact_guard 强 gate 误判，改写经常被回退 | 误判即回退到原文，AI 味分不变但事实零风险（可接受） | feature flag `ENABLE_FACT_GUARD_HARD` |
| medical_fact_guard 弱 gate 误判 | 仅打日志不阻断 | feature flag `ENABLE_FACT_GUARD_SOFT` |
| 风险词硬阻断误伤合法内容 | (a) 红色仅记录不阻断的 fallback；(b) 用户申诉通道；(c) 词典版本控制（哪些词加了能查） | feature flag `ENABLE_RISK_WORD_HARD_BLOCK` |
| 改写轮数分级配置错 | 通过 `DEAI_REWRITE_ROUNDS` 单文件改 | 配置秒级回滚 |
| 语义一致性 gate（异步版）调用失败 | 失败时默认通过（fail-open），记录到 logger.warning | 自动 |

---

## 5. 关键指标与评估

发布前必须人工标注一组 baseline：

| 指标 | 测量方法 | 目标 |
|---|---|---|
| AIGC 主分分布合理性 | 人工标注 100 篇分清洁/中等/重 AI 味，比对分数 | 三档区分度 ≥ 70 分 |
| 医学事实一致率 | 强 gate 通过率 + 人工抽 50 篇核对 | ≥ 99% |
| 改写前后字数变化 | 自动统计 | ±20% 内 |
| 高风险词命中精确率 | 人工标注 100 篇 | precision ≥ 90% |
| 用户"标记可发布"接受率 | 产品埋点 | baseline → 监控 |
| 用户手动改稿比例 | P2-3 埋点 | baseline → 监控 |
| 改写延迟 | 后端日志 | 短稿 -30% |
| 周期性离线 LLM 判别器准确率 | 每周抽样 100 篇 | 与主分相关性 ≥ 0.6 |

---

## 6. 推荐执行顺序

```
本周（P0）:
  Day 1 上午: P0-2 改写器信息禁令（30 分钟，仅改 prompt）
  Day 1 下午: P0-1 fact_guard 模块骨架（study_subjects / citations 强 gate 优先）
  Day 2:      P0-1 数字归一化 + 集成 _validate_rewrite + 单元测试
  Day 3:      P0-3 风险词分级清单 + 后端扫描
  Day 4:      P0-3 前端 alert / 阻断 / toast 集成 + 联调

下周（P1）:
  Day 1-2: P1-1 concreteness 检测器 + 前端定位
  Day 3:   P1-2 改写轮数分级 + 回归测试
  Day 4-5: P1-3 段落 [AI 优化] 标记 + diff 前端

P1 上线 2 周后：
  - 评估 P1-4 是否需要（看 P0-1 准确率）
  - 评估 P1-2 各 content_format 实际收益（数据驱动校准）
  - 启动 P2-1 引用增强调研（业务侧并行）
  - 启动 P2-3 用户反馈埋点（开发侧）
```

---

## 7. 文档分发

本方案在仓库内的多处副本/精简版：

| 文件 | 用途 | 受众 |
|---|---|---|
| `docs/AIGC治理可执行方案_v1.1.md`（本文件） | 完整方案 | 项目负责人 / 工程主导 |
| `docs/principles/AIGC原则.md` | 5 条核心原则 | PR review 时对照 |
| `docs/decisions/不做项清单.md` | 已否决方案 + 理由 | 新人入职必读 |
| `docs/runbook/AIGC回滚预案.md` | feature flag + 回滚步骤 | oncall / 运维 |

---

## 8. 修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| v1.0 | 2026-05-01 | 初版 |
| v1.1 | 2026-05-01 | 整合反馈：P0-1 双 gate 分级（强/弱）+ 数字归一化 + drugs 黑名单逻辑；P0-2 加第 7 条限定词禁令；P0-3 风险词分类型分级触发（绝对化用语→需确认 / 高风险决策→直接阻断）；P1-2 qa_article 改 2 轮；P1-4 重评成本延迟，降级为异步抽检；P2-1 引用增强提前调研；P2-3 新增用户反馈与 diff 沉淀机制；新增"周期性离线 LLM 判别器"作为外部基准线。 |
| v1.1.1 | 2026-05-01 | 追加附录 A：P0-1 / P0-2 / P0-3 共 22 项最终设计决策（开工前最后一次拍板，所有实现细节以本附录为准）。 |

---

## 附录 A：P0 阶段 22 项最终设计决策

> 本附录是 P0 开工前的最终拍板清单。任何实现细节与本附录冲突时，以本附录为准。
> 决策日期：2026-05-01。决策人：项目负责人 + 工程主导。

### A.1 fact_guard 数字归一化（N1, N2）

| ID | 决策 | 实现细节 |
|---|---|---|
| **N1** | "约 / 大约 / 大致 / 差不多 / 近 / 接近 / 约莫 / 左右 / 上下 / 前后" 全部合并为同一模糊估算等价类 | `normalizers/modifier_words.py` 中 `MODIFIER_EQUIVALENCE_CLASSES` 第一个集合即模糊估算类，前置和后置统一 |
| **N2** | 分数与百分比 P0 严格不互换（"三分之一" ≠ "33%"），但代码预留 `fraction_tolerance` hook 供 P1 升级到分级处理 | `numbers_consistent(orig, rewritten, *, fraction_tolerance: float = 0.0)` 接口签名 P0 上线时 `tolerance=0` 严格；1-2 周后看误报数据决定是否升级到 0.005 启用同精度等价 |

### A.2 fact_guard study_subjects（S1-S6）

| ID | 决策 | 实现细节 |
|---|---|---|
| **S1** | "年" 与 "岁" 拆分为 `year` / `age` 两个独立单位 | `UNIT_ALIASES` 中 `"年" → "year"`、`"岁"/"周岁" → "age"`；月份 / 月龄 P0 不拆分 |
| **S2** | 独立 `IN_VIVO_AMBIGUOUS` 类别 + 同段消解规则 | "in vivo"、"在体内"等归该类；如同段已出现明确 ANIMAL 或 HUMAN 词，AMBIGUOUS 项被消解，不参与一致性判断 |
| **S3** | 不收录英文 `subject` | 英文 "subject" 含义太泛，漏判优于误判；信任改写器禁令 R3 + R4 双重保护 |
| **S4** | `HUMAN_PATIENTS` 仅识别"患者 / 病人 / 病患"等泛指词 | "高血压患者 / 糖尿病患者"等疾病限定的细分推迟到 v0.2 |
| **S5** | "受试者" / "志愿者" 不拆分，都归入 `HUMAN_GENERAL` | 中文医学文本两者经常混用；研究阶段（I/II/III 期）改用单独的"临床试验阶段一致性"维度，未来按需求加 |
| **S6** | 词典冲突启动报错 + 单元测试兜底 | `_build_term_to_layer2()` 检测重复 key 时直接 `raise ValueError`；增加 `test_dictionary_no_conflict` 测试 |

### A.3 fact_guard citations（C1）

| ID | 决策 | 实现细节 |
|---|---|---|
| **C1** | `[文献N]` 和 `[N]` 双语法都识别；用前后否定环视排除化学式 / 数学符号 | `LITERATURE_PATTERN` 优先匹配 `[文献N]`；`SIMPLE_NUM_PATTERN` 加 `(?<![A-Za-z+\-])` 前置否定和 `(?![+\-])` 后置否定避免 `[H+]`、`[Cl-]` 误识别 |

### A.4 fact_guard dosage（D1）

| ID | 决策 | 实现细节 |
|---|---|---|
| **D1** | 拆分为 `dosage_amounts`（弱 gate）+ `dosage_schedules`（强 gate） | amounts 走数字归一化通道；schedules 用整体匹配捕获频率（"每天 3 次"）/ 时长（"疗程 7 天"）/ 时机（"睡前 / 餐后"）作为不可拆分的整体 |

### A.5 fact_guard drugs（G1, G2）

| ID | 决策 | 实现细节 |
|---|---|---|
| **G1** | `drugs` gate 强弱级别：弱 gate | 仅记录 diff 不阻断，避免药物词典不全导致大量误报 |
| **G2** | `drugs` 模块推迟到 P0.5 启用 | P0 阶段配置 `ENABLE_FACT_GUARD_DRUGS = False`；P0-2 改写器禁令第 2 条 + 生成层禁令同时强化 "禁止补充原文没有的药物名" |

### A.6 fact_guard 集成（I1, I2）

| ID | 决策 | 实现细节 |
|---|---|---|
| **I1** | 默认短路 + 通过 `full_scan` flag 支持全量模式 | `validate_facts_consistency(..., full_scan: bool = False)`；生产 `FACT_GUARD_FULL_SCAN=False`（短路，性能好）；灰度期与离线分析脚本 `True`（全量收数据） |
| **I2** | 引入 `GateResult.PASS_BY_FAIL_OPEN` 单独状态 | `FactCheckResult.passed` 同时承认 `PASS` 和 `PASS_BY_FAIL_OPEN`；`is_normal_pass` 仅承认 `PASS`；`FactGuardSummary` 单独统计两者比例，监控 `PASS_BY_FAIL_OPEN > 1%` 即告警 |

### A.7 fact_guard 节奏（P1）

| ID | 决策 | 实现细节 |
|---|---|---|
| **P1** | 阶梯式上线：Week 1-2 dry_run + full_scan / Week 3 切 hard_block + 短路 | 由 `FACT_GUARD_HARD_BLOCK` 与 `FACT_GUARD_FULL_SCAN` 两个 flag 联合控制；Day 7 必须做三指标评估（拦截率 5-15% / P0-2 让拦截率降幅 ≥ 50% / 抽 50 case 准确率 ≥ 95%）任一不达标推迟切换 |

### A.8 P0-2 改写器 prompt（R1, R2, R3）

| ID | 决策 | 实现细节 |
|---|---|---|
| **R1** | 多轮改写第 2 轮只给原文，不给上一轮结果 | 第 2 轮 user prompt 明示"这是第 2 轮，但你看到的是原文，重点做句式微调"避免改动量过激；A/B/C 三组对比验证（100 段 × 3 配置）放 P0 上线后第 2 周做，不阻塞上线 |
| **R2** | P0-1 与 P0-2 配对发布 | Day 3 同时上线；Day 7 三指标评估通过才切 `FACT_GUARD_HARD_BLOCK=True` |
| **R3** | 抽共享禁令模块（生成 + 改写共用） | 文件 `backend/app/agents/prompts/fact_preservation_rules.py`；导出 3 个常量：`FACT_PRESERVATION_RULES`（描述式，给生成层）/ `REWRITE_FACT_RULES`（命令式，给改写层）/ `REWRITE_VIOLATION_EXAMPLES` + `REWRITE_LEGAL_EXAMPLES`（仅改写层用） |

### A.9 P0-3 风险词（K1, K2, K3）

| ID | 决策 | 实现细节 |
|---|---|---|
| **K1** | P0 阶段全部 CONFIRM，不做 BLOCK；引入 `CONFIRM_HARD` / `CONFIRM_SOFT` 视觉分级 | 自行注射放 `CONFIRM_HARD`（红色 + 必须勾选）；其他放 `CONFIRM_SOFT`（橙色 + 必须勾选）；`BLOCK` 在枚举中保留但 P0 不实际触发，等 P1 数据驱动升级 |
| **K2** | 处方药模糊匹配规则改为 `LOG_ONLY` + 否定环视 + 警示语境二次过滤 | 引入 `NEGATION_PREFIXES`（不/避免/禁止/切勿/严禁等）和 `WARNING_CONTEXTS`（风险/危险/副作用等）；处方药规则 P0 仅后端日志、不展示用户，1 个月后看数据决定是否升级 WARN |
| **K3** | WARN 默认全开；UI 默认折叠 | CONFIRM 永远展开；WARN 折叠状态由 localStorage 持久化；提供"关闭此类提示"按钮（存用户设置）；埋点 WARN 展开率 / 处理率 / 屏蔽率 |

### A.10 ActionLevel 最终枚举

```python
class ActionLevel(Enum):
    BLOCK = "block"                # P1 启用，P0 注册但不实际触发
    CONFIRM_HARD = "confirm_hard"  # 红色 + 必须勾选才能发
    CONFIRM_SOFT = "confirm_soft"  # 橙色 + 必须勾选才能发
    WARN = "warn"                  # 黄色 + UI 默认折叠
    LOG_ONLY = "log_only"          # 仅后端日志，不展示给用户
```

### A.11 灰度时间线（双 flag 联动）

```
Week 1-2 (dry_run)  : FACT_GUARD_HARD_BLOCK=False  +  FACT_GUARD_FULL_SCAN=True
                     P0-1 跑全维度只记录不阻断；P0-2 prompt 已替换；P0-3 全 CONFIRM
                     Day 7 三指标评估
Week 3 (hard_block) : FACT_GUARD_HARD_BLOCK=True   +  FACT_GUARD_FULL_SCAN=False
                     P0-1 真实启用阻断 + 短路性能模式
P0+2 周             : 跑 P0-2 的 A/B/C 三组对比；评估是否升级 N2 分级处理
P0+1 月             : 评估处方药 LOG_ONLY 数据；决定升级 WARN 或保持
```

### A.12 不做项（22 项决策中明确否决的）

- ❌ 月份 / 月龄拆分（P0 只拆年/岁）
- ❌ 英文 "subject" 收录（漏判优于误判）
- ❌ "受试者" / "志愿者" 拆分
- ❌ 疾病限定的 `HUMAN_PATIENTS` 细分（P0 只识别泛指）
- ❌ `drugs` 强 gate（P0 弱 gate，P0.5 再启用模块）
- ❌ 风险词 `BLOCK` 实际触发（P0 全 CONFIRM，P1 数据驱动升级）
- ❌ 处方药规则展示给用户（P0 `LOG_ONLY` 收数据）

---

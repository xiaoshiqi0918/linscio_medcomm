# AIGC 治理 Runbook & 回滚预案

> **用途**：oncall 工程师在 AIGC 相关功能出现线上问题时的应急手册。
> **完整方案**见 [`../AIGC治理可执行方案_v1.1.md`](../AIGC治理可执行方案_v1.1.md)。

---

## 1. Feature Flags 总览

所有 AIGC 治理功能必须通过 feature flag 控制，便于秒级回滚。Flag 配置位置：
- 后端：`backend/app/core/config.py` 的 `Settings` 类
- 环境变量：`deploy/.env.production`

| Flag | 默认值 | 控制对象 | 关闭后行为 |
|---|---|---|---|
| `ENABLE_FACT_GUARD_HARD` | `True` | 改写后强 gate（study_subjects / citations / dosage） | 改写后不做事实强校验，回到旧的"仅长度校验"模式 |
| `ENABLE_FACT_GUARD_SOFT` | `True` | 改写后弱 gate（数字归一化 / 药物候选） | 不打 warning 日志 |
| `ENABLE_RISK_WORD_HARD_BLOCK` | `True` | 风险词硬阻断（高风险决策 / 处方药） | 命中后仅记录到 `report["risk_warnings"]`，不阻断生成 |
| `ENABLE_RISK_WORD_CONFIRM` | `True` | 风险词需确认（绝对化用语 / 不当承诺） | 命中后仅 toast，不要求勾选 |
| `ENABLE_CONCRETENESS_DETECT` | `True` | 医学空洞度检测（P1-1） | 不计算、不展示 |
| `ENABLE_DEAI_REWRITE_FORMAT_ROUNDS` | `True` | 改写轮数按格式分级 | 全格式统一 2 轮（旧行为） |
| `ENABLE_SEMANTIC_GATE_ASYNC` | `False` | 异步语义一致性抽检（P1-4） | 不抽检 |

---

## 2. 常见故障与回滚步骤

### 故障 A：改写器频繁回退到原文（fact_guard 强 gate 误判）

**症状**：
- 监控告警：`fact_guard.hard_gate_failure_rate > 30%`
- 用户反馈："AI 味检测分一直没下降"
- 日志大量 `WARNING: fact_guard hard gate failed: study_subjects mismatch`

**应急回滚（5 分钟）**：

```bash
# 1. 临时关闭强 gate
# 在 deploy/.env.production 设置：
ENABLE_FACT_GUARD_HARD=false

# 2. 重启后端服务
sudo systemctl restart linscio-backend

# 3. 观察 5 分钟，确认改写恢复正常
tail -f /var/log/linscio/backend.log | grep "fact_guard"
```

**根因分析（24 小时内）**：
1. 拉出最近 100 条 hard gate 失败日志
2. 检查是哪一类 fact 被误判（study_subjects / citations / dosage）
3. 判断是：
   - (a) `extract_medical_facts` 提取规则有 bug → 修代码
   - (b) `normalize_number` 归一化漏了某种表达 → 加规则
   - (c) 改写器确实在改事实 → 修 prompt（P0-2 的 7 条禁令）

**重新打开**：修复后通过 feature flag 灰度（先 10% 流量验证 24h，再 50%，再 100%）。

---

### 故障 B：风险词硬阻断误伤合法内容

**症状**：
- 用户反馈："明明在写就医建议，被识别为高风险阻断"
- 客服工单激增

**应急回滚（5 分钟）**：

```bash
# 关闭硬阻断，降级为"仅记录"
ENABLE_RISK_WORD_HARD_BLOCK=false

sudo systemctl restart linscio-backend
```

**根因分析**：
1. 拉取被阻断的样本
2. 检查是哪条正则误命中（`backend/app/services/safety/risk_words.py` 的 `RED_LIST_HARD_BLOCK`）
3. 修正正则边界（通常是上下文敏感问题，如"建议手术" vs "建议咨询医生是否需要手术"）

**重新打开**：在 `RED_LIST_HARD_BLOCK` 加 negative lookahead 排除合法上下文，然后灰度。

---

### 故障 C：改写后语义漂移（P1-4 异步抽检告警）

**症状**：
- 异步抽检告警：`semantic_drift_rate > 5%`
- 数据库表 `semantic_drift_samples` 大量新样本

**这不是紧急故障**（异步抽检不阻断流程），但需要 24 小时内响应。

**响应流程**：
1. 拉出 drift 样本，人工抽 20 条核对
2. 分类：
   - (a) 异步检查器误判 → 调整 P1-4 prompt
   - (b) 改写器确实在飘 → 加强 P0-2 禁令 + 重新校验 P0-1 fact_guard 是否漏了某类
3. 如果漏率 > 10%，临时关闭对应格式的改写：
   ```python
   # 在 registry.py 临时把某 content_format 加入 SKIP_DEAI_REWRITE_FORMATS
   SKIP_DEAI_REWRITE_FORMATS = {..., "qa_article"}  # 临时禁用
   ```

---

### 故障 D：检测器分数突然全员 100 分（检测器失效）

**症状**：
- 离线 LLM 判别器与线上 AIGC 主分相关性 < 0.3（每周报表）
- 用户反馈："AI 味检测不准了"

**这是检测器规则失效信号**（GPT 模板词换代了，规则没跟上）。

**响应流程**：
1. 抽取最近 1 周 AIGC 主分 ≥ 90 但人工标注为"重 AI 味"的样本
2. 提取共同特征（新出现的高频词 / 新句式 / 新结构模板）
3. 在 `detect_ai_patterns` 加新规则
4. 上线前用旧测试集回归（确保新规则不误伤）

**应急措施**：暂时降低 AIGC 主分阈值（前端 `aigcSummaryTagType` 计算公式），让"通过"标准更严，争取修复时间。

---

## 3. 词典更新流程

### 风险词 RED_LIST 更新

**频率**：建议每月一次。

**流程**：
1. 拉取 [国家药品监督管理局违规通报](https://www.nmpa.gov.cn/) 最近 30 天
2. 拉取 [国家卫健委医疗广告违规典型案例](http://www.nhc.gov.cn/) 最近 30 天
3. 由医学背景人（医生 / 药师）评估新增词条
4. 提交 PR：`backend/app/services/safety/risk_words.py`
5. 必须有至少 1 名医学背景 reviewer + 1 名工程 reviewer

**第三方词库接入（可选）**：
- 阿里云内容安全（医疗场景）
- 网易易盾（医疗合规）
- 接入后做并集，命中任一即触发

### AI 味检测规则 `_ISSUE_PATTERNS` 更新

**频率**：每季度一次回顾，或检测器失效时（故障 D）触发。

**流程**：
1. 抽取最近 1 季度 AIGC 主分 ≥ 90 但用户人工改稿率高（diff 数据，见 P2-3）的样本
2. 共同特征提取
3. 提交 PR：`backend/app/services/verification/pipeline.py`
4. 必须用历史测试集回归验证（不能让旧规则失效）

---

## 4. 监控指标与告警阈值

### 必须监控的指标

| 指标 | 数据源 | 告警阈值 |
|---|---|---|
| `fact_guard.hard_gate_failure_rate` | 后端日志聚合 | > 30%（持续 1h） |
| `risk_word.hard_block_rate` | 后端日志聚合 | > 10%（持续 1h） |
| `risk_word.hard_block_user_appeal_rate` | 客服工单 | > 5%（每日） |
| `aigc_score_distribution` | DB report 表聚合 | 90+ 分占比 > 80%（每日） |
| `semantic_drift_async_rate` | 异步抽检表 | > 5%（每日） |
| `rewrite_latency_p95` | 后端日志 | > 60s（每小时） |
| `weekly_offline_judge_correlation` | 每周离线评测 | < 0.6 |

### 告警通道

- 即时告警（5 分钟级）：飞书群 / 企微群 + on-call 电话
- 日报：邮件汇总
- 周报：含离线 LLM 判别器评测结果

---

## 5. 应急联系人

| 角色 | 职责 |
|---|---|
| 工程主导 | 决定是否回滚、是否上线修复 |
| 医学顾问 | 评估词典 / 规则的医学合理性 |
| 法务 | 评估合规风险（涉及法律红线时） |
| 运营 | 处理用户申诉工单 |

> 实际联系人列表见公司内部文档（不放在仓库 git 历史里）。

---

## 6. 修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| v1.0 | 2026-05-01 | 初版（与方案 v1.1 同步） |

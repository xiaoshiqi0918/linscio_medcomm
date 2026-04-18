# Layer 1 — 形式族规则与受众补丁

> **装配位置**：System 消息后半段
> **优先级**：在 Layer 0 框架内追加体裁/受众专属约束，不可削弱 Layer 0 规则

---

## 文件结构

| 文件 | 触发条件 | 说明 |
|------|---------|------|
| `anti_hallucination.txt` | 始终加载 | 通用防编造十条（polishing 链路使用） |
| `visual_anti.txt` | 图示类体裁 | 漫画/长图/海报等视觉内容附加规则 |
| `script_anti.txt` | 脚本类体裁 | 口播稿/情景剧本等附加规则 |
| `children_audience_patch.txt` | audience=children | 儿童受众专属规范 |

---

## children_audience_patch.txt 章节概览

| 章节 | 内容 |
|------|------|
| § 1 | 目标读者 — 默认 6-8岁，含 3-5 / 6-8 / 9-12 三档差异指引 |
| § 2 | 语言标准 — 句长、词汇、类比素材、因果表达规范 |
| § 3 | 儿童安全专属禁止项 — 视觉恐吓、危险表述、抽象概念 |
| § 4 | 风格锚定 — "大哥哥/大姐姐讲故事"语感示例 |

---

## 加载逻辑

```python
# audiences.py 中根据 audience 参数决定是否追加
if target_audience == "children":
    system_prompt += load_children_audience_patch()
```

---

## 扩展方向

各 `content_format` 的形式族专属规则仍主要在 `anti_hallucination.py` 代码中；可按需拆分为 `layer1/formats/*.txt` 并逐步接入 loader。

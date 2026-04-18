# 去 AI 化改写

| 文件 | 说明 |
|------|------|
| `rewrite_full.txt` | 第 1 轮全文改写（user，含 `{content}`） |
| `opening.txt` | 开头段改写（`{problem_description}` `{paragraph}`） |
| `ending.txt` | 结尾段改写 |
| `paragraph.txt` | 一般段落改写（`{style_instruction}`） |
| `system_override.txt` | **可选**：非空时**整段替换**动态 system（含风格注册表）；留空则使用代码中的 `_build_deai_system_prompt` |
| `system_static.txt` | 旧版静态 system 文案备份，默认不参与加载；以 `system_override` 为准 |

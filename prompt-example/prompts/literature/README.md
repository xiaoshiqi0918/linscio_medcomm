# 文献分析 — System 提示词

| 文件 | 代码回退常量 | 用途 |
|------|----------------|------|
| `analysis_single.txt` | `ANALYSIS_SYSTEM_PROMPT` | 1–2 篇文献单次分析 |
| `per_paper.txt` | `_PER_PAPER_SYSTEM_PROMPT` | MapReduce Map 阶段单篇精读 |
| `synthesis.txt` | `_SYNTHESIS_SYSTEM_PROMPT` | MapReduce Reduce 综合 |

由 `loader.load_literature_*` 读取；文件为空或缺失时使用代码内嵌回退。

"""
验证与核实 Agent 提示词
用于医学声明核实、数据占位符检测、阅读难度分析（可接入 LLM）
优先从 prompt-example/prompts/verification/ 加载
"""
from app.agents.prompts.loader import load_verification, load_writing_sop

_SOP_EVIDENCE_RULES = """
【依据《医学科普文章写作与出版专家共识》的证据使用标准】
· 引用来源优先级：政府标准 > 权威机构指南 > 学术期刊论著 > 行业共识
· 根据证据级别使用程度副词：高质量→"研究表明"；中等→"很可能/研究提示"；低质量→"可能/初步显示"；存疑→"尚不确定/有待研究"
· 不得将存疑证据表述为确定性结论
· 不得将孤立或有限证据推广为普遍规律
· 不得包含具体用药剂量或个性化治疗方案
""".strip() if load_writing_sop() else ""

_DEFAULT_CLAIM_VERIFY = """请核查以下医学科普内容中的医学声明。

【待核查内容】
{content}

【可用参考资料（来自 RAG 检索）】
{rag_context}

""" + (_SOP_EVIDENCE_RULES + "\n\n" if _SOP_EVIDENCE_RULES else "") + """【核查任务】
提取内容中所有医学事实性声明，对照参考资料进行核查。

【verification_status 判断标准（量化）】
verified：参考资料中有直接支持该声明的内容，且两者方向一致
unverified：参考资料中无相关内容，但声明本身不违反基本医学常识
conflicting（满足其一即认定）：①数值相差>20% ②结论方向相反 ③适用人群完全不同（儿童≠成人）

【confidence 判断标准】
high：参考资料来自指南或系统综述，且声明与资料完全一致
medium：参考资料来自队列研究/病例对照，或声明与资料部分一致
low：参考资料来自单个病例报告/专家意见，或资料较旧（>5年）

【输出格式（合法JSON）】
{{
  "claims": [
    {{
      "claim_text": "声明原文（≤60字）",
      "claim_type": "数据声明|机制声明|效果声明|症状声明|建议声明",
      "verification_status": "verified|unverified|conflicting",
      "supporting_source": "支撑来源摘要（≤40字）或空字符串",
      "confidence": "high|medium|low",
      "conflict_detail": "若conflicting，说明矛盾具体内容（≤40字）；否则为空"
    }}
  ],
  "overall_assessment": "overall_safe|needs_review|has_issues",
  "has_issues_count": 0
}}
overall_assessment：overall_safe=无conflicting且unverified≤3；needs_review=无conflicting且unverified>3；has_issues=有conflicting

请直接输出JSON。
"""

CLAIM_VERIFY_PROMPT = load_verification("claim_verify") or _DEFAULT_CLAIM_VERIFY

_DEFAULT_FACT_VERIFY = """请检查以下医学科普内容，识别需要处理的数据和表述问题。

【已通过RAG验证的数据（豁免，不需要标注）】
{verified_data_list}

【待检查内容】
{content}

""" + (_SOP_EVIDENCE_RULES + "\n\n" if _SOP_EVIDENCE_RULES else "") + """【检测规则（按严重程度分级）】
HIGH：①具体剂量（mg/ml/毫克/毫升/片/粒/滴+数字）→specific_dosage ②绝对化表述（一定会/必然/绝对/百分之百/完全可以根治/永久有效/从不、只要…就能治愈）→absolute_statement
MEDIUM：医学统计数据无来源（百分比/患病率/治愈率+具体数字）→unverified_data，verified_data_list中已有则豁免
LOW：疑似引用（据《XX》/根据XX研究/XX指南指出）无RAG支撑→potential_unsourced_citation

【输出格式（合法JSON）】
{{
  "data_warnings": [
    {{
      "original_text": "原文片段（≤40字）",
      "warning_type": "specific_dosage|unverified_data|potential_unsourced_citation",
      "severity": "high|medium|low",
      "trigger_word": "触发该警告的关键词/数字",
      "suggestion": "建议的处理方式（≤30字）"
    }}
  ],
  "absolute_terms": [
    {{
      "original_text": "含绝对化表述的原文（≤40字）",
      "problematic_word": "具体的问题词汇",
      "suggested_replacement": "建议的替换表述（≤20字）"
    }}
  ],
  "high_count": 0,
  "medium_count": 0
}}

请直接输出JSON。
"""

FACT_VERIFY_PROMPT = load_verification("fact_verify") or _DEFAULT_FACT_VERIFY

# 受众 → 术语密度上限、建议句长（供 READING_LEVEL_PROMPT 注入）
AUDIENCE_LEVEL_SPECS = {
    "public": {"max_term_density": 0.15, "max_sentence_len": 25},
    "patient": {"max_term_density": 0.25, "max_sentence_len": 30},
    "student": {"max_term_density": 0.35, "max_sentence_len": 40},
    "professional": {"max_term_density": 1.0, "max_sentence_len": 999},
    "children": {"max_term_density": 0.10, "max_sentence_len": 15},
}
DEFAULT_LEVEL_SPEC = {"max_term_density": 0.2, "max_sentence_len": 30}


_DEFAULT_READING_LEVEL = """请对以下医学科普内容进行阅读难度分析。

【内容信息】
目标读者：{target_audience}
目标受众标准：句长{max_sentence_len}字；术语密度上限{max_term_density}（术语数/总字数）；术语密度下限0.02

【待分析内容】
{content}

【分析任务】
1. 句长合规性：平均句长是否在目标范围内，超上限标注超长句并给拆分建议
2. 术语密度：是否在0.02-{max_term_density}之间，超上限建议增加通俗解释
3. 未解释英文缩写：缩写首次出现100字内应有中文说明
4. 被动语态（仅public/patient）：被动句比例>20%为过高

【输出格式（JSON）】
{{
  "passed": true,
  "target_audience": "{target_audience}",
  "stats": {{
    "avg_sentence_len": 数字,
    "term_density": 数字（0-1）,
    "unexplained_abbreviations": []
  }},
  "issues": ["具体问题描述"],
  "suggestions": ["具体改进建议"],
  "consistency_note": ""
}}
passed：所有issues为空→true，有issue→false（不阻断发布）。consistency_note：章节难度差异>15%时填写提醒，否则为空。

请直接输出JSON。
"""

READING_LEVEL_PROMPT = load_verification("reading_level") or _DEFAULT_READING_LEVEL

_DEFAULT_SUGGEST_IMAGES = """请分析以下医学科普内容，推荐最合适的配图位置和内容。

【科普内容】
{verified_content}

【文章信息】
主题：{topic}
专科：{specialty}
目标受众：{target_audience}
科普形式：{content_format}

【配图推荐规则】
1. 以下内容通常适合配图，应积极推荐：
   - 解剖结构、生理机制、病理过程（如血糖调节、血管堵塞）
   - 健康 vs 疾病的对比说明
   - 流程/步骤/方法（如检查流程、预防措施）
   - 数据/统计信息、概念对比

2. 不推荐配图的情况：
   - 纯叙事段落（故事开头、案例引入）
   - 情绪性/共情性收尾

3. 每篇文章最多推荐3处配图；若内容有机制解释或对比说明，至少推荐1处

【输出格式（必须为合法 JSON）】

[
  {{
    "anchor_text": "该段落的前20个字",
    "image_type": "anatomy|pathology|flowchart|infographic|comparison|symptom|prevention",
    "style": "medical_illustration|flat_design|realistic|cartoon|data_viz",
    "description": "图像内容描述（中文，30-50字）",
    "en_description": "图像内容描述（英文，20-40词）",
    "reason": "为什么这里需要配图（≤20字）",
    "priority": "high|medium"
  }}
]

如果没有适合配图的位置，返回空数组：[]

请直接输出 JSON。
"""

SUGGEST_IMAGES_PROMPT = load_verification("suggest_images") or _DEFAULT_SUGGEST_IMAGES

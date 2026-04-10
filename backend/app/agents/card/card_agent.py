"""知识卡片 Agent - 系列规划 + 封面卡 + 内容卡 + 结尾卡"""
from app.agents.base import BaseAgent
from app.agents.prompts.loader import load_task


CARD_COLOR_GUIDANCE = {
    "blue": "蓝色系，专业感强，适合机制解释类",
    "green": "绿色系，健康积极，适合预防/建议类",
    "orange": "橙色系，温暖活泼，适合行动类/儿科",
    "purple": "紫色系，权威感，适合数据/研究类",
    "red": "红色系，警示感，适合风险提示类",
}

_PRESENTATION_MODES = """信息呈现方式（选择最适合本卡内容的一种）：
  ● 要点罗列：3-5条，每条≤15字
  ● 对比结构：✓正确 vs ✗错误（知识卡最高效的信息传递方式）
  ● 流程步骤：第1步→第2步→第3步
  ● 数据展示：数字+说明（善用数字作标题钩子："3个信号""5步自查"）
  ● 图示为主+少量文字"""


def _get_series_plan_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    total = meta.get("total_cards", 9)
    color_scheme = meta.get("color_scheme", "blue")
    color_guidance = CARD_COLOR_GUIDANCE.get(color_scheme, CARD_COLOR_GUIDANCE["blue"])
    return f"""请为医学科普知识卡片系列规划整体方案。

【系列信息】
主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}
目标受众：{state.get("target_audience", "public")}
目标平台：{state.get("platform", "xiaohongshu")}
默认配色：{color_guidance}

【输出格式（严格遵守 JSON 结构）】

{{
  "series_theme": "系列主题名称（≤12字，适合做封面标题）",
  "total_cards": {total},
  "core_science_point": "1-2句话概括核心科普点",
  "visual_style": {{
    "color_scheme": "主色+辅色描述",
    "font_style": "字体风格建议",
    "icon_style": "图标风格（如线性/填充/手绘）",
    "layout": "1080×1080正方形 或 1080×1440竖版3:4"
  }},
  "cards": [
    {{
      "card_index": 0,
      "card_role": "cover",
      "card_title": "封面标题（≤12字）",
      "subtitle": "副标题（≤20字）",
      "hook": "封面钩子描述"
    }},
    {{
      "card_index": 1,
      "card_role": "content",
      "card_title": "本卡小标题（≤10字）",
      "key_point": "本卡核心信息预览",
      "presentation_mode": "要点罗列|对比结构|流程步骤|数据展示|图示为主"
    }},
    ...内容卡若干...
    {{
      "card_index": N,
      "card_role": "ending",
      "card_title": "结尾卡标题",
      "summary_direction": "总结方向"
    }}
  ]
}}

【规划原则】
- 推荐 5-9 张一组（封面1 + 内容3-7 + 结尾1）
- 善用数字做标题钩子："3个信号""5步自查""8大误区"
- 每张卡只讲一个知识点，信息密度靠结构而非堆字
- 对比结构（正确 vs 错误）是最高效的信息传递方式
- 系列卡片保持统一的视觉风格和编号规则

请直接输出 JSON，不要有任何其他文字。
"""


def _get_cover_card_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    planner_json = meta.get("planner_json", {})
    visual_style = planner_json.get("visual_style", {})
    series_theme = planner_json.get("series_theme", state.get("topic", ""))

    cards = planner_json.get("cards", [])
    cover_info = next((c for c in cards if c.get("card_role") == "cover"), {})

    return f"""请为知识卡片系列生成封面卡。

【系列信息】
系列主题：{series_theme}
整体主题：{state.get("topic", "")}
视觉风格：{visual_style}
封面规划：{cover_info}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "card_role": "cover",
  "main_title": "主标题（≤12字，有悬念感或数字钩子）",
  "subtitle": "副标题（≤20字，补充说明或吸引点击）",
  "illustration_desc": "封面主视觉描述（英文，30-50词，DALL·E 使用）",
  "brand_position": "品牌/账号标识位置建议",
  "visual_notes": "给设计师的说明"
}}

【封面卡要求】
- 主标题决定整个系列的点击率
- 标题格式建议：数字型（"5个信号"）/ 问句型（"你知道吗？"）/ 反转型
- 色彩鲜艳，信息层级分明
- illustration_desc 必须用英文，风格：flat design, bright colors, clean layout
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


def _get_content_card_prompt(state: dict, section_type: str) -> str:
    meta = state.get("format_meta", {})
    card_index = meta.get("card_index", 1)
    total = meta.get("total_cards", 9)
    planner_json = meta.get("planner_json", {})
    visual_style = planner_json.get("visual_style", {})

    cards = planner_json.get("cards", [])
    card_info = next(
        (c for c in cards if c.get("card_index") == card_index),
        cards[card_index] if card_index < len(cards) else {},
    )
    card_title = card_info.get("card_title", "")
    presentation_mode = card_info.get("presentation_mode", "要点罗列")

    return f"""请为知识卡片系列生成第 {card_index} 张内容卡。

【卡片信息】
整体主题：{state.get("topic", "")}
系列主题：{planner_json.get("series_theme", "")}
本卡标题：{card_title}
本卡呈现方式：{presentation_mode}
视觉风格：{visual_style}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "card_role": "content",
  "card_index": {card_index},
  "card_title": "小标题（≤10字）",
  "headline": "卡片最显眼的一句话（≤15字，浓缩本卡核心）",
  "presentation_mode": "{presentation_mode}",
  "body_items": [
    "要点1（≤15字）",
    "要点2（≤15字）",
    "要点3（≤15字）"
  ],
  "body_text": "正文补充（≤80字，仅在body_items不足以表达时使用，否则为空）",
  "key_takeaway": "划重点（≤20字）",
  "illustration_desc": "配图描述（英文，20-40词，DALL·E 使用）",
  "icon_suggestions": ["图标1", "图标2"],
  "special_note": "特殊标注（如有，如数据来源、注意事项）"
}}

{_PRESENTATION_MODES}

【内容卡要求】
- 单张正文不超过80字，信息密度靠结构而非堆字
- 一张卡只讲一件事
- headline 要有张力：✅ "血糖高了，先别急着吃药" ❌ "血糖管理的重要性"
- body_items 每条≤15字，简洁有力
- illustration_desc 必须英文，风格：flat design medical illustration, bright colors, white background
- 与前后卡片保持视觉风格统一
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


def _get_ending_card_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    planner_json = meta.get("planner_json", {})
    visual_style = planner_json.get("visual_style", {})
    series_theme = planner_json.get("series_theme", state.get("topic", ""))

    cards = planner_json.get("cards", [])
    ending_info = next((c for c in cards if c.get("card_role") == "ending"), {})

    return f"""请为知识卡片系列生成结尾卡。

【系列信息】
系列主题：{series_theme}
整体主题：{state.get("topic", "")}
视觉风格：{visual_style}
结尾规划：{ending_info}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "card_role": "ending",
  "summary_text": "总结语（≤30字，浓缩全系列核心信息）",
  "action_call": "行动号召（如：转发给家人/收藏备用/关注获取更多）",
  "source_note": "来源标注（如：内容参考XX指南）",
  "account_info": "账号信息/二维码位置建议",
  "illustration_desc": "结尾卡视觉描述（英文，20-40词，DALL·E 使用）",
  "visual_notes": "给设计师的说明"
}}

【结尾卡要求】
- 总结语要有记忆点，适合截图分享
- 行动号召要明确（关注/转发/收藏）
- 保持与系列其他卡片的视觉一致性
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


class CardSeriesWriter(BaseAgent):
    """知识卡片 Agent：series_plan 输出系列规划 JSON，各卡输出单卡内容 JSON"""

    module = "card_series"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        if self.section_type == "series_plan":
            return _get_series_plan_prompt(state)
        if self.section_type == "cover_card":
            return _get_cover_card_prompt(state)
        if self.section_type == "ending_card":
            return _get_ending_card_prompt(state)
        return _get_content_card_prompt(state, self.section_type)

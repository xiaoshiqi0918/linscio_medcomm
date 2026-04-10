"""科普绘本 Agent - 面向儿童，完整故事+插画，跨页结构"""
import json as _json
from app.agents.base import BaseAgent

_SPREAD_ROLES = {
    "spread_1": ("故事开场", "P2-3", "介绍主角和日常场景，建立代入感"),
    "spread_2": ("问题出现", "P4-5", "主角遇到问题或发现异常，制造好奇心"),
    "spread_3": ("展开", "P6-7", "问题加深或主角尝试解决但遇到困难"),
    "spread_4": ("深入", "P8-9", "引入新角色/新线索，推动情节发展"),
    "spread_5": ("知识核心", "P10-11", "通过角色行动/对话自然带出核心知识点"),
    "spread_6": ("转折", "P12-13", "关键转折，主角找到正确方法"),
    "spread_7": ("结局", "P14-15", "问题解决，主角成长，正向强化"),
}


def _get_book_plan_prompt(state: dict) -> str:
    return f"""请为儿童医学科普绘本规划整体方案。

【绘本信息】
主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}
目标年龄：3-8岁儿童
页数：16页（封面+7个跨页+封底）
尺寸：210×210mm 方形

【输出格式（严格遵守 JSON 结构）】

{{
  "book_title": "绘本书名（有画面感、吸引儿童，≤12字）",
  "target_age": "3-8岁",
  "core_knowledge": "全书最核心的一个知识点（儿童能理解的版本，≤30字）",
  "story_summary": "一句话概括故事主线（≤40字）",
  "main_character": {{
    "name": "主角名字",
    "appearance": "外貌和标志性物品",
    "personality": "性格特征（1-2个词）"
  }},
  "supporting_characters": [
    {{"name": "配角名字", "role": "身份/作用", "appearance": "外貌描述"}}
  ],
  "personification": [
    {{"original": "被拟人化的对象", "becomes": "拟人化后的形象", "example": "如：白细胞→小卫士"}}
  ],
  "art_style": {{
    "reference": "画风参考（如：宫崎骏风/迪士尼风/北欧简约风）",
    "color_palette": "配色方案（如：明亮暖色系+柔和粉彩）",
    "special_craft": "特殊工艺（无/触摸页/翻翻页/洞洞书）"
  }},
  "spreads": [
    {{
      "spread_index": 1,
      "pages": "P2-3",
      "function": "故事开场",
      "theme": "本跨页传递的内容",
      "emotion": "情绪基调",
      "page_turn_hook": "翻页前的小悬念"
    }},
    {{
      "spread_index": 2,
      "pages": "P4-5",
      "function": "问题出现",
      "theme": "...",
      "emotion": "...",
      "page_turn_hook": "..."
    }},
    {{
      "spread_index": 3,
      "pages": "P6-7",
      "function": "...",
      "theme": "...",
      "emotion": "...",
      "page_turn_hook": "..."
    }},
    {{
      "spread_index": 4,
      "pages": "P8-9",
      "function": "...",
      "theme": "...",
      "emotion": "...",
      "page_turn_hook": "..."
    }},
    {{
      "spread_index": 5,
      "pages": "P10-11",
      "function": "知识核心",
      "theme": "...",
      "knowledge_embed": "嵌入的知识点",
      "emotion": "...",
      "page_turn_hook": "..."
    }},
    {{
      "spread_index": 6,
      "pages": "P12-13",
      "function": "...",
      "theme": "...",
      "emotion": "...",
      "page_turn_hook": "..."
    }},
    {{
      "spread_index": 7,
      "pages": "P14-15",
      "function": "问题解决/结局",
      "theme": "...",
      "emotion": "..."
    }}
  ]
}}

【规划原则】
- 叙事有起承转合，不是知识点的罗列
- 主角最好是拟人化的身体部件/动物/儿童（比成人角色更亲切）
- 每个跨页只推进一个情节节点
- 翻页前制造小悬念："小卫士冲进去一看……"
- 知识不是"讲"出来的，是通过角色的行动"做"出来的
- 结尾给正向强化，不恐吓
- 所有内容不引起恐惧感，不出现血腥/手术/痛苦画面

请直接输出 JSON，不要有任何其他文字。
"""


def _get_cover_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    title = pj.get("book_title", state.get("topic", ""))
    mc = pj.get("main_character", {})
    art = pj.get("art_style", {})

    return f"""请为儿童科普绘本生成封面（P1）内容。

【绘本信息】
书名：{title}
主角：{mc.get("name", "")} - {mc.get("appearance", "")}
画风：{art.get("reference", "")}
配色：{art.get("color_palette", "")}

【输出格式（严格遵守 JSON）】

{{
  "book_title": "{title}",
  "title_style": "书名位置和排版建议（如：居中上方，圆体加粗，柔和阴影）",
  "cover_illustration": "封面插图描述（英文，50-70词，DALL·E可直接使用）",
  "subtitle": "副标题/引导语（选填，≤15字，如：一个关于勇敢看牙的故事）",
  "age_badge": "适读年龄标识（如：3-8岁适读）"
}}

【封面要求】
- cover_illustration 必须英文，详细描述主角在封面的形象、动作、表情、背景
- 风格关键词：children's picture book, cute, bright colors, warm, inviting, no text in illustration
- 封面决定吸引力，要让孩子一眼就想打开
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON。
"""


def _get_spread_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    spread_idx = meta.get("spread_index", 1)
    st = state.get("section_type", f"spread_{spread_idx}")

    role_name, pages, role_desc = _SPREAD_ROLES.get(
        st, (f"展开{spread_idx}", f"P{spread_idx*2}-{spread_idx*2+1}", "推进情节")
    )

    mc = pj.get("main_character", {})
    art = pj.get("art_style", {})
    spreads = pj.get("spreads", [])
    spread_plan = next((s for s in spreads if s.get("spread_index") == spread_idx), {})
    theme = spread_plan.get("theme", "")
    emotion = spread_plan.get("emotion", "")
    hook = spread_plan.get("page_turn_hook", "")
    knowledge = spread_plan.get("knowledge_embed", "")

    planner_block = ""
    if pj:
        planner_block = f"\n【绘本规划（必须遵循）】\n{_json.dumps(pj, ensure_ascii=False, indent=2)}\n"

    return f"""请为儿童科普绘本生成{role_name}跨页（{pages}）内容。

【绘本信息】
书名：{pj.get("book_title", state.get("topic", ""))}
主角：{mc.get("name", "")} - {mc.get("appearance", "")}
画风：{art.get("reference", "")}
配色：{art.get("color_palette", "")}

【本跨页规划】
功能：{role_name}（{role_desc}）
页码：{pages}
主题：{theme}
情绪基调：{emotion}
{f"翻页悬念：{hook}" if hook else ""}
{f"嵌入知识点：{knowledge}" if knowledge else ""}
{planner_block}

【输出格式（严格遵守 JSON）】

{{
  "spread_index": {spread_idx},
  "pages": "{pages}",
  "function": "{role_name}",
  "left_page": {{
    "illustration_desc": "左页插图描述（英文，40-60词，详细的画面元素+角色动作+表情+背景）",
    "layout_note": "左页版式说明（文图位置关系）"
  }},
  "right_page": {{
    "illustration_desc": "右页插图描述（英文，40-60词）",
    "layout_note": "右页版式说明"
  }},
  "page_text": "这个跨页的文字（中文，≤50字，朗读顺口，节奏感强）",
  "sound_words": "拟声词/互动词（可选，如'哗啦啦！''你猜猜看？'）",
  "emotion": "{emotion}",
  "page_turn_hook": "翻页前的小悬念（让孩子想翻下一页的那句话/画面）"
}}

【文字规范（最重要）】
- page_text ≤50字，是整个跨页（左+右两页）的全部文字
- 文字要简单、有节奏感，朗读出来顺口
- 每个跨页只推进一个情节节点，不要挤太多信息
- 用儿童视角，短句为主，可以用感叹号和省略号制造节奏
- 知识不是"讲"出来的，是通过角色的行动"做"出来的

【illustration_desc 规范】
- 必须英文，左右页各一段
- 风格统一：children's picture book, {art.get("reference", "warm watercolor")}, bright colors, {art.get("color_palette", "soft pastels")}
- 不出现血腥/恐怖元素
- 角色外貌描述要与前后页一致

【禁止项】
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注
- 不出现引起恐惧的画面
- 不使用成人化语言

请直接输出 JSON。
"""


def _get_back_cover_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    title = pj.get("book_title", state.get("topic", ""))
    core = pj.get("core_knowledge", "")

    return f"""请为儿童科普绘本生成封底/家长指南（P16）内容。

【绘本信息】
书名：{title}
核心知识点：{core}

【输出格式（严格遵守 JSON）】

{{
  "parent_guide": "给家长的话（≤100字，帮助大人用正确方式和孩子讨论本书内容）",
  "extension_activities": [
    "延伸活动建议1（如：和孩子一起画出故事里的角色）",
    "延伸活动建议2（如：用绘本中的比喻向孩子解释XX）",
    "延伸活动建议3"
  ],
  "back_illustration": "封底插图描述（英文，30-40词，温馨、可爱的结尾画面）",
  "copyright_placeholder": "版权信息占位（ISBN、出版信息等）",
  "knowledge_summary": "本书涉及的关键医学知识点（给家长参考，≤80字）"
}}

【封底要求】
- parent_guide 是封底最重要的内容，帮助家长用正确方式讨论
- 延伸活动要具体可操作，适合亲子互动
- back_illustration 英文，温馨收尾画面
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON。
"""


class PictureBookWriter(BaseAgent):
    """科普绘本 Agent：book_plan 输出规划 JSON，跨页输出左右页内容"""

    module = "picture_book"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        if self.section_type == "book_plan":
            return _get_book_plan_prompt(state)
        if self.section_type == "cover":
            return _get_cover_prompt(state)
        if self.section_type == "back_cover":
            return _get_back_cover_prompt(state)
        if self.section_type.startswith("spread_"):
            return _get_spread_prompt(state)
        return _get_spread_prompt(state)

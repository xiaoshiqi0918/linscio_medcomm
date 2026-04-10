"""条漫 Agent - 形式族 C 图示类，输出 JSON，七幕叙事结构"""
from app.agents.base import BaseAgent
from app.agents.prompts.loader import load_comic

_PANEL_ACT_MAP = {
    1: ("封面", "封面格决定点击率。标题要有悬念感或反差感，主角形象完整呈现，色彩鲜艳吸引眼球。"),
    2: ("日常引入", "用一个具体的日常场景快速建立代入感。展现主角的日常状态，让读者产生共鸣。"),
    3: ("问题出现", "冲突/转折点。出现一个'不对劲'的信号，引发读者好奇。可使用特殊效果（放大、惊叹号）。"),
    4: ("误区展示", "展示主角或大众常见的错误认知或错误做法。角色表情可以是'自信但错误的'。"),
    5: ("误区展示", "展示另一个误区或错误做法的后果。让读者意识到需要改变。"),
    6: ("知识讲解", "核心科普区。只讲一个知识点，用视觉类比解释抽象概念。可切换画风增加节奏变化。"),
    7: ("知识讲解", "核心科普区。承接上格，讲第二个关键知识点。对白≤20字，画面为主。"),
    8: ("知识讲解", "核心科普区。第三个知识点或深入解释。用角色的表情和肢体语言传递'豁然开朗'的感觉。"),
    9: ("正确做法", "给出第一个具体可操作的正确做法。角色表情积极、自信。"),
    10: ("正确做法", "给出第二个具体可操作的建议。画面展示角色实践正确行为的场景。"),
    11: ("正确做法", "补充建议或强化前两格的做法。如无更多建议，可用于过渡到结尾。"),
    12: ("总结收尾", "总结金句放显眼位置。角色做出友好/鼓励动作。包含行动号召（转发/关注/收藏）。"),
}


def _parse_panel_index(section_type: str, default_total: int = 12) -> tuple[int, int]:
    """从 section_type 解析 panel_index，如 panel_3 -> (3, 12)"""
    if section_type and section_type.startswith("panel_"):
        try:
            idx = int(section_type.replace("panel_", ""))
            return idx, default_total
        except ValueError:
            pass
    return 1, default_total


def _get_act_guidance(panel_index: int, total_panels: int, panel_role: str) -> tuple[str, str]:
    """根据格号返回叙事幕名称和创作指导"""
    act_info = _PANEL_ACT_MAP.get(panel_index)
    if act_info:
        return act_info

    if panel_index == total_panels:
        return ("总结收尾", "最后一格是落点。总结金句+行动号召，给读者情感上的满足感。")

    return (panel_role or "情节推进",
            f"承接上一格的情节自然推进。本格功能：{panel_role or '推进情节'}。")


def _get_comic_planner_prompt(state: dict) -> str:
    tpl = load_comic("planner")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            target_audience=state.get("target_audience", "public"),
            platform=state.get("platform", "wechat"),
        )
    return _default_comic_planner(state)


def _default_comic_planner(state: dict) -> str:
    return f"""请为医学科普条漫规划分格方案。

【条漫信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标受众：{state.get('target_audience', 'public')}
目标平台：{state.get('platform', 'wechat')}

【输出格式（严格遵守 JSON 结构）】

{{
  "total_panels": 12,
  "story_type": "医患对话|疾病旅程|误区纠正|日常科普",
  "story_arc": "一句话说明整体叙事弧线",
  "core_science_point": "1-2句话概括核心科普点",
  "characters": [
    {{
      "name": "角色姓名",
      "role": "主角|配角|医生",
      "visual_desc": "视觉特征描述（年龄、外貌、服装、标志性特征）",
      "personality": "性格特征"
    }}
  ],
  "color_theme": "整体色调建议",
  "art_style": "画风参考（如扁平插画/Q版卡通/半写实）",
  "panels": [
    {{
      "panel_index": 1,
      "act": "封面|日常引入|问题出现|误区展示|知识讲解|正确做法|总结收尾",
      "panel_theme": "本格讲什么",
      "key_visual": "最重要的视觉元素",
      "emotion": "本格的情绪基调",
      "text_hint": "预计对白/旁白方向（≤15字）"
    }},
    ...共12个
  ]
}}

【七幕叙事结构（必须遵守）】

第1格·封面：标题+引导语+主角形象，决定点击率
第2格·日常引入：用具体场景建立代入感
第3格·问题出现：冲突/转折，引发好奇
第4-5格·误区展示：每格展示一个常见错误认知
第6-8格·知识讲解（核心区）：每格只讲一个知识点
第9-11格·正确做法：每格一个可操作建议
第12格·总结收尾：金句+行动号召

【角色设定原则】
- 主角设定要具体（年龄、职业、生活习惯），避免"某患者"
- 至少1个主角+1个医生/科普角色
- visual_desc 必须详细到能让AI绘图工具复现

【视觉设计原则】
- 色彩鲜艳明快，用对比强烈的颜色
- 版式节奏感：关键格可放大突出
- 以视觉为主，文字为辅

请直接输出 JSON，不要有任何其他文字。
"""


def _get_comic_panel_prompt(state: dict, section_type: str) -> str:
    format_meta = state.get("format_meta") or {}
    panel_index = format_meta.get("panel_index")
    total_panels = format_meta.get("total_panels")
    if panel_index is None or total_panels is None:
        panel_index, total_panels = _parse_panel_index(section_type, default_total=12)

    panel_role = format_meta.get("panel_role", "")
    panel_theme = format_meta.get("panel_theme", "")
    story_arc = format_meta.get("story_arc", "")

    planner_items = format_meta.get("planner_items", [])
    if planner_items and (not panel_role or not panel_theme):
        item = next((p for p in planner_items if p.get("panel_index") == panel_index), None)
        if not item and 0 < panel_index <= len(planner_items):
            item = planner_items[panel_index - 1]
        if item:
            panel_role = panel_role or item.get("panel_role", "") or item.get("act", "")
            panel_theme = panel_theme or item.get("panel_theme", "")
    planner_json = format_meta.get("planner_json", {})
    if not story_arc and planner_json:
        story_arc = planner_json.get("story_arc", "")

    act_name, position_guidance = _get_act_guidance(panel_index, total_panels, panel_role)

    characters_block = ""
    if planner_json and planner_json.get("characters"):
        import json as _json
        characters_block = f"\n【角色设定（视觉特征必须严格复现）】\n{_json.dumps(planner_json['characters'], ensure_ascii=False, indent=2)}\n"

    tpl = load_comic("panel")
    if tpl:
        return tpl.format(
            panel_index=panel_index,
            total_panels=total_panels,
            topic=state.get("topic", ""),
            story_arc_line=f"整体叙事：{story_arc}\n" if story_arc else "",
            panel_role_line=f"本格叙事幕：{act_name}\n" if act_name else "",
            panel_theme_line=f"本格主题：{panel_theme}\n" if panel_theme else "",
            position_guidance=position_guidance,
        )

    return _default_comic_panel(
        state, section_type, panel_index, total_panels,
        story_arc, act_name, panel_theme, position_guidance, characters_block,
    )


def _default_comic_panel(
    state: dict, section_type: str,
    panel_index: int, total_panels: int,
    story_arc: str, act_name: str, panel_theme: str,
    position_guidance: str, characters_block: str,
) -> str:
    planner_json = (state.get("format_meta") or {}).get("planner_json", {})
    planner_block = ""
    if planner_json:
        import json as _json
        planner_block = f"\n【分格规划总览（必须遵循）】\n{_json.dumps(planner_json, ensure_ascii=False, indent=2)}\n"
    return f"""请为医学科普条漫生成第 {panel_index}/{total_panels} 格的详细内容。

【条漫信息】
整体主题：{state.get('topic', '')}
{f'整体叙事：{story_arc}' if story_arc else ''}
本格叙事幕：{act_name}
{f'本格主题：{panel_theme}' if panel_theme else ''}
创作指导：{position_guidance}
{characters_block}{planner_block}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "panel_index": {panel_index},
  "scene_desc": "画面描述（英文，30-50词，精确描述构图、人物动作、表情、背景，DALL·E 可直接使用）",
  "dialogue": "人物对白（中文，≤30字，如果本格无对白则为空字符串）",
  "narration": "旁白文字（中文，≤20字，显示在格外的叙述文字，如无则为空字符串）",
  "caption": "图注或知识点标注（中文，≤15字，可为空）",
  "visual_notes": "给绘图者的特别说明"
}}

【各叙事幕画面要求】
▌封面格：标题文字放显眼位置，主角形象完整，色彩鲜艳吸引点击
▌日常引入格：日常场景，生活感强，角色状态自然放松
▌问题出现格：明确视觉冲突信号，角色表情惊讶/困惑，可用视觉特效
▌误区展示格：展示错误认知行为，可用"×"或红色暗示错误
▌知识讲解格：每格只讲一个知识点，可切换"小课堂"画风，用视觉类比
▌正确做法格：展示具体可操作行为，角色积极自信，可用"✓"绿色强调
▌总结收尾格：金句+行动号召，角色友好鼓励

【画面描述（scene_desc）规范】
- 必须用英文
- 包含：主体+动作/状态+背景环境+情绪/氛围+色彩风格
- 角色视觉特征必须与planner中定义的一致
- 色彩鲜艳明快
- ✅ "A middle-aged woman holding a blood glucose meter, looking worried, sitting in a bright clinic, warm lighting, flat illustration style, vibrant colors."
- ❌ "画面是一个女人在医院"

【对白规范】
- 每句≤15字，口语化，一格最多2-3句
- 医学术语必须通俗化

【医学内容要求】
- 知识点必须准确，不出现具体剂量
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


class ComicPanelWriter(BaseAgent):
    """条漫 Agent：planner 输出分格方案 JSON，panel 输出单格内容 JSON"""

    module = "comic_strip"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        if self.section_type == "planner":
            return _get_comic_planner_prompt(state)
        return _get_comic_panel_prompt(state, self.section_type)

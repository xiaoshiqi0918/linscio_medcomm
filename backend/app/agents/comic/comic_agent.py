"""条漫 Agent - 形式族 C 图示类，输出 JSON"""
from app.agents.base import BaseAgent
from app.agents.prompts.loader import load_comic


def _parse_panel_index(section_type: str, default_total: int = 6) -> tuple[int, int]:
    """从 section_type 解析 panel_index，如 panel_3 -> (3, 6)"""
    if section_type and section_type.startswith("panel_"):
        try:
            idx = int(section_type.replace("panel_", ""))
            return idx, default_total
        except ValueError:
            pass
    return 1, default_total


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

【分格规划要求】

请输出以下 JSON 格式（严格遵守，不添加多余内容）：

{{
  "total_panels": 6,
  "story_type": "医患对话|疾病旅程|误区纠正|日常科普",
  "story_arc": "一句话说明整体叙事弧线",
  "panels": [
    {{
      "panel_index": 1,
      "panel_role": "开场/建立情境",
      "panel_theme": "本格讲什么",
      "key_visual": "最重要的视觉元素",
      "emotion": "本格的情绪基调"
    }},
    ...
  ]
}}

【规划原则】
标准格数：4-8格（微信公众号推荐6格，小红书推荐4-5格）

叙事结构参考：
- 4格：建立问题→探索→发现→解决
- 6格：引入场景→问题出现→寻求帮助→获得解释→理解实践→总结升华
- 8格：更细腻的情感和知识展开

每格的功能定位：
- 第1格：钩子，吸引读者继续读（问题/冲突/有趣场景）
- 中间格：知识点展开（每格一个知识点或情节推进）
- 最后格：总结+行动/情感落点

视觉连贯性：
- 主要人物在整条漫中保持一致
- 场景变换时要有合理的叙事过渡

请直接输出 JSON，不要有任何其他文字。
"""


def _get_comic_panel_prompt(state: dict, section_type: str) -> str:
    format_meta = state.get("format_meta") or {}
    panel_index = format_meta.get("panel_index")
    total_panels = format_meta.get("total_panels")
    if panel_index is None or total_panels is None:
        panel_index, total_panels = _parse_panel_index(section_type, default_total=6)

    panel_role = format_meta.get("panel_role", "")
    panel_theme = format_meta.get("panel_theme", "")
    story_arc = format_meta.get("story_arc", "")

    planner_items = format_meta.get("planner_items", [])
    if planner_items and (not panel_role or not panel_theme):
        item = next((p for p in planner_items if p.get("panel_index") == panel_index), None)
        if not item and 0 < panel_index <= len(planner_items):
            item = planner_items[panel_index - 1]
        if item:
            panel_role = panel_role or item.get("panel_role", "")
            panel_theme = panel_theme or item.get("panel_theme", "")
    planner_json = format_meta.get("planner_json", {})
    if not story_arc and planner_json:
        story_arc = planner_json.get("story_arc", "")

    position_guidance = {
        1: "第一格是钩子，必须在读者还没决定要不要继续读之前就抓住他们。可以用一个让人有共鸣的日常场景，或者一句让人好奇的话。",
        total_panels: "最后一格是落点，需要给读者情感上的满足感，同时自然带出核心知识或行动建议。结尾要有余韵。",
    }.get(
        panel_index,
        f"本格在故事中的功能：{panel_role or '推进情节'}。承接上一格的情节，推进到下一格。"
        if panel_role
        else "承接上一格的情节，推进到下一格。",
    )

    story_arc_line = f"整体叙事：{story_arc}\n" if story_arc else ""
    panel_role_line = f"本格功能：{panel_role}\n" if panel_role else ""
    panel_theme_line = f"本格主题：{panel_theme}\n" if panel_theme else ""

    tpl = load_comic("panel")
    if tpl:
        return tpl.format(
            panel_index=panel_index,
            total_panels=total_panels,
            topic=state.get("topic", ""),
            story_arc_line=story_arc_line,
            panel_role_line=panel_role_line,
            panel_theme_line=panel_theme_line,
            position_guidance=position_guidance,
        )

    return _default_comic_panel(state, section_type, panel_index, total_panels, story_arc, panel_role, panel_theme, position_guidance)


def _default_comic_panel(
    state: dict, section_type: str,
    panel_index: int, total_panels: int,
    story_arc: str, panel_role: str, panel_theme: str,
    position_guidance: str,
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
{f'本格功能：{panel_role}' if panel_role else ''}
{f'本格主题：{panel_theme}' if panel_theme else ''}
创作指导：{position_guidance}
{planner_block}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "panel_index": {panel_index},
  "scene_desc": "画面描述（英文，30-50词，精确描述构图、人物动作、表情、背景，DALL·E 可直接使用）",
  "dialogue": "人物对白（中文，≤30字，如果本格无对白则为空字符串）",
  "narration": "旁白文字（中文，≤20字，显示在格外的叙述文字，如无则为空字符串）",
  "caption": "图注或知识点标注（中文，≤15字，可为空）",
  "visual_notes": "给绘图者的特别说明（如：人物情绪需要特别突出/背景应该模糊/某元素需要标注）"
}}

【画面描述（scene_desc）规范】
- 必须用英文
- 包含：主体（人物/器官/物体）+ 动作/状态 + 背景环境 + 情绪/氛围
- 示例：
  ✅ "A middle-aged woman holding a blood glucose meter, looking worried, sitting in a bright clinic waiting room, warm lighting, flat illustration style, Chinese characters on the wall."
  ❌ "画面是一个女人在医院" （太模糊，无法生成）

【对白规范】
- 简短有力，每句≤15字
- 口语化，像真实对话
- 一格最多2-3句对白
- 医学术语必须通俗化

【医学内容要求】
- 本格的医学知识点必须准确
- 不出现具体剂量
- 如有数据需求用 [DATA:] 标注在 visual_notes 中

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

"""情景剧本 Agent - 用冲突推动剧情，用角色的错误→碰壁→被纠正完成科普"""
import json as _json
from app.agents.base import BaseAgent


def _get_drama_plan_prompt(state: dict) -> str:
    return f"""请为情景剧短视频规划剧本概况。

【剧本信息】
主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}
目标平台：{state.get("platform", "douyin")}

【输出格式（严格 JSON）】

{{
  "title": "剧本标题（有戏剧感，≤20字）",
  "core_knowledge_point": "核心科普点（一句话概括观众看完应该记住什么，≤30字）",
  "estimated_duration": "2-3分钟|3-5分钟",
  "total_script_chars": 1200,
  "tone_style": "温情感人|搞笑轻松|悬疑反转|日常写实",
  "shooting_difficulty": "低（1-2人+固定场景）|中（3-4人+2-3场景）|高（多人+多场景+特殊道具）",
  "story_arc": {{
    "act_1": "日常建立：描述主角的日常状态和潜在健康问题",
    "act_2": "冲突触发：健康问题爆发或被发现的契机",
    "act_3": "错误应对：主角用错误方式处理（偏方/自行用药/拖延）",
    "act_4": "专业介入：专业角色纠正误区，传递核心知识（核心场）",
    "act_5": "结局升华：主角改变行为/意识转变"
  }},
  "conflict_type": "误区型|拖延型|偏方型|恐惧型"
}}

【规划原则】
- 用冲突推动剧情，用角色的错误→碰壁→被纠正完成科普
- 每场戏只推进一个节拍（beat），不在一场里塞太多转折
- 错误应对那场戏很重要——观众从"看别人犯错"中学到更多
- 搞笑可以有，但不要消解健康问题的严肃性

请直接输出 JSON。
"""


def _get_cast_table_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    tone = pj.get("tone_style", "日常写实")
    arc = pj.get("story_arc", {})

    planner_block = ""
    if pj:
        planner_block = f"\n【剧本规划（必须遵循）】\n{_json.dumps(pj, ensure_ascii=False, indent=2)}\n"

    return f"""请为情景剧短视频设计角色表。

【剧本信息】
主题：{state.get("topic", "")}
风格调性：{tone}
{planner_block}

【输出格式（严格 JSON）】

{{
  "protagonist": {{
    "name": "角色姓名（如：小李/张阿姨）",
    "identity": "身份描述（如：28岁，996程序员）",
    "personality": "性格特征（2-3个关键词）",
    "core_misconception": "这个角色对健康问题的错误认知",
    "appearance": "外在表现（着装、习惯动作等）"
  }},
  "corrector": {{
    "name": "角色姓名",
    "identity": "身份（如：社区医生/药剂师/护士）",
    "speaking_style": "说话风格（如：耐心温和/幽默直白）",
    "key_message": "这个角色要传递的核心信息"
  }},
  "catalyst": {{
    "name": "角色姓名",
    "identity": "身份（如：主角的妈妈/同事/朋友）",
    "plot_function": "剧情作用（如：发现主角问题/劝说就医）",
    "is_optional": false
  }}
}}

【角色设计要求】
- 主角设定要具体（年龄、职业、生活习惯），避免"某患者"
- 纠正者（医生）不要"全知全能"，可以从倾听患者开始再给建议
- 催化剂角色推动剧情转折（发现问题/劝说就医/提供关键信息）
- 角色之间有自然的关系和互动动机
- 不输出内部标注

请直接输出 JSON。
"""


def _get_act_prompt(state: dict, act_num: int) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    arc = pj.get("story_arc", {})

    act_config = {
        1: {
            "title": "第一场·日常建立",
            "time": "30-60秒",
            "purpose": "快速建立主角的日常状态和潜在健康问题",
            "arc_key": "act_1",
            "extra_fields": '"foreshadowing": "本场埋下的伏笔"',
        },
        2: {
            "title": "第二场·冲突触发",
            "time": "30-60秒",
            "purpose": "主角的健康问题爆发或被发现",
            "arc_key": "act_2",
            "extra_fields": '"conflict_point": "冲突点描述"',
        },
        3: {
            "title": "第三场·错误应对",
            "time": "30-60秒",
            "purpose": "主角用错误的方式处理问题（民间偏方/自行用药/拖延不管等）",
            "arc_key": "act_3",
            "extra_fields": '"wrong_action": "主角的错误做法",\n    "harm_explanation": "这样做的危害是什么"',
        },
        4: {
            "title": "第四场·专业介入（核心场）",
            "time": "60-120秒",
            "purpose": "专业角色出场，纠正误区，传递核心知识",
            "arc_key": "act_4",
            "extra_fields": '"knowledge_points": [\n      {{"point": "知识点1", "delivered_by": "谁说的", "delivery_method": "用什么方式（类比/生活化语言）"}},\n      {{"point": "知识点2", "delivered_by": "谁说的", "delivery_method": "用什么方式"}}\n    ]',
        },
        5: {
            "title": "第五场·结局与升华",
            "time": "30-60秒",
            "purpose": "主角改变行为/意识转变，给出积极结局或警示",
            "arc_key": "act_5",
            "extra_fields": '"ending_type": "圆满型|警示型|开放型",\n    "behavior_change": "主角的具体改变"',
        },
    }

    cfg = act_config[act_num]
    arc_hint = arc.get(cfg["arc_key"], cfg["purpose"])

    return f"""请为情景剧短视频撰写{cfg["title"]}。

【剧本信息】
主题：{state.get("topic", "")}
本场目的：{arc_hint}
时长：{cfg["time"]}

【输出格式（严格 JSON）】

{{
  "scene": "场景描述（时间+地点，如'工作日傍晚·公司工位'）",
  "purpose": "{cfg["purpose"]}",
  "dialogue_table": [
    {{
      "character": "角色名",
      "line": "台词内容（口语化，≤30字）",
      "action": "动作/表情描述",
      "shot_hint": "画面提示（如：近景/中景/特写）"
    }}
  ],
  {cfg["extra_fields"]}
}}

【写作要求】
- 对白要像"这个人真的会说的话"，不是念课文
- 每句台词≤30字，节奏明快
- 动作说明简洁，指导拍摄
- 每场戏只推进一个节拍（beat），不要在一场里塞太多转折
- 医学知识点通过对话自然带出，不说教
{"- 医生角色不要满口术语，用类比和生活化语言解释" if act_num == 4 else ""}
{"- 错误应对很重要——观众从'看别人犯错'中学到更多" if act_num == 3 else ""}
- 角色名字、身份、关系与角色表完全一致
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON。
"""


def _get_finale_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    core_point = pj.get("core_knowledge_point", "")

    return f"""请为情景剧短视频撰写终场字幕总结。

【剧本信息】
主题：{state.get("topic", "")}
核心科普点：{core_point}

【输出格式（严格 JSON）】

{{
  "visual_direction": "画面指示（如：定格/渐黑 + 字幕）",
  "summary_text": "总结文字（≤50字，点明核心知识点）",
  "reference_note": "参考来源标注",
  "cta_text": "行动号召字幕（如：关注我们，获取更多健康知识）"
}}

【要求】
- 总结文字≤50字，要有记忆点
- 不输出内部标注

请直接输出 JSON。
"""


def _get_filming_notes_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    difficulty = pj.get("shooting_difficulty", "")
    tone = pj.get("tone_style", "")

    return f"""请为情景剧短视频生成拍摄备注。

【剧本信息】
主题：{state.get("topic", "")}
风格调性：{tone}
拍摄难度：{difficulty}

【输出格式（严格 JSON）】

{{
  "scene_list": [
    {{"scene_name": "场景1名称", "location": "拍摄地点", "props": "需要的布景/道具"}},
    {{"scene_name": "场景2名称", "location": "拍摄地点", "props": "需要的布景/道具"}}
  ],
  "actor_count": "演员数量及角色分配",
  "special_props": "特殊道具清单",
  "music_suggestion": "配乐建议（风格/情绪/参考曲目）",
  "estimated_shooting_time": "预估拍摄时长",
  "costume_notes": "服装建议"
}}

【要求】
- 场景清单要具体，便于拍摄团队准备
- 配乐建议与风格调性匹配
- 不输出内部标注

请直接输出 JSON。
"""


class DramaScriptWriter(BaseAgent):
    """情景剧本 Agent：drama_plan 规划 → cast_table 角色 → 5 场分场剧本 → 终场 → 拍摄备注"""

    module = "drama_script"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        dispatch = {
            "drama_plan": _get_drama_plan_prompt,
            "cast_table": _get_cast_table_prompt,
            "act_1": lambda s: _get_act_prompt(s, 1),
            "act_2": lambda s: _get_act_prompt(s, 2),
            "act_3": lambda s: _get_act_prompt(s, 3),
            "act_4": lambda s: _get_act_prompt(s, 4),
            "act_5": lambda s: _get_act_prompt(s, 5),
            "finale": _get_finale_prompt,
            "filming_notes": _get_filming_notes_prompt,
        }
        fn = dispatch.get(self.section_type)
        if fn:
            return fn(state)
        return _get_act_prompt(state, 1)

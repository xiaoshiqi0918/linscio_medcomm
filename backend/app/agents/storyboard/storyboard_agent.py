"""动画分镜 Agent - 四栏并行（画面+旁白+字幕+动效），抽象概念必须可视化"""
import json as _json
from app.agents.base import BaseAgent


def _get_anim_plan_prompt(state: dict) -> str:
    return f"""请为科普动画/MG动画规划分镜方案。

【内容信息】
主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}
目标平台：{state.get("platform", "bilibili")}

【输出格式（严格 JSON）】

{{
  "title": "动画标题（≤20字）",
  "core_knowledge_point": "核心科普点（观众看完应该记住什么，≤30字）",
  "target_duration": "1-2分钟|2-3分钟",
  "total_shots": 17,
  "animation_style": "MG扁平动画|手绘白板风|2.5D立体|角色动画|实拍+动画混合",
  "aspect_ratio": "16:9横版|9:16竖版|1:1方形",
  "voiceover_style": "男声稳重|女声亲切|男声活泼|女声专业|童声",
  "music_style": "配乐风格描述（如：轻快活泼、科技感、温暖治愈）",
  "color_palette": {{
    "primary": "主色调",
    "secondary": "辅助色",
    "accent": "强调色"
  }},
  "reel_outline": [
    {{"reel": 1, "title": "引入", "time_range": "0:00-0:15", "shots": 3, "theme": "..."}},
    {{"reel": 2, "title": "问题呈现", "time_range": "0:15-0:35", "shots": 4, "theme": "..."}},
    {{"reel": 3, "title": "机制解释（核心段）", "time_range": "0:35-1:20", "shots": 5, "theme": "..."}},
    {{"reel": 4, "title": "正确做法/建议", "time_range": "1:20-1:50", "shots": 3, "theme": "..."}},
    {{"reel": 5, "title": "总结收尾", "time_range": "1:50-2:00", "shots": 2, "theme": "..."}}
  ]
}}

【规划原则】
- 四栏并行：画面+旁白+字幕+动效，每镜都要同步
- 抽象概念必须可视化（用拟人化、比喻、动画角色呈现）
- 机制解释段是动画最大优势，设计好可视化比喻
- 画面停留时间通常2-4秒，信息量不能太大
- 景别要有变化，避免全程中景导致视觉疲劳

请直接输出 JSON。
"""


def _get_char_design_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    style = pj.get("animation_style", "MG扁平动画")

    planner_block = ""
    if pj:
        planner_block = f"\n【动画规划（必须遵循）】\n{_json.dumps(pj, ensure_ascii=False, indent=2)}\n"

    return f"""请为科普动画设计角色和元素设定。

【内容信息】
主题：{state.get("topic", "")}
动画风格：{style}
{planner_block}

【输出格式（严格 JSON）】

{{
  "protagonist": {{
    "name": "主角名称（如有）",
    "visual_desc": "形象描述（40-60字英文，用于 AI 绘图参考）",
    "visual_ref": "视觉参考说明"
  }},
  "anthropomorphism": [
    {{
      "abstract_concept": "抽象概念（如：免疫细胞）",
      "visual_form": "视觉形象（如：头戴钢盔的小圆球战士）",
      "design_desc": "设计描述（30字英文）"
    }}
  ],
  "scenes": [
    {{
      "scene_name": "场景1名称",
      "visual_desc": "视觉描述+色调",
      "design_desc": "30字英文设计描述"
    }}
  ]
}}

【设计要求】
- 拟人化方案：将抽象概念可视化，至少设计2-3个拟人化元素
- 场景设定：至少3个场景，与分幕对应
- 视觉描述用英文（design_desc），便于 AI 绘图
- 不输出内部标注

请直接输出 JSON。
"""


def _get_reel_prompt(state: dict, reel_num: int) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    outline = pj.get("reel_outline", [])
    reel_plan = next((r for r in outline if r.get("reel") == reel_num), {})

    reel_config = {
        1: {
            "title": "第一幕·引入",
            "time": "0:00-0:15",
            "shots": 3,
            "purpose": "开场吸引注意力，引出主题",
            "extra_note": "开场3秒是关键——用视觉冲击或悬念抓住观众",
        },
        2: {
            "title": "第二幕·问题呈现",
            "time": "0:15-0:35",
            "shots": 4,
            "purpose": "呈现健康问题，建立共鸣",
            "extra_note": "画面要让观众直观感受到问题的存在",
        },
        3: {
            "title": "第三幕·机制解释（核心段）",
            "time": "0:35-1:20",
            "shots": 5,
            "purpose": "用可视化比喻讲清楚'是什么'和'为什么'",
            "extra_note": "这是动画最大优势所在！旁白速度放慢，给观众消化时间",
        },
        4: {
            "title": "第四幕·正确做法/建议",
            "time": "1:20-1:50",
            "shots": 3,
            "purpose": "给出可操作的具体建议",
            "extra_note": "建议用图标+短文案方式呈现，清晰易记",
        },
        5: {
            "title": "第五幕·总结收尾",
            "time": "1:50-2:00",
            "shots": 2,
            "purpose": "总结核心信息+Logo+行动号召",
            "extra_note": "核心结论≤20字，留下记忆点",
        },
    }

    cfg = reel_config[reel_num]
    theme = reel_plan.get("theme", cfg["purpose"])
    time_range = reel_plan.get("time_range", cfg["time"])
    shot_count = reel_plan.get("shots", cfg["shots"])

    return f"""请为科普动画撰写{cfg["title"]}的分镜脚本。

【内容信息】
主题：{state.get("topic", "")}
本幕目的：{theme}
时间段：{time_range}
镜头数：{shot_count}

【输出格式（严格 JSON）】

{{
  "reel_title": "{cfg["title"]}",
  "time_range": "{time_range}",
  "shots": [
    {{
      "shot_number": 1,
      "duration": "3s",
      "shot_type": "全景|中景|近景|特写|俯拍|仰拍",
      "visual_desc": "画面描述（场景、人物、动画效果，≤80字）",
      "character_action": "角色动作描述",
      "voiceover": "旁白文字（口语化，与画面同步）",
      "subtitle_highlight": "重点字幕（需要在画面上强调的关键词）",
      "effects_transition": "动效/转场描述"
    }}
  ],
  "transition_to_next": "转场方式描述"
}}

【写作要求·四栏并行原则】
- 画面描述（visual_desc）：≤80字，具体可视觉化
- 旁白（voiceover）：口语化，与画面同步，每句间留0.5-1秒气口
- 字幕（subtitle_highlight）：提炼关键词，在画面上强调
- 动效（effects_transition）：描述动画效果和转场

【本幕特别注意】
- {cfg["extra_note"]}
- 景别要有变化（全景/中景/近景/特写交替）
- 每镜画面停留2-4秒，信息量不能太大
- 旁白和画面必须同步，不能"说A画面还在B"
- 抽象概念用拟人化/比喻可视化，与 char_design 一致
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON。
"""


def _get_prod_notes_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    style = pj.get("animation_style", "")
    aspect = pj.get("aspect_ratio", "")

    return f"""请为科普动画生成制作备注。

【内容信息】
主题：{state.get("topic", "")}
动画风格：{style}
画面比例：{aspect}

【输出格式（严格 JSON）】

{{
  "sound_effects": [
    "音效1描述（如：心跳声——用于展示心血管场景）",
    "音效2描述",
    "音效3描述"
  ],
  "style_reference": "素材参考/风格板描述",
  "delivery_resolution": "交付分辨率（如：1920×1080 / 1080×1920）",
  "subtitle_spec": {{
    "font": "字幕字体建议",
    "color": "字幕颜色规范",
    "position": "字幕位置"
  }},
  "total_duration_estimate": "总时长预估",
  "frame_rate": "帧率建议（如：24fps / 30fps）"
}}

【要求】
- 音效需求要具体，与动画内容对应
- 分辨率与画面比例匹配
- 不输出内部标注

请直接输出 JSON。
"""


class StoryboardWriter(BaseAgent):
    """动画分镜 Agent：anim_plan 规划 → char_design 设定 → 5 幕分镜 → 制作备注"""

    module = "storyboard"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        dispatch = {
            "anim_plan": _get_anim_plan_prompt,
            "char_design": _get_char_design_prompt,
            "reel_1": lambda s: _get_reel_prompt(s, 1),
            "reel_2": lambda s: _get_reel_prompt(s, 2),
            "reel_3": lambda s: _get_reel_prompt(s, 3),
            "reel_4": lambda s: _get_reel_prompt(s, 4),
            "reel_5": lambda s: _get_reel_prompt(s, 5),
            "prod_notes": _get_prod_notes_prompt,
        }
        fn = dispatch.get(self.section_type)
        if fn:
            return fn(state)
        return _get_reel_prompt(state, 1)

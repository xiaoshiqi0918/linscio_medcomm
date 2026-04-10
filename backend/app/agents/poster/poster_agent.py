"""科普海报 Agent - 单张大图，3秒传达一个核心信息"""
from app.agents.base import BaseAgent

_PURPOSE_OPTIONS = """海报目的类型：
  ● 疾病警示（提醒关注某疾病/症状）→ 红橙色系
  ● 行为倡导（推动健康行为）→ 蓝绿色系
  ● 节日/纪念日宣传（世界糖尿病日等）→ 主题色系
  ● 活动推广（义诊、筛查等）→ 暖色系
  ● 数据展示（一个震撼数字）→ 对比强烈色系"""

_COLOR_MAP = """色调参考：
  健康/积极 → 蓝绿色系（#2196F3 / #4CAF50）
  警示/紧急 → 红橙色系（#F44336 / #FF5722）
  温暖/关怀 → 暖黄色系（#FFC107 / #FF9800）
  权威/专业 → 深蓝紫色系（#1A237E / #4A148C）"""


def _get_poster_brief_prompt(state: dict) -> str:
    return f"""请为医学科普海报规划整体方案。

【海报信息】
主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}
目标平台：{state.get("platform", "xiaohongshu")}

{_PURPOSE_OPTIONS}

【输出格式（严格遵守 JSON 结构）】

{{
  "poster_purpose": "疾病警示|行为倡导|节日宣传|活动推广|数据展示",
  "core_message": "这张海报最想让人记住的一句话（≤15字）",
  "target_scene": "使用场景描述（如：社群传播/候诊室张贴/线下活动）",
  "size_spec": "1080×1920px竖版 或 A3横版 或 1080×1080正方形",
  "visual_style": "摄影写实|扁平插画|3D立体|数据图表|极简文字",
  "color_direction": "主色调方向及原因",
  "headline_direction": "主标题方向（≤10字预览）",
  "data_highlight": "如有可用的震撼数字，写在此处；否则留空"
}}

【规划原则】
- 海报只做一件事：传达一个核心信息
- 如果需要超过60字正文，说明不适合做海报，考虑长图或卡片
- 主标题要能脱离画面独立成立——即使看不到图，标题本身也有冲击力

请直接输出 JSON，不要有任何其他文字。
"""


def _get_headline_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    planner_json = meta.get("planner_json", {})
    purpose = planner_json.get("poster_purpose", "")
    core_msg = planner_json.get("core_message", "")
    headline_dir = planner_json.get("headline_direction", "")

    return f"""请为医学科普海报生成标题区内容。

【海报信息】
主题：{state.get("topic", "")}
海报目的：{purpose}
核心信息：{core_msg}
标题方向：{headline_dir}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "main_title": "主标题（≤10字，要大、要醒目，路人3秒内明白主题）",
  "subtitle": "副标题（≤20字，补充说明，选填，无则为空）",
  "core_message": "核心信息（≤15字，这张海报最想让人记住的一句话）"
}}

【标题区要求】
- 主标题 ≤10字，是海报视觉最大的文字元素
- 主标题要能脱离画面独立成立，本身有冲击力
- 副标题补充解释，不是重复主标题
- 核心信息是读者看完应该记住的一句话
- 善用数字做钩子："每5人就有1人""3个信号"
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


def _get_body_visual_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    planner_json = meta.get("planner_json", {})
    purpose = planner_json.get("poster_purpose", "")
    visual_style = planner_json.get("visual_style", "扁平插画")
    data_highlight = planner_json.get("data_highlight", "")
    color_dir = planner_json.get("color_direction", "")

    return f"""请为医学科普海报生成主体内容和视觉描述。

【海报信息】
主题：{state.get("topic", "")}
海报目的：{purpose}
视觉风格：{visual_style}
色调方向：{color_dir}
{f'数据亮点：{data_highlight}' if data_highlight else ''}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "main_visual_desc": "主视觉描述（英文，40-60词，DALL·E 可直接使用，精确描述画面核心元素、构图、色调、风格）",
  "body_text": "正文内容（≤60字，简短补充说明，如无需正文则为空）",
  "data_points": [
    "数据亮点1（如有，格式：数字+说明，如'每5人中就有1人患高血压'）",
    "数据亮点2（如有）"
  ],
  "visual_notes": "给设计师/绘图AI的补充说明"
}}

【主体内容要求】
- 正文 ≤60字，超过说明不适合海报
- 数据亮点只用有来源保障的数据
- 要点用数字/动词开头：❌"保持健康" ✅"每天走路30分钟"

【主视觉描述要求】
- main_visual_desc 必须用英文
- 包含：核心视觉元素 + 构图 + 人物/物体 + 色调 + 风格
- 风格关键词参考：medical illustration, bold typography, professional, eye-catching
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


def _get_cta_footer_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    planner_json = meta.get("planner_json", {})
    purpose = planner_json.get("poster_purpose", "")

    return f"""请为医学科普海报生成行动号召和底部信息栏。

【海报信息】
主题：{state.get("topic", "")}
海报目的：{purpose}
目标平台：{state.get("platform", "xiaohongshu")}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "call_to_action": "行动号召（≤15字，具体可执行）",
  "cta_style": "CTA 呈现建议（如：按钮样式/醒目色块/底部横幅）",
  "source_note": "来源/声明（如：内容参考XX指南；仅供科普参考，不替代医嘱）",
  "footer_layout": "底部信息栏布局建议（机构Logo位置、二维码位置等）"
}}

【行动号召要求】
- CTA 要具体可执行：❌"关注健康" ✅"转发给爸妈" ✅"立即预约筛查" ✅"扫码了解更多"
- 与海报目的匹配：疾病警示→就医建议，行为倡导→具体行动，活动推广→报名方式
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


def _get_design_spec_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    planner_json = meta.get("planner_json", {})
    visual_style = planner_json.get("visual_style", "扁平插画")
    color_dir = planner_json.get("color_direction", "")
    size_spec = planner_json.get("size_spec", "1080×1920px竖版")

    return f"""请为医学科普海报生成设计规格说明。

【海报信息】
主题：{state.get("topic", "")}
视觉风格：{visual_style}
色调方向：{color_dir}
尺寸规格：{size_spec}

{_COLOR_MAP}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "size": "{size_spec}",
  "color_scheme": {{
    "primary": "主色（色值+名称）",
    "secondary": "辅色（色值+名称）",
    "accent": "强调色（色值+名称）",
    "background": "背景色",
    "text_color": "主文字色"
  }},
  "typography": {{
    "main_title_ratio": "主标题占画面比例（如30%）",
    "title_to_body_ratio": "主标题与正文字号比（如5:1）",
    "font_style": "字体风格建议（如：黑体加粗/圆体/手写体）"
  }},
  "layout": {{
    "structure": "布局结构（如：上图下文/左图右文/居中对称/全出血图+文字浮层）",
    "white_space": "留白要求（如：四周至少留10%边距）",
    "visual_hierarchy": "视觉层级说明（读者视线路径：标题→图→正文→CTA）"
  }},
  "print_notes": "印刷注意事项（如需线下使用：分辨率≥300dpi，出血线3mm）"
}}

【设计规格要求】
- 色值使用 HEX 格式
- 布局必须考虑读者3秒扫视路径
- 主标题占比要醒目（通常占画面25-35%）
- 如有数据亮点，字号应仅次于主标题
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON，不要有任何其他文字。
"""


class PosterWriter(BaseAgent):
    """科普海报 Agent：poster_brief 输出规划 JSON，各区块输出对应内容 JSON"""

    module = "poster"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        dispatch = {
            "poster_brief": _get_poster_brief_prompt,
            "headline": _get_headline_prompt,
            "body_visual": _get_body_visual_prompt,
            "cta_footer": _get_cta_footer_prompt,
            "design_spec": _get_design_spec_prompt,
        }
        fn = dispatch.get(self.section_type)
        if fn:
            return fn(state)
        return _get_body_visual_prompt(state)

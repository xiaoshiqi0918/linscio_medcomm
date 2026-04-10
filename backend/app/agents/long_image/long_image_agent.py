"""竖版长图 Agent - 手机端线性阅读科普，6-10区块，总长≤8000px"""
import json as _json
from app.agents.base import BaseAgent

_PRESENTATION_MODES = """信息呈现方式选项：
  ● 纯文字+配图
  ● 图标+短文案
  ● 对比图（正确 vs 错误）
  ● 流程图/步骤图
  ● 数据可视化"""

_COLOR_THEMES = """色调参考：
  ● blue_professional → 专业、信赖 → #2196F3 + #E3F2FD
  ● green_health → 健康、自然 → #4CAF50 + #E8F5E9
  ● orange_warm → 温暖、亲切 → #FF9800 + #FFF3E0
  ● red_alert → 警示、紧急 → #F44336 + #FFEBEE
  ● purple_authority → 权威、深度 → #7B1FA2 + #F3E5F5"""


def _get_image_plan_prompt(state: dict) -> str:
    platform = state.get("platform", "wechat")
    platform_guide = {
        "wechat": "微信公众号/朋友圈竖版滑动，推荐8-10个区块",
        "xiaohongshu": "小红书长图，视觉感强，推荐6-8个区块",
    }.get(platform, "通用长图，推荐7-9个区块")

    return f"""请为竖版长图进行整体内容规划。

【长图信息】
主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}
目标平台：{platform}（{platform_guide}）
总字数预估：800-1200字
宽度：750-1080px，总长度控制在8000px以内

{_COLOR_THEMES}

【输出格式（严格遵守 JSON）】

{{
  "core_message": "这张长图最核心的一个信息（≤30字）",
  "total_chars_target": 1000,
  "color_theme": {{
    "primary": "主色调（HEX + 名称）",
    "secondary": "辅助色（HEX + 名称）",
    "background": "背景色",
    "text_color": "主文字色"
  }},
  "typography": {{
    "title_font": "标题字体建议",
    "body_font": "正文字体建议"
  }},
  "separator_style": "色带|分割线|渐变过渡|场景切换",
  "icon_style": "线性|面性|手绘|3D",
  "blocks": [
    {{
      "block_index": 1,
      "block_type": "title",
      "block_theme": "封面标题区主题",
      "estimated_chars": 40
    }},
    {{
      "block_index": 2,
      "block_type": "intro",
      "block_theme": "引入区主题",
      "estimated_chars": 80
    }},
    {{
      "block_index": 3,
      "block_type": "core",
      "block_theme": "核心内容区主题",
      "presentation_mode": "纯文字+配图|图标+短文案|对比图|流程图|数据可视化",
      "estimated_chars": 100
    }}
  ]
}}

【区块类型说明】
- title：封面标题区（1个，必须在最前）
- intro：引入区（1个）
- core：核心内容区（2-4个，每个只讲一个知识点）
- tips：实用建议区（1个）
- warning：特别提醒区（0-1个，有重要警示时使用）
- summary_cta：总结/行动号召区（1个）
- footer：尾部信息区（1个，必须在最后）

【规划原则】
- 封面决定90%的阅读率——标题要有"不看亏了"的感觉
- 每个区块是一个独立信息单元，即使跳读也能看懂
- 控制总长度，超过8000px读者容易放弃
- 区块之间用视觉手段明确分段
- 核心内容区不要在一个区块里堆砌多个知识点

请直接输出 JSON。
"""


def _get_title_block_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    core_msg = pj.get("core_message", "")
    color = pj.get("color_theme", {})

    return f"""请为竖版长图生成封面标题区。

【长图信息】
主题：{state.get("topic", "")}
核心信息：{core_msg}
配色方案：{_json.dumps(color, ensure_ascii=False) if isinstance(color, dict) else color}

【输出格式（严格 JSON）】

{{
  "main_title": "主标题（≤15字，要有'不看亏了'的感觉）",
  "subtitle": "副标题（≤25字，补充说明）",
  "visual_desc": "主视觉描述（英文，40-60词，DALL·E可用）",
  "background_mood": "背景色/氛围描述"
}}

【标题要求】
- 主标题≤15字，是整张长图视觉最大的文字
- 善用数字钩子："3个信号""每5人就有1人""90%的人不知道"
- 标题要能脱离画面独立成立，本身有冲击力
- visual_desc 必须英文，描述封面区的画面
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON。
"""


def _get_intro_block_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    blocks = pj.get("blocks", [])
    intro_plan = next((b for b in blocks if b.get("block_type") == "intro"), {})

    return f"""请为竖版长图生成引入区内容。

【长图信息】
主题：{state.get("topic", "")}
引入区主题：{intro_plan.get("block_theme", "")}

【输出格式（严格 JSON）】

{{
  "subtitle": "小标题（≤12字）",
  "body_text": "正文（≤100字，用短句，每段不超过3行）",
  "image_prompt": "配图描述（英文，30-50词）",
  "design_element": "设计元素建议（如：渐变背景/图标装饰/引用气泡框）"
}}

【引入区要求】
- 正文≤100字，抛出问题或制造共鸣，让读者想继续看
- 用短句，口语化，正文用数字/动词开头
- image_prompt 英文，配合引入区的内容氛围
- 不输出内部标注

请直接输出 JSON。
"""


def _get_core_block_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    block_idx = meta.get("block_index", 1)
    blocks = pj.get("blocks", [])
    core_blocks = [b for b in blocks if b.get("block_type") == "core"]
    block_plan = next((b for b in core_blocks if b.get("block_index") == block_idx), {})
    if not block_plan and core_blocks:
        st = state.get("section_type", "")
        if st.startswith("core_"):
            try:
                idx = int(st.replace("core_", "")) - 1
                if 0 <= idx < len(core_blocks):
                    block_plan = core_blocks[idx]
            except ValueError:
                pass
    theme = block_plan.get("block_theme", "")
    mode = block_plan.get("presentation_mode", "纯文字+配图")
    color = pj.get("color_theme", {})
    icon_style = pj.get("icon_style", "线性")

    return f"""请为竖版长图生成核心内容区。

【长图信息】
主题：{state.get("topic", "")}
本区块主题：{theme}
信息呈现方式：{mode}
图标风格：{icon_style}
配色方案：{_json.dumps(color, ensure_ascii=False) if isinstance(color, dict) else color}

{_PRESENTATION_MODES}

【输出格式（严格 JSON）】

{{
  "subtitle": "小标题（≤12字）",
  "body_text": "正文（≤100字，短句为主，每段不超3行）",
  "presentation_mode": "{mode}",
  "key_points": ["要点1（如使用图标+短文案模式）", "要点2"],
  "comparison": {{
    "correct": "正确做法（如使用对比图模式）",
    "incorrect": "错误做法"
  }},
  "image_prompt": "配图描述（英文，30-50词）",
  "layout_notes": "排版建议（≤30字）"
}}

【核心内容区要求】
- 每个区块只讲一个知识点，是独立的信息单元
- 正文≤100字，用短句，每段不超过3行
- 正文用数字/动词开头：❌"保持健康" ✅"每天走路30分钟"
- data类型无RAG来源时不出现具体数值
- image_prompt 英文，风格与整体一致
- 不输出内部标注

请直接输出 JSON。
"""


def _get_tips_block_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})

    return f"""请为竖版长图生成实用建议区。

【长图信息】
主题：{state.get("topic", "")}

【输出格式（严格 JSON）】

{{
  "subtitle": "小标题（≤12字，如'3步轻松做到'）",
  "tips": [
    {{"index": 1, "text": "建议1（≤30字，具体可执行）", "icon_desc": "图标描述（英文，5-10词）"}},
    {{"index": 2, "text": "建议2", "icon_desc": "..."}},
    {{"index": 3, "text": "建议3", "icon_desc": "..."}}
  ],
  "image_prompt": "配图描述（英文，30-50词）",
  "layout_notes": "排版建议"
}}

【建议区要求】
- 3-5条建议，每条≤30字，具体可执行
- 用数字/动词开头：❌"保持健康饮食" ✅"每餐先吃一拳蔬菜"
- 不涉及具体药物名称或剂量
- 不输出内部标注

请直接输出 JSON。
"""


def _get_warning_block_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})

    return f"""请为竖版长图生成特别提醒区。

【长图信息】
主题：{state.get("topic", "")}

【输出格式（严格 JSON）】

{{
  "warning_text": "警示内容（≤60字，不恐吓但要引起重视）",
  "design_style": "高亮色块|警告图标|对话框",
  "when_to_see_doctor": "就医信号（≤40字，具体症状描述）",
  "image_prompt": "配图描述（英文，20-35词，警示但不恐怖）"
}}

【提醒区要求】
- 不使用恐吓式表达，但要明确"什么情况下需要重视"
- 就医信号要具体：❌"感觉不适就去医院" ✅"连续3天头痛+视物模糊，尽快就医"
- 设计上要与普通区块有明显视觉区分
- 不输出内部标注

请直接输出 JSON。
"""


def _get_summary_cta_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    platform = state.get("platform", "wechat")
    platform_cta = {
        "wechat": "引导转发给家人朋友，或关注公众号获取更多科普",
        "xiaohongshu": "引导收藏+点赞，'收藏备用，关键时刻用得上'",
    }.get(platform, "引导读者采取健康行动")

    return f"""请为竖版长图生成总结/CTA区。

【长图信息】
主题：{state.get("topic", "")}
目标平台：{platform}
CTA方向：{platform_cta}

【输出格式（严格 JSON）】

{{
  "summary_line": "核心总结语（≤30字，一句话概括全图核心）",
  "call_to_action": "行动号召（≤20字，具体可执行）",
  "share_copy": "分享文案（≤35字，让人想转发）",
  "image_prompt": "总结区配图描述（英文，20-35词）"
}}

【总结/CTA要求】
- summary_line 是全图的总结升华，不是重复前面的内容
- call_to_action 要具体：❌"关注健康" ✅"转发给爸妈看看"
- share_copy 要让人有转发冲动
- 不输出内部标注

请直接输出 JSON。
"""


def _get_footer_info_prompt(state: dict) -> str:
    return f"""请为竖版长图生成尾部信息区。

【长图信息】
主题：{state.get("topic", "")}
目标平台：{state.get("platform", "wechat")}

【输出格式（严格 JSON）】

{{
  "source_note": "来源标注（如：内容参考XX指南，仅供科普参考，不替代医嘱）",
  "org_placeholder": "机构信息/Logo占位说明",
  "qrcode_placeholder": "二维码/联系方式占位说明",
  "disclaimer": "免责声明（≤40字）",
  "design_note": "尾部区域设计建议（背景色、高度、排版）"
}}

【尾部要求】
- 必须包含来源声明和免责声明
- 设计上要与正文区域有明确的视觉分隔
- 不输出内部标注

请直接输出 JSON。
"""


class LongImageWriter(BaseAgent):
    """竖版长图 Agent：image_plan 输出规划，各区块输出独立信息单元"""

    module = "long_image"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        state = {**state, "section_type": self.section_type}
        dispatch = {
            "image_plan": _get_image_plan_prompt,
            "title_block": _get_title_block_prompt,
            "intro_block": _get_intro_block_prompt,
            "tips_block": _get_tips_block_prompt,
            "warning_block": _get_warning_block_prompt,
            "summary_cta": _get_summary_cta_prompt,
            "footer_info": _get_footer_info_prompt,
        }
        fn = dispatch.get(self.section_type)
        if fn:
            return fn(state)
        if self.section_type.startswith("core_"):
            return _get_core_block_prompt(state)
        return _get_core_block_prompt(state)

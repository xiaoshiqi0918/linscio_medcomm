"""口播脚本 Agent - 开头3秒定生死，每30秒一个钩子，结尾必有行动号召"""
import json as _json
from app.agents.base import BaseAgent

_HOOK_TYPES = """开头类型（选一种）：
  ● 反常识冲击："你以为XX，其实完全相反。"
  ● 恐惧唤醒："如果你经常XX，一定要看完这条。"
  ● 争议挑衅："XX到底有没有用？评论区吵翻了。"
  ● 数据震撼："中国每X个人里就有1个XX。"
  ● 场景还原："你有没有过这种情况——XX？"
  ● 直接否定："XX根本不能XX！别再被骗了。" """

_CLOSING_TYPES = """收尾类型（选一种）：
  ● 悬念引导："想知道XX？关注我下期告诉你。"
  ● 互动提问："你中了几条？评论区告诉我。"
  ● 金句总结："记住，XX就是最好的XX。"
  ● 行动号召："赶紧转发给你身边的XX人。"
  ● 自嘲/幽默："当然，最重要的还是——别熬夜看我的视频。" """

_PERSONA_OPTIONS = """出镜人身份：医生 / 药剂师 / 营养师 / 健康博主
口吻风格：严肃权威型 / 邻家亲切型 / 犀利吐槽型 / 温柔科普型"""


def _get_script_plan_prompt(state: dict) -> str:
    platform = state.get("platform", "douyin")
    platform_guide = {
        "douyin": "抖音偏短平快，60秒以内最优，节奏极快",
        "kuaishou": "快手偏生活化，接地气，60-120秒",
        "wechat": "视频号用户年龄偏大，120-180秒可接受，语速适中",
        "bilibili": "B站可稍长但节奏不能拖，信息密度要高",
        "xiaohongshu": "小红书短视频偏精致，60-90秒，画面感强",
    }.get(platform, "通用短视频平台，60-120秒")

    return f"""请为口播短视频规划脚本方案。

【视频信息】
主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}
目标平台：{platform}（{platform_guide}）

{_PERSONA_OPTIONS}

【输出格式（严格 JSON）】

{{
  "core_knowledge_point": "核心知识点（一句话，≤30字）",
  "target_duration": "60秒以内|60-120秒|120-180秒",
  "total_script_chars": 300,
  "persona": {{
    "identity": "医生|药剂师|营养师|健康博主",
    "tone_style": "严肃权威型|邻家亲切型|犀利吐槽型|温柔科普型",
    "first_person": "出镜人第一人称称呼（如：我/咱们）"
  }},
  "hook_type": "反常识冲击|恐惧唤醒|争议挑衅|数据震撼|场景还原|直接否定",
  "closing_type": "悬念引导|互动提问|金句总结|行动号召|自嘲幽默",
  "script_outline": [
    {{"section": "golden_hook", "time": "0-5s", "theme": "...", "chars": 40}},
    {{"section": "problem_setup", "time": "5-20s", "theme": "...", "chars": 100}},
    {{"section": "core_knowledge", "time": "20-50s", "theme": "...", "chars": 200}},
    {{"section": "practical_tips", "time": "50-65s", "theme": "...", "chars": 100}},
    {{"section": "closing_hook", "time": "最后5-10s", "theme": "...", "chars": 60}}
  ]
}}

【规划原则】
- 一条视频只讲一个知识点，贪多必烂
- 开头3秒定生死——第一句就要抓住注意力
- 每30秒一个钩子（小悬念/反转/提问），防止划走
- 结尾必有行动号召
- 平台差异：{platform_guide}

请直接输出 JSON。
"""


def _get_golden_hook_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    hook_type = pj.get("hook_type", "")
    persona = pj.get("persona", {})
    platform = state.get("platform", "douyin")

    return f"""请为口播短视频撰写黄金开头（0-5秒）。

【视频信息】
主题：{state.get("topic", "")}
出镜人：{persona.get("identity", "医生")} · {persona.get("tone_style", "邻家亲切型")}
目标平台：{platform}
开头类型：{hook_type}

{_HOOK_TYPES}

【输出格式（严格 JSON）】

{{
  "hook_type": "{hook_type}",
  "dialogue": "开头台词（≤40字，口语化）",
  "performance_note": "表演提示（表情/动作/道具/画面提示）",
  "time_range": "00:00-00:05"
}}

【黄金开头要求】
- ≤40字，3秒内必须抓住注意力
- 完全口语化，像说话不像写文章
- 短句为主，每句≤15字
- 第一个字不能是「我」（避免弱开场）
- 写完自己念一遍，念着别扭就改
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON。
"""


def _get_problem_setup_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    persona = pj.get("persona", {})
    outline = pj.get("script_outline", [])
    setup_plan = next((s for s in outline if s.get("section") == "problem_setup"), {})

    return f"""请为口播短视频撰写问题铺垫段（5-20秒）。

【视频信息】
主题：{state.get("topic", "")}
出镜人：{persona.get("identity", "医生")} · {persona.get("tone_style", "邻家亲切型")}
本段主题：{setup_plan.get("theme", "建立共鸣，让观众觉得'这说的就是我'")}

【输出格式（严格 JSON）】

{{
  "dialogue": "台词（≤100字，口语化，用/标注停顿位置）",
  "performance_note": "表演提示（表情/动作/画面提示）",
  "subtitle_highlights": ["需要在画面上放大/高亮的关键词1", "关键词2"],
  "time_range": "00:05-00:20"
}}

【问题铺垫要求】
- ≤100字，建立共鸣，让观众觉得"这说的就是我"
- 口语化：用"因为""所以""但是"，不用"由于""因此""然而"
- 句子≤20字，让观众跟得上
- 用/标注需要停顿的位置
- 不输出内部标注

请直接输出 JSON。
"""


def _get_core_knowledge_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    persona = pj.get("persona", {})
    core_point = pj.get("core_knowledge_point", "")
    outline = pj.get("script_outline", [])
    core_plan = next((s for s in outline if s.get("section") == "core_knowledge"), {})

    planner_block = ""
    if pj:
        planner_block = f"\n【脚本规划（必须遵循）】\n{_json.dumps(pj, ensure_ascii=False, indent=2)}\n"

    return f"""请为口播短视频撰写核心科普段（20-50秒）。

【视频信息】
主题：{state.get("topic", "")}
核心知识点：{core_point}
出镜人：{persona.get("identity", "医生")} · {persona.get("tone_style", "邻家亲切型")}
本段主题：{core_plan.get("theme", "讲清楚'是什么''为什么'")}
{planner_block}

【输出格式（严格 JSON）】

{{
  "dialogue": "台词（≤200字，口语化，信息密度最高的部分）",
  "rhythm_marks": {{
    "pauses": ["需要停顿的位置（引用原文片段）"],
    "emphasis": ["需要加重语气的词"],
    "gestures": ["需要配合手势/指向的位置"]
  }},
  "visual_aids": "需要插入的图示/动画/文字版说明",
  "performance_note": "表演提示",
  "time_range": "00:20-00:50"
}}

【核心科普要求】
- ≤200字，这是信息密度最高的部分
- 讲清楚"是什么"和"为什么"
- 口语化，短句为主，每句≤20字
- 标注所有停顿⏸、加重⬆、手势👆——这些是口播的"标点符号"
- 可用类比让复杂概念好懂
- 不输出内部标注

请直接输出 JSON。
"""


def _get_practical_tips_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    persona = pj.get("persona", {})

    return f"""请为口播短视频撰写实用建议段（50-65秒）。

【视频信息】
主题：{state.get("topic", "")}
出镜人：{persona.get("identity", "医生")} · {persona.get("tone_style", "邻家亲切型")}

【输出格式（严格 JSON）】

{{
  "dialogue": "台词（≤100字，'那到底应该怎么办'，给出具体建议）",
  "tips_list": [
    "第一，具体可操作的建议",
    "第二，...",
    "第三，..."
  ],
  "performance_note": "表演提示（如：伸出手指比1/2/3）",
  "time_range": "00:50-01:05"
}}

【实用建议要求】
- ≤100字，给出可操作的具体建议
- 用"第一""第二""第三"结构化
- 建议要具体：❌"注意饮食" ✅"每天盐不超过一啤酒瓶盖"
- 不涉及具体药物名称或剂量
- 不输出内部标注

请直接输出 JSON。
"""


def _get_closing_hook_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    closing_type = pj.get("closing_type", "")
    persona = pj.get("persona", {})
    platform = state.get("platform", "douyin")

    platform_cta = {
        "douyin": "关注+点赞",
        "kuaishou": "双击+关注",
        "bilibili": "一键三连",
        "wechat": "转发+在看",
        "xiaohongshu": "收藏+点赞",
    }.get(platform, "关注+转发")

    return f"""请为口播短视频撰写收尾钩子（最后5-10秒）。

【视频信息】
主题：{state.get("topic", "")}
出镜人：{persona.get("identity", "医生")} · {persona.get("tone_style", "邻家亲切型")}
收尾类型：{closing_type}
平台互动方式：{platform_cta}

{_CLOSING_TYPES}

【输出格式（严格 JSON）】

{{
  "closing_type": "{closing_type}",
  "dialogue": "收尾台词（≤60字）",
  "performance_note": "表演提示",
  "time_range": "最后5-10秒"
}}

【收尾钩子要求】
- ≤60字，结尾必有行动号召或留钩
- 结合平台特色互动方式（{platform_cta}）
- 语气亲切有力，不强硬
- 不输出内部标注

请直接输出 JSON。
"""


def _get_extras_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    persona = pj.get("persona", {})
    platform = state.get("platform", "douyin")

    return f"""请为口播短视频生成附加信息。

【视频信息】
主题：{state.get("topic", "")}
出镜人：{persona.get("identity", "医生")}
目标平台：{platform}

【输出格式（严格 JSON）】

{{
  "cover_title": "封面标题建议（≤15字，用于视频封面文字，要有点击欲）",
  "hashtags": ["#话题标签1", "#话题标签2", "#话题标签3", "#话题标签4", "#话题标签5"],
  "pinned_comment": "评论区置顶内容（补充说明/引用来源/互动问题）",
  "filming_notes": {{
    "scene": "拍摄场景建议",
    "outfit": "着装建议",
    "props": "道具建议",
    "special_shots": "特殊画面需求"
  }}
}}

【附加信息要求】
- cover_title ≤15字，决定点击率，要有"不看亏了"的感觉
- hashtags 5个，混合热门标签和精准标签
- pinned_comment 可以放补充来源或引导互动
- 不输出内部标注

请直接输出 JSON。
"""


class OralScriptWriter(BaseAgent):
    """口播脚本 Agent：script_plan 规划 → 5 段脚本 → 附加信息"""

    module = "oral_script"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        dispatch = {
            "script_plan": _get_script_plan_prompt,
            "golden_hook": _get_golden_hook_prompt,
            "problem_setup": _get_problem_setup_prompt,
            "core_knowledge": _get_core_knowledge_prompt,
            "practical_tips": _get_practical_tips_prompt,
            "closing_hook": _get_closing_hook_prompt,
            "extras": _get_extras_prompt,
        }
        fn = dispatch.get(self.section_type)
        if fn:
            return fn(state)
        return _get_core_knowledge_prompt(state)

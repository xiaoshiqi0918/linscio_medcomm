"""患者手册 Agent - 形式族 D 互动类"""
from app.agents.base import BaseAgent
from app.agents.prompts.audiences import AUDIENCE_PROFILES
from app.agents.prompts.loader import load_handbook


def _get_cover_prompt(state: dict) -> str:
    tpl = load_handbook("cover")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            target_audience=state.get("target_audience", "patient"),
        )
    return _default_cover(state)


def _default_cover(state: dict) -> str:
    return f"""请为患者教育手册生成封面文案。

【手册信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
适用人群：{state.get('target_audience', 'patient')}

【输出格式（JSON）】

{{
  "main_title": "手册主标题（≤15字，清晰说明手册内容）",
  "sub_title": "副标题（≤25字，说明手册的价值/用途）",
  "tagline": "一句话口号（≤20字，给患者信心和安全感）",
  "cover_visual_desc": "封面主视觉（英文，30-40词，医疗专业感但温暖友好）",
  "institution_placeholder": "[医院名称/科室名称]",
  "edition_note": "版本说明（如：2026年版，仅供参考，请遵医嘱）"
}}

封面基调：专业但温暖，给患者安全感，不引起恐惧。

请直接输出 JSON，不要有其他文字。
"""


def _get_disease_intro_prompt(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get("patient", AUDIENCE_PROFILES["public"])
    tpl = load_handbook("disease_intro")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_vocabulary=audience["vocabulary"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return _default_disease_intro(state, audience)


def _default_disease_intro(state: dict, audience: dict) -> str:
    return f"""请为患者教育手册撰写疾病介绍部分。

【手册信息】
疾病/主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
读者：患者及家属

【内容要求】

疾病介绍需要回答患者最想知道的三个问题：

**Q1：这是什么病？（100-150字）**
- 用最简单的语言解释疾病是什么
- 类比优先：找一个日常生活中的事物类比
- 不要用病理学定义开场

**Q2：为什么我会得这个病？（100-150字）**
- 列出主要病因（不超过4个）
- 区分"可以改变的因素"和"不可以改变的因素"
- 语气：理解，不批判（即使是不良生活习惯）

**Q3：这个病危险吗？（80-120字）**
- 客观描述疾病的危害（不夸大，不轻描淡写）
- 强调早发现早治疗的重要性
- 结尾给予信心：通过规范管理可以…

【语言规范】
{audience['vocabulary']}
{audience['tone']}
句长：{audience['sentence']}

【格式】
使用小标题 + 段落格式
可以用★或•列举要点
"""


def _get_symptoms_prompt(state: dict) -> str:
    tpl = load_handbook("symptoms")
    if tpl:
        return tpl.format(topic=state.get("topic", ""))
    return _default_symptoms(state)


def _default_symptoms(state: dict) -> str:
    return f"""请为患者教育手册撰写症状识别部分。

【手册信息】
疾病：{state.get('topic', '')}

【内容结构】

**常见症状**
列出主要症状（4-6个），每条格式：
[症状名称]：[通俗描述患者会有的感受]
示例：
多尿：感觉经常想去洗手间，有时夜里也要起来如厕

**需要立即就医的信号（警示框）**
⚠️ 【注意】如果出现以下情况，请立即就医或拨打急救：
· [紧急症状1]
· [紧急症状2]
· [紧急症状3]

**容易忽视的症状**
[1-2个患者常忽视的早期症状，提醒重视]

【特别要求】
- 症状描述用患者的感受表达，而不是医学体征描述
  ✅ "感觉眼睛看东西变模糊了，擦眼睛也没用"
  ❌ "视力下降，视野模糊"
- 最后必须附加：
  "⚠️ 以上症状仅供参考，出现相关症状请及时就医，由医生进行专业诊断。"
"""


def _get_treatment_prompt(state: dict) -> str:
    tpl = load_handbook("treatment")
    if tpl:
        return tpl.format(topic=state.get("topic", ""), specialty=state.get("specialty", ""))
    return _default_treatment(state)


def _default_treatment(state: dict) -> str:
    return f"""请为患者教育手册撰写治疗方案概述部分。

【手册信息】
疾病：{state.get('topic', '')}
专科：{state.get('specialty', '')}

【内容要求】

治疗部分需要让患者理解"治疗大方向"，而不是给出具体方案。

**治疗目标**（50-80字）
用患者能理解的语言说明治疗要达到什么效果

**主要治疗方式**（每种50-80字）
列出主要的治疗方向（2-4种），格式：
[治疗方式名称]
适用情况：[简述]
作用：[通俗解释这种治疗怎么帮助身体]
注意：[最重要的一个注意事项]

【严格禁止】
❌ 不提及任何具体药物名称
❌ 不给出任何剂量信息
❌ 不建议患者自行选择治疗方式

必须在结尾加：
【医嘱】治疗方案需要由您的主治医生根据您的具体情况制定，请务必遵医嘱，不要自行调整治疗。
"""


def _get_daily_care_prompt(state: dict) -> str:
    tpl = load_handbook("daily_care")
    if tpl:
        return tpl.format(topic=state.get("topic", ""))
    return _default_daily_care(state)


def _default_daily_care(state: dict) -> str:
    return f"""请为患者教育手册撰写日常注意事项部分。

【手册信息】
疾病：{state.get('topic', '')}

【内容结构（患者最关心的日常管理）】

**饮食管理**
- 3-4条具体建议
- 要具体可操作：❌"饮食清淡" ✅"烹饪时每道菜用盐不超过一个啤酒瓶盖的量"
- 告诉患者"可以吃什么"，不只是"不能吃什么"

**运动建议**
- 推荐的运动类型（温和的，大多数患者可以做的）
- 运动强度和时间的通俗描述（❌"中等强度有氧运动" ✅"运动时能说话但不能唱歌，这个强度正好"）
- 运动时需要注意的信号（什么时候应该停下来）

**日常监测**
- 需要患者自我监测的指标
- 如何记录（建议使用健康记录本或APP）
- 什么数值需要告知医生

**生活方式调整**
- 睡眠/压力/烟酒等相关建议
- 每条都要说明原因（"因为……所以……"）

【语言要求】
实用性 > 全面性。每条建议能立刻执行，不是空泛原则。
"""


def _get_visit_tips_prompt(state: dict) -> str:
    tpl = load_handbook("visit_tips")
    if tpl:
        return tpl.format(topic=state.get("topic", ""), specialty=state.get("specialty", ""))
    return _default_visit_tips(state)


def _default_visit_tips(state: dict) -> str:
    return f"""请为患者教育手册撰写就诊提示部分。

【手册信息】
疾病：{state.get('topic', '')}
专科：{state.get('specialty', '')}

【内容结构（帮助患者更有效地就诊）】

**就诊前准备**
- 需要携带的资料/检查报告
- 需要提前记录的信息（症状日记）
- 就诊前注意事项（如空腹要求等）

**和医生沟通的清单**
列出患者应该主动问医生的5个问题：
① [最重要的问题]
② [治疗相关的问题]
③ [日常管理相关的问题]
④ [副作用/注意事项相关的问题]
⑤ [复诊/随访相关的问题]

**复诊频率参考**
说明一般建议的复诊周期（用"通常"/"一般"等非绝对化表述）
强调：具体复诊计划由医生制定

**紧急联系指引**
列出需要立即寻求帮助的情况
提示拨打120或前往急诊的时机

【结尾】
"您是自己健康的第一责任人。与您的医疗团队保持良好沟通，是管理好疾病的关键。"
"""


def _get_fallback_prompt(state: dict, section_type: str) -> str:
    tpl = load_handbook("fallback")
    if tpl:
        return tpl.format(
            section_type=section_type,
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
        )
    return f"""请为患者教育手册撰写「{section_type}」部分。

疾病/主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：患者及家属

格式要求：
- 语言简洁，适合患者直接阅读
- 重要提示用【注意】标注
- 医嘱类内容用【医嘱】标注
- 避免专业术语，必须使用时括号内附通俗解释
- 不给出具体用药剂量
"""


_PROMPT_FUNCS = {
    "cover_copy": _get_cover_prompt,
    "disease_intro": _get_disease_intro_prompt,
    "symptoms": _get_symptoms_prompt,
    "treatment": _get_treatment_prompt,
    "daily_care": _get_daily_care_prompt,
    "visit_tips": _get_visit_tips_prompt,
}


class HandbookSectionAgent(BaseAgent):
    """患者教育手册 Agent，各节使用规范级 prompt"""

    module = "patient_handbook"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        func = _PROMPT_FUNCS.get(self.section_type)
        if func:
            return func(state)
        return _get_fallback_prompt(state, self.section_type)

"""患者手册 Agent — 实用至上，语言直白，可操作可勾选"""
import json as _json
from app.agents.base import BaseAgent


def _get_handbook_plan_prompt(state: dict) -> str:
    return f"""请为患者教育手册生成整体规划信息。

【手册信息】
疾病/主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}

【输出格式（严格 JSON）】

{{
  "disease_name": "疾病/主题名称",
  "target_audience": "适用人群（如：新确诊2型糖尿病患者及家属）",
  "distribution_scene": "门诊诊后|住院期间|出院随访|线上下载",
  "print_spec": "A5对折|A5骑马钉|A4单张|电子PDF",
  "total_pages": "预估页数（8-16页）",
  "layout_spec": {{
    "body_font_size": "12pt（老年患者建议14pt）",
    "title_font_size": "16-18pt",
    "line_spacing": "1.5倍以上",
    "primary_color": "主色调建议",
    "symbols": ["⬜ 勾选框", "⚠ 警告", "💡 提示", "✗ 禁止"]
  }},
  "section_outline": [
    {{"part": 1, "title": "认识疾病", "pages": "1-2页", "focus": "..."}},
    {{"part": 2, "title": "治疗方案", "pages": "2-3页", "focus": "..."}},
    {{"part": 3, "title": "日常管理", "pages": "2-3页", "focus": "..."}},
    {{"part": 4, "title": "复诊与随访", "pages": "1页", "focus": "..."}},
    {{"part": 5, "title": "紧急情况", "pages": "1页", "focus": "..."}},
    {{"part": 6, "title": "常见问题", "pages": "1-2页", "focus": "..."}}
  ]
}}

【规划原则】
- 实用至上：患者拿到就能用
- 语言直白：全程用"你"，不用"患者应当"
- 留足填写空间：手册是被"用"的，不只是被"读"的
- 紧急情况页建议印成红色或加色块高亮

请直接输出 JSON。
"""


def _get_cover_prompt(state: dict) -> str:
    meta = state.get("format_meta", {})
    pj = meta.get("planner_json", {})
    audience = pj.get("target_audience", "患者及家属")

    planner_block = ""
    if pj:
        planner_block = f"\n【手册规划（必须遵循）】\n{_json.dumps(pj, ensure_ascii=False, indent=2)}\n"

    return f"""请为患者教育手册生成封面内容。

【手册信息】
疾病/主题：{state.get("topic", "")}
适用人群：{audience}
{planner_block}

【输出格式（严格 JSON）】

{{
  "main_title": "手册标题（≤20字，如：糖尿病自我管理手册）",
  "sub_title": "副标题/一句话定位（≤30字，如：您的控糖随身指南）",
  "cover_visual_desc": "封面视觉描述（英文，30-50词）",
  "institution_placeholder": "[医院名称/科室名称]",
  "edition_note": "版本说明（如：2026年版）"
}}

【封面基调】
- 专业但温暖，给患者安全感
- 标题清晰说明手册内容，不玩文字游戏
- 不引起恐惧

请直接输出 JSON。
"""


def _get_disease_know_prompt(state: dict) -> str:
    return f"""请为患者教育手册撰写"认识疾病"部分（第一部分，1-2页）。

【手册信息】
疾病/主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}

【输出格式（严格 JSON）】

{{
  "section_title": "了解你的身体正在发生什么",
  "what_is_it": {{
    "question": "我得了什么病？",
    "answer": "用≤100字告诉患者这个病是怎么回事（通俗类比优先）"
  }},
  "why_me": {{
    "question": "为什么是我？",
    "intro": "常见病因（勾选框让患者对照自身情况）",
    "checkboxes": [
      "⬜ 病因1（如：家族中有人患此病）",
      "⬜ 病因2",
      "⬜ 病因3",
      "⬜ 病因4"
    ]
  }},
  "is_it_serious": {{
    "question": "这个病严重吗？",
    "answer": "诚实但不制造恐慌，重点放在'可控'上（≤100字）"
  }},
  "illustration_hint": "配图建议（简单示意图：病变部位/发病机制简图）"
}}

【写作规范】
- 全程用"你"称呼患者
- 医学术语必须配通俗解释，或直接用大白话替代
- "为什么是我"部分用勾选框，让患者自主对照
- "严重吗"部分诚实但给信心：强调"通过规范管理可以…"
- 不输出 [共识]、[推断]、[[待补充]] 等内部标注

请直接输出 JSON。
"""


def _get_treatment_prompt(state: dict) -> str:
    return f"""请为患者教育手册撰写"治疗方案"部分（第二部分，2-3页）。

【手册信息】
疾病/主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}

【输出格式（严格 JSON）】

{{
  "section_title": "医生为你制定的方案",
  "treatment_plan_template": {{
    "diagnosis_placeholder": "主要诊断：_______________",
    "treatment_options": ["⬜ 药物治疗", "⬜ 手术", "⬜ 生活方式干预", "⬜ 联合治疗"],
    "plan_note": "方案说明（由医生填写）：_______________"
  }},
  "medication_table": {{
    "intro": "我的用药清单（请与医生一起填写）",
    "columns": ["药名", "剂量", "服用时间", "注意事项", "我的记录"],
    "rows": 3,
    "note": "表格供患者/医生填写，每行末尾附 ⬜ 已服用 勾选框"
  }},
  "medication_faq": [
    {{
      "q": "忘记吃药怎么办？",
      "a": "具体、安全的建议（≤60字）"
    }},
    {{
      "q": "可以自己停药吗？",
      "a": "强调不可自行停药的原因（≤60字）"
    }},
    {{
      "q": "出现哪些副作用需要联系医生？",
      "a": "列出3-4个常见需要注意的信号（≤80字）"
    }}
  ],
  "medical_order": "【医嘱】治疗方案需要由您的主治医生根据您的具体情况制定，请务必遵医嘱，不要自行调整治疗。"
}}

【写作规范】
- 不提及任何具体药物名称或剂量（用药清单由患者/医生填写）
- 治疗方案解释用患者能理解的语言
- 全程用"你"称呼
- 结尾必须附医嘱声明
- 不输出内部标注

请直接输出 JSON。
"""


def _get_daily_care_prompt(state: dict) -> str:
    return f"""请为患者教育手册撰写"日常管理"部分（第三部分，2-3页）。

【手册信息】
疾病/主题：{state.get("topic", "")}

【输出格式（严格 JSON）】

{{
  "section_title": "每天可以做的事",
  "diet": {{
    "title": "饮食指导",
    "recommended": "推荐食物（具体、可操作）",
    "limited": "限制食物",
    "forbidden": "禁忌食物",
    "sample_menu": {{
      "breakfast": "早餐示例",
      "lunch": "午餐示例",
      "dinner": "晚餐示例",
      "snack": "加餐示例"
    }}
  }},
  "exercise": {{
    "title": "运动指导",
    "recommended_types": "推荐运动类型",
    "frequency": "频率和时长（通俗描述）",
    "cautions": "运动禁忌/注意（什么时候应该停下来）"
  }},
  "lifestyle_checklist": {{
    "title": "生活习惯",
    "items": [
      "⬜ 习惯1（具体可执行）",
      "⬜ 习惯2",
      "⬜ 习惯3",
      "⬜ 习惯4"
    ]
  }},
  "self_monitoring": {{
    "title": "自我监测",
    "what_to_monitor": "需要监测的指标",
    "how_to_record": "如何记录（建议使用记录本或APP）",
    "table_columns": ["日期", "时间", "数值", "备注"],
    "table_rows": 5,
    "alert_values": "什么数值需要告知医生"
  }}
}}

【写作规范】
- 具体可操作：❌"饮食清淡" ✅"烹饪时每道菜用盐不超过一个啤酒瓶盖的量"
- 运动强度通俗描述：❌"中等强度有氧运动" ✅"运动时能说话但不能唱歌，这个强度正好"
- 生活习惯用勾选框，让患者每天自查
- 告诉患者"可以做什么"，不只是"不能做什么"
- 不输出内部标注

请直接输出 JSON。
"""


def _get_followup_prompt(state: dict) -> str:
    return f"""请为患者教育手册撰写"复诊与随访"部分（第四部分，1页）。

【手册信息】
疾病/主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}

【输出格式（严格 JSON）】

{{
  "section_title": "什么时候需要回来看医生",
  "followup_plan": {{
    "next_visit": "下次复诊时间：_______________（由医生填写）",
    "required_tests": "复诊需要做的检查（列出常规检查项目）",
    "preparation": "复诊前需要准备的（如：带上用药记录、监测记录等）"
  }},
  "regular_check_table": {{
    "title": "定期检查清单",
    "columns": ["检查项目", "建议频率", "上次日期", "下次日期"],
    "items": [
      {{
        "test_name": "检查项目1",
        "frequency": "建议频率（如：每3个月）",
        "last_date": "_______________",
        "next_date": "_______________"
      }},
      {{
        "test_name": "检查项目2",
        "frequency": "建议频率",
        "last_date": "_______________",
        "next_date": "_______________"
      }},
      {{
        "test_name": "检查项目3",
        "frequency": "建议频率",
        "last_date": "_______________",
        "next_date": "_______________"
      }}
    ]
  }},
  "doctor_questions": [
    "最重要的问题（如：我的病情有变化吗？）",
    "治疗相关（如：药物需要调整吗？）",
    "日常管理相关",
    "副作用/注意事项相关",
    "下次复诊相关"
  ]
}}

【写作规范】
- 表格留足填写空间（日期栏用下划线占位）
- 复诊频率用"一般建议"等非绝对化表述
- 具体检查计划由医生制定，手册仅提供常规参考
- 不输出内部标注

请直接输出 JSON。
"""


def _get_emergency_prompt(state: dict) -> str:
    return f"""请为患者教育手册撰写"紧急情况"部分（第五部分，1页）。

【手册信息】
疾病/主题：{state.get("topic", "")}

【输出格式（严格 JSON）】

{{
  "section_title": "出现这些情况请立即就医",
  "danger_signals": [
    {{
      "signal": "⚠ 危险信号1（大号加粗描述）",
      "description": "简短说明什么情况下算这个信号（≤30字）"
    }},
    {{
      "signal": "⚠ 危险信号2",
      "description": "..."
    }},
    {{
      "signal": "⚠ 危险信号3",
      "description": "..."
    }},
    {{
      "signal": "⚠ 危险信号4",
      "description": "..."
    }}
  ],
  "emergency_contacts": {{
    "emergency_phone": "急诊电话：120",
    "doctor_phone": "主治医生电话：_______________",
    "nurse_station": "护士站电话：_______________",
    "nearest_er": "就近急诊地址：_______________"
  }},
  "design_note": "本页建议印成红色或加色块高亮，让人一翻就找到"
}}

【写作规范】
- 危险信号用患者能感知的症状描述，不用医学术语
- 信号描述简短有力，紧急感强
- 联系方式留填写空间（患者或医生填入具体电话）
- 不输出内部标注

请直接输出 JSON。
"""


def _get_faq_prompt(state: dict) -> str:
    return f"""请为患者教育手册撰写"常见问题"部分（第六部分，1-2页）。

【手册信息】
疾病/主题：{state.get("topic", "")}
专科：{state.get("specialty", "")}

【输出格式（严格 JSON）】

{{
  "section_title": "您可能还想知道",
  "questions": [
    {{
      "q": "患者最常问的问题1",
      "a": "直白、实用的回答（≤80字）"
    }},
    {{
      "q": "问题2",
      "a": "回答（≤80字）"
    }},
    {{
      "q": "问题3",
      "a": "回答（≤80字）"
    }},
    {{
      "q": "问题4",
      "a": "回答（≤80字）"
    }},
    {{
      "q": "问题5",
      "a": "回答（≤80字）"
    }}
  ],
  "caregiver_note": {{
    "title": "给家属的话",
    "content": "针对照护者的实用建议（≤100字），照护者也是重要读者"
  }}
}}

【写作规范】
- 问题选择患者和家属真正关心的（饮食、运动、工作、生活质量等）
- 回答直白实用，不回避问题
- 不涉及具体药物名称或剂量
- 加入"给家属的话"，照护者也是重要读者
- 不输出内部标注

请直接输出 JSON。
"""


def _get_back_cover_prompt(state: dict) -> str:
    return f"""请为患者教育手册生成封底内容。

【手册信息】
疾病/主题：{state.get("topic", "")}

【输出格式（严格 JSON）】

{{
  "encouragement": "一句鼓励的话（≤30字，给患者信心和温暖）",
  "institution_info": "[医院名称/科室名称]",
  "qr_code_placeholder": "二维码/线上资源链接：_______________",
  "disclaimer": "本手册仅供健康教育参考，不替代医生诊疗意见。如有疑问，请咨询您的主治医生。",
  "version": "版本号：V1.0 / 更新日期：_______________"
}}

【封底基调】
- 温暖鼓励，给患者信心
- 免责声明必须包含

请直接输出 JSON。
"""


_PROMPT_FUNCS = {
    "handbook_plan": _get_handbook_plan_prompt,
    "cover": _get_cover_prompt,
    "disease_know": _get_disease_know_prompt,
    "treatment": _get_treatment_prompt,
    "daily_care": _get_daily_care_prompt,
    "followup": _get_followup_prompt,
    "emergency": _get_emergency_prompt,
    "faq": _get_faq_prompt,
    "back_cover": _get_back_cover_prompt,
}


class HandbookSectionAgent(BaseAgent):
    """患者教育手册 Agent：handbook_plan 规划 → 封面 → 6大部分 → 封底"""

    module = "patient_handbook"

    def __init__(self, section_type: str):
        self.section_type = section_type

    def get_base_prompt(self, state: dict) -> str:
        func = _PROMPT_FUNCS.get(self.section_type)
        if func:
            return func(state)
        return f"""请为患者教育手册撰写「{self.section_type}」部分。
疾病/主题：{state.get('topic', '')}
全程用"你"称呼患者，语言直白，输出 JSON 格式。
"""

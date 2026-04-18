"""
受众适配矩阵（v2.0 修订）
所有任务提示词通过 {audience_profile} 变量注入
"""
from app.agents.prompts.loader import load_children_audience_patch

_DEFAULT_CHILDREN_PATCH = """【儿童受众专属规范（必须遵守）】

目标读者：3-12岁儿童，阅读能力有限，需图文配合

▌语言标准
· 句长：每句6-15字（下限保证流畅，上限确保简单）
· 词汇：小学一二年级词汇，每句只表达一个意思
· 类比：使用动物、玩具、食物、学校等儿童熟悉的事物

▌禁止事项
· 复杂从句、抽象概念、引起恐惧的内容
· 连接词："并且""因为""所以"（用短句自然衔接代替）
· 注射器、针头、血液、伤口、哭泣或痛苦表情等恐吓元素

▌风格
活泼有趣、充满好奇，像讲故事，不是上课。
"""

CHILDREN_AUDIENCE_PATCH = load_children_audience_patch() or _DEFAULT_CHILDREN_PATCH

AUDIENCE_PROFILES = {
    "public": {
        "desc": "普通大众，无医学背景，初中文化水平",
        "vocabulary": "完全日常用语，专业词首次出现必须括号内附通俗说法",
        "sentence": "简洁为主，大多数句子短一些，偶尔可用一个长句展开解释",
        "analogy": "选读者生活中熟悉的事物做类比，不限领域",
        "tone": "亲切自然不说教，像朋友聊天",
        "forbidden": "英文缩写、统计学术语、被动语态密集、从句嵌套",
    },
    "patient": {
        "desc": "患者及家属，有基本就医经验，了解自身病情",
        "vocabulary": "允许已解释过的医学词，首次出现必须解释",
        "sentence": "允许稍长的解释句，但核心信息用短句",
        "analogy": "选与读者就医或生活体验相关的事物做类比",
        "tone": "理解与共情，给予信心，不回避困难信息",
        "forbidden": "恐吓性表述、具体剂量建议、替代医嘱",
    },
    "student": {
        "desc": "医学生，有系统医学知识，需巩固临床理解",
        "vocabulary": "可用标准医学术语，鼓励与基础知识关联",
        "sentence": "句子长度自然即可，复杂机制可用长句，但避免从句堆砌",
        "analogy": "用生化/生理过程的形象化类比帮助理解机制",
        "tone": "严谨但生动，启发思考，关联临床实际",
        "forbidden": "过度简化、省略重要机制、将临床个案普遍化",
    },
    "professional": {
        "desc": "医疗专业人员，具备完整临床知识",
        "vocabulary": "标准医学术语，可引用指南级别表述",
        "sentence": "句子长度不限，但避免过长从句堆砌",
        "analogy": "同行交流风格；需要类比时，选机制精确的科学类比",
        "content_focus": "强调临床意义、证据级别、与现有实践的关联",
        "tone": "专业、简洁、基于证据",
        "forbidden": "过度通俗化、浪费篇幅解释基础概念",
    },
    "children": {
        "desc": "3-12岁儿童，阅读能力有限，需图文配合",
        "vocabulary": "小学一二年级词汇，每句一个意思",
        "sentence": "每句6-15字（下限保证流畅，上限确保简单）",
        "analogy": "动物/玩具/食物/学校等儿童熟悉的事物",
        "tone": "活泼有趣充满好奇，像讲故事",
        "forbidden": '复杂从句、抽象概念、引起恐惧的内容、「并且/因为/所以」等连接词',
        "framework_patch": True,
    },
}


# ────────────────────────────────────────────
# 写作风格注册表：platform × audience → 统一风格配置
# ────────────────────────────────────────────

WRITING_STYLES = {
    "casual_oral": {
        "name": "科普口语",
        "register": "口语化科普——像在跟朋友说一件事，轻松、亲近、不讲究文法",
        "persona": "你是一个做健康科普短视频的医生博主，语气轻松有趣但内容准确。",
        "terminology": "极低。专业术语必须转化为日常说法，首次出现用生活化解释替代",
        "data_rigor": "模糊化处理（'不少人''大约一半'），不使用[N]引用角标",
        "sentence_style": "短句为主，大多数≤20字。可以用问句、感叹句、省略句",
        "emotion": "轻松亲近，可以用'说白了''你想啊''其实吧'",
        "ending": "给一个简单的行动建议就结束",
        "forbidden": "[N]引用角标、学术术语密集使用、长从句、被动语态",
        "typical": "'其实吧' '说白了' '你有没有发现'",
        "citation_mode": "none",
    },
    "serious_popular": {
        "name": "严肃科普",
        "register": "半正式科普——平实准确，带[N]文献引用，比论文易读但不口语化",
        "persona": "你是一位给专业健康媒体写专栏的临床医生，稿件带文献引用，面向有一定知识基础的读者。",
        "terminology": "高。标准医学术语可直接使用，可附英文对照",
        "data_rigor": "严谨——数据带范围和限定条件，引用标注[N]规范使用",
        "sentence_style": "中长句为主，因果链条完整。句长自然，不刻意求短也不堆砌",
        "emotion": "中性专业，可以有个人判断但不情绪化",
        "ending": "总结临床意义或给出循证建议",
        "forbidden": "口语词（'其实吧''折腾''咱们'）、戏剧化修辞、感叹句渲染",
        "typical": "'临床实践中' '相关研究显示' '证据表明'",
        "citation_mode": "bracket_n",
    },
    "wechat_popular": {
        "name": "公众号科普",
        "register": "公众号科普——像医生朋友跟你聊天，口语化但有知识增量，用生活类比解释专业概念",
        "persona": "你是一个在健康类公众号写文章的临床医生，读者是关注健康的普通人。你用聊天的口吻讲专业知识，会分享自己的临床经历，善于用生活类比让抽象概念变具体。你的文章有课堂互动感，偶尔幽默，让读者在轻松的氛围中获取硬核医学知识。",
        "terminology": "低到中。术语首次出现时用生活化类比或括号附通俗解释（如'甘油三酯（TG）'后跟类比解释其功能）。同一概念后续可直接用缩写",
        "data_rigor": "轻引用——关键数据直接说来源名称（如'根据《中国血脂管理指南（2023）》'），不用[N]角标。数据不追求精确区间，可以用'将近40个人'这样的口语化表述",
        "sentence_style": "以口语化中等长度的句子为主（15-35字），偶尔用一个极短的判断句（5-10字）点睛。不要刻意交替长短句——连续几句差不多长是正常的，关键是偶尔来一句特别短的打破节奏。句内需要解释时用冒号引出，少用破折号。允许适度的幽默或有趣的类比（如果它和主题沾边且能帮助理解）",
        "emotion": "真实共情+课堂互动——可以写个人经历（'我慌啦'），用'敲黑板''有请主角'等课堂互动词，允许适度幽默（如用流行文化梗辅助理解），但不刻意煽情",
        "ending": "实操建议清单或就医指引，可以有简短总结",
        "forbidden": "论文腔（'本文将探讨'）、[N]角标（公众号读者看不懂）、纯学术术语不解释、被动语态堆砌、名词化公文表达、没有人味的匀速行文、连续使用3个以上逻辑连接词（因此/然而/此外/同时）",
        "typical": "'今天我们来聊聊' '大家应该都听说过' '简单理解就是' '敲黑板！' '有请主角' '可就伟大了'",
        "citation_mode": "inline_name",
    },
}

# platform × audience → style_key 映射
_STYLE_MAPPING: dict[tuple[str, str], str] = {
    # 微信公众号：面向大众/患者用公众号风，面向专业用严肃风
    ("wechat", "public"): "wechat_popular",
    ("wechat", "patient"): "wechat_popular",
    ("wechat", "student"): "serious_popular",
    ("wechat", "professional"): "serious_popular",
    # 抖音/快手：口语风为主
    ("douyin", "public"): "casual_oral",
    ("douyin", "patient"): "casual_oral",
    # 小红书：公众号风
    ("xiaohongshu", "public"): "wechat_popular",
    ("xiaohongshu", "patient"): "wechat_popular",
    # B站：公众号风
    ("bilibili", "public"): "wechat_popular",
    ("bilibili", "patient"): "wechat_popular",
    # 期刊：严肃风
    ("journal", "public"): "serious_popular",
    ("journal", "patient"): "serious_popular",
    ("journal", "student"): "serious_popular",
    ("journal", "professional"): "serious_popular",
    # 线下印刷：严肃风
    ("offline", "public"): "serious_popular",
    ("offline", "patient"): "serious_popular",
    ("offline", "professional"): "serious_popular",
}


def resolve_writing_style(
    platform: str = "wechat",
    target_audience: str = "public",
) -> dict:
    """根据 platform + audience 返回完整的风格配置 dict。"""
    key = _STYLE_MAPPING.get(
        (platform, target_audience),
        _STYLE_MAPPING.get((platform, "public"), "wechat_popular"),
    )
    if isinstance(key, dict):
        return key
    return WRITING_STYLES.get(key or "wechat_popular", WRITING_STYLES["wechat_popular"])

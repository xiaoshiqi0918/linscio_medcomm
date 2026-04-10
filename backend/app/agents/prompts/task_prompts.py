"""
Layer 3：任务提示词
按 content_format + section_type 返回详细任务指令
优先从 prompt-example/prompts/task/*.txt 加载，不存在时使用内置 f-string
"""
from app.agents.prompts.audiences import AUDIENCE_PROFILES
from app.agents.prompts.loader import load_platform_config, load_task


# ═══ 章节字数按全文目标自动分配 ═══

_SECTION_WORD_RATIOS: dict[str, dict[str, float]] = {
    "article": {"intro": 0.10, "body": 0.45, "case": 0.0, "qa": 0.22, "summary": 0.15},
    "story": {
        "hook": 0.08,            # 引子 100-200字
        "development": 0.22,     # 发展 300-500字
        "turning_point": 0.16,   # 转折·就医 200-400字
        "science_core": 0.27,    # 科普核心 400-600字
        "resolution": 0.14,      # 结局 200-300字
        "action_list": 0.08,     # 行动清单 100-200字
        "closing_quote": 0.05,   # 结尾金句
    },
    "debunk": {
        "rumor_present": 0.11,   # 谣言还原 100-200字
        "verdict": 0.05,         # 真相判定 50-100字
        "debunk_1": 0.15,        # 拆解·漏洞1
        "debunk_2": 0.15,        # 拆解·漏洞2
        "debunk_3": 0.15,        # 拆解·漏洞3（可选）
        "correct_practice": 0.18,  # 正确做法 200-300字
        "anti_fraud": 0.09,      # 防骗指南 100-150字
    },
    "qa_article": {
        "qa_intro": 0.03,        # 问题引入 40-70字
        "qa_1": 0.18,            # 问答1·入门 200-400字
        "qa_2": 0.18,            # 问答2·入门 200-400字
        "qa_3": 0.18,            # 问答3·进阶 200-400字
        "qa_4": 0.18,            # 问答4·实操（可选）
        "qa_5": 0.18,            # 问答5·特殊（可选）
        "qa_summary": 0.07,      # 总结 100-170字
    },
    "research_read": {
        "one_liner": 0.03,       # 一句话摘要 ≤30字
        "study_card": 0.05,      # 研究信息卡 ~50字
        "why_matters": 0.15,     # 为什么值得关注 100-200字
        "methods": 0.20,         # 研究怎么做的 150-250字
        "findings": 0.27,        # 核心发现 200-300字
        "implication": 0.18,     # 对普通人意味着什么 150-200字
        "limitation": 0.12,      # 注意事项·研究局限 100-200字
    },
}

_PLATFORM_DEFAULT_WORD_COUNT = {
    "wechat": 1200,
    "xiaohongshu": 800,
    "douyin": 300,
    "journal": 3000,
    "offline": 2000,
}


def _section_word_target(state: dict) -> str:
    """根据全文目标字数和章节类型，返回当前章节的字数指引字符串。
    跳过的章节字数预算按比例重分配给剩余活跃章节。"""
    total = state.get("target_word_count")
    platform = state.get("platform", "wechat")
    if not total:
        total = _PLATFORM_DEFAULT_WORD_COUNT.get(platform, 1500)

    fmt = state.get("content_format", "article")
    st = state.get("section_type", "body")
    skip = set(state.get("skip_sections") or [])

    ratios = _SECTION_WORD_RATIOS.get(fmt, {})
    ratio = ratios.get(st, 0.0)

    if ratio <= 0 or st in skip:
        return ""

    active_total = sum(v for k, v in ratios.items() if v > 0 and k not in skip)
    if active_total <= 0:
        return ""
    total_positive = sum(v for v in ratios.values() if v > 0)
    adjusted_ratio = ratio / active_total * total_positive

    target = int(total * adjusted_ratio)
    lo = max(50, int(target * 0.8))
    hi = int(target * 1.2)
    return f"{lo}-{hi}字"

PLATFORM_WORD_GUIDE = {
    "wechat": "整体建议 800-2000 字，每节 150-400 字",
    "xiaohongshu": "整体建议 500-1000 字，每节 100-200 字，多用短句",
    "journal": "整体建议 1500-3000 字，每节 300-600 字",
    "offline": "整体建议 1000-2000 字，适合印刷阅读的段落节奏",
    "douyin": "整体建议 200-400 字，极度精炼",
    "universal": "整体建议 800-1500 字",
}

PLATFORM_HOOKS = {
    "wechat": "可以用反问句开头，或以一个读者身边可能发生的场景开头",
    "xiaohongshu": "用「你知道吗」或直接抛出一个让人惊讶的事实开头，第一句就要抓人",
    "journal": "以一个具有临床意义的现象或研究发现开头，略显正式",
    "douyin": "第一句就是最强的观点或最惊人的事实，没有铺垫",
    "offline": "用一个温暖的生活场景开头，亲切自然",
    "universal": "用一个读者普遍有共鸣的生活场景开头",
}

PLATFORM_FORMAT = {
    "wechat": "使用小标题（##）分隔各知识点，每节内容可用短段落+列表混合",
    "xiaohongshu": "多用短段落，每段 2-4 句，可适当加 emoji，但不超过 3 个/段",
    "journal": "段落为主，减少列表，语言偏正式但保持通俗",
    "douyin": "纯段落，每段最多 2 句，像在说话不像在写文章",
    "offline": "段落为主，偶尔用列表，适合印刷阅读的排版",
    "universal": "段落与列表混合，结构清晰",
}


def get_article_intro(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    platform_hooks = PLATFORM_HOOKS.get(state.get("platform", "wechat"), PLATFORM_HOOKS["universal"])
    tpl = load_task("article_intro")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform=state.get("platform", "wechat"),
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            audience_vocabulary=audience["vocabulary"],
            platform_hooks=platform_hooks,
        )
    return f"""请为以下医学科普文章撰写引言部分。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
平台风格：{state.get('platform', 'wechat')}

【写作要求】

▌语言标准
{audience['tone']}
句子长度：{audience['sentence']}
词汇要求：{audience['vocabulary']}

▌内容结构（按顺序呈现）
① 开场钩子（1-2句）
   {platform_hooks}
   不要用「随着医学的发展」或「在当今社会」等套话开头

② 建立共鸣（2-3句）
   让读者感受到「这个话题和我有关」
   可以描述目标读者群体常见的生活困扰或疑惑

③ 明确收益（1-2句）
   告诉读者读完这篇文章能解决什么问题、学到什么知识
   具体说，不要用「让我们一起来了解」这类空洞表述

▌字数要求
引言部分总字数：{_section_word_target(state) or '150-250字（抖音/小红书：50-100字）'}

▌禁止事项
- 不用「众所周知」「大家都知道」等开头
- 不用「本文将介绍」等论文式写法
- 不用感叹号密集的标题党风格
- 不要在引言里就开始讲知识点

请直接输出引言正文，不需要标注「引言」标题。

🚨 字数红线：引言必须控制在 {_section_word_target(state) or '150-250字'} 之间，超过上限必须删减。写完后请自查字数。
"""


def get_article_body(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    platform_format = PLATFORM_FORMAT.get(state.get("platform", "wechat"), PLATFORM_FORMAT["universal"])
    outline_ctx = state.get("outline_context", "")
    tpl = load_task("article_body")
    if tpl:
        outline_context_line = f"大纲参考：{outline_ctx}" if outline_ctx else ""
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform_format=platform_format,
            outline_context_line=outline_context_line,
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            audience_vocabulary=audience["vocabulary"],
            audience_analogy=audience["analogy"],
            audience_forbidden=audience["forbidden"],
        )
    wt = _section_word_target(state) or '400-800字（抖音：100-200字）'
    twc = state.get("target_word_count") or _PLATFORM_DEFAULT_WORD_COUNT.get(state.get("platform", "wechat"), 1500)
    skip = set(state.get("skip_sections") or [])
    body_ratio = _SECTION_WORD_RATIOS.get("article", {}).get("body", 0.45)
    active_total = sum(v for k, v in _SECTION_WORD_RATIOS.get("article", {}).items() if v > 0 and k not in skip)
    total_positive = sum(v for v in _SECTION_WORD_RATIOS.get("article", {}).values() if v > 0)
    adj_body_ratio = (body_ratio / active_total * total_positive) if active_total > 0 else body_ratio
    body_budget = int(twc * adj_body_ratio)
    if body_budget <= 350:
        max_points = 2
        point_hint = "精选 2 个核心知识点，每个 120-150 字"
    elif body_budget <= 700:
        max_points = 3
        point_hint = "精选 2-3 个核心知识点，每个 150-200 字"
    else:
        max_points = 4
        point_hint = "3-4 个核心知识点，每个 200-300 字"

    return f"""请为以下医学科普文章撰写正文核心部分。

🚨🚨🚨 最重要的规则——字数限制 🚨🚨🚨
本章节中文正文必须控制在 {wt} 之间。
这意味着你只能写 {max_points} 个知识点（{point_hint}），加上 1 处误区澄清。
超过上限的内容必须删减，宁可少覆盖一个话题也绝不可超字。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
平台格式：{platform_format}
{f'大纲参考：{outline_ctx}' if outline_ctx else ''}

【写作要求】

▌语言标准
风格：{audience['tone']}
句长：{audience['sentence']}
词汇：{audience['vocabulary']}
类比原则：{audience['analogy']}
禁止：{audience['forbidden']}

▌内容要求（严格控制在 {max_points} 个知识点以内）
① 知识点讲解（最多 {max_points} 个，每个独立一节）
   - 先给出结论，再展开解释（金字塔原则）
   - 每个知识点用一个具体的类比或例子说明
   - 如有争议的观点，明确说明「目前学界的主流观点认为」

② 误区澄清（至少 1 处，可融入知识点中）
   - 用「很多人以为……但实际上……」的结构
   - 纠正误区时语气平和，不批评读者

③ 数据处理
   - 如需引用数据但无文献来源支撑，使用 [[待补充：描述所需数据]] 占位
   - 有数据支撑时，以通俗方式表达（如「大约相当于10个人中有1个」）

④ 专业术语处理
   - 首次出现的专业术语：通俗说法（医学名称）
   - 示例：「血糖（简单说就是血液里的糖分含量）」

▌格式要求
{platform_format}

▌正文边界（必须遵守）
正文只负责知识讲解和误区澄清，以下内容留给后续的「小结」章节，正文中不要出现：
- 不要写「行动指南」「行动清单」「实用建议」等总结性行动建议章节
- 不要写「什么时候需要就医 / 寻求帮助」的就医提示段落
- 不要在末尾写情感收束、鼓励性结语或总结段
- 不要用「请记住」「总结一下」等收尾语开启最后一段
正文应在最后一个知识点或误区讲解完毕后自然结束，不做任何总结或升华。

▌严格禁止
- 不给出具体用药剂量
- 不引用具体指南或研究名称（除非 RAG 提供了确切来源）
- 不使用「一定会」「绝对」等绝对化表述
- 不出现「……请咨询度娘」等导流表述

请直接输出正文内容，可以包含小标题，不需要在开头写「正文」两字。
正文只写 {max_points} 个小节，每节控制在 150-200 字，全文不超过 {wt}。
"""


def get_article_case(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("article_case")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为以下医学科普文章撰写典型案例故事。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【案例写作规范】

▌案例性质声明
案例必须是虚构的，开头使用以下格式之一：
- 「王阿姨（化名）今年62岁，……」
- 「小李（化名）是一名28岁的上班族，……」
- 「李先生（化名）最近总是……」
注意：化名应选择普通、易记的中文名字，年龄和职业要符合目标读者群体

▌案例结构（严格按顺序）
① 人物与场景（50-80字）
   - 简洁描述案例人物的基本情况
   - 设置与主题相关的生活场景

② 问题出现（80-120字）
   - 描述症状或困惑的出现过程
   - 用目标读者能理解的语言，不用临床表述
   - 加入人物的心理活动，增加真实感

③ 就医/了解（60-100字）
   - 人物获得专业帮助的过程
   - 医生/专家的核心解释（通俗化处理）

④ 结果与收获（50-80字）
   - 人物的转变或改善
   - 读者能从中学到的关键点
   - 正向结尾，给读者信心和希望

▌语言要求
风格：{audience['tone']}
句长：{audience['sentence']}
叙事视角：第三人称，但贴近人物内心

▌禁止事项
- 不使用真实人名或地名
- 不描述具体用药过程（如需提及，用「在医生指导下接受了治疗」）
- 不以悲剧结尾（即使疾病预后不佳，也要给出积极的应对角度）
- 不出现「经过科学治疗，完全治愈」等过度乐观的表述

总字数：250-400字
请直接输出案例内容，案例标题可自行命名（如「他的经历让很多人受益」）。
"""


def get_article_qa(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("article_qa")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    qa_wt = _section_word_target(state) or '250-400字'
    twc_qa = state.get("target_word_count") or _PLATFORM_DEFAULT_WORD_COUNT.get(state.get("platform", "wechat"), 1500)
    skip_qa = set(state.get("skip_sections") or [])
    qa_ratio = _SECTION_WORD_RATIOS.get("article", {}).get("qa", 0.22)
    active_total_qa = sum(v for k, v in _SECTION_WORD_RATIOS.get("article", {}).items() if v > 0 and k not in skip_qa)
    total_positive_qa = sum(v for v in _SECTION_WORD_RATIOS.get("article", {}).values() if v > 0)
    adj_qa_ratio = (qa_ratio / active_total_qa * total_positive_qa) if active_total_qa > 0 else qa_ratio
    qa_budget = int(twc_qa * adj_qa_ratio)
    per_qa = min(150, max(80, qa_budget // 3))

    return f"""请为以下医学科普文章撰写常见问题解答（Q&A）部分。

🚨🚨🚨 最重要的规则——字数限制 🚨🚨🚨
Q&A 部分总字数必须控制在 {qa_wt} 之间。
写 3 个 Q&A，每个问答控制在 {per_qa} 字以内（含问题和回答）。
超过即删减，宁可回答更简短也不可超字。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【最重要原则：Q&A 必须与正文互补，严禁重复】
本文的引言、正文、案例部分已经完成（见上下文中的已完成章节）。
Q&A 的核心价值是补充正文未覆盖的读者疑惑，而不是用问答形式重述正文内容。
- 正文已详细讲解的知识点，绝对不能作为 Q&A 的问题或答案
- 必须站在读者角度思考：看完正文后，读者还会有什么新的困惑？
- 如需引用正文已有内容，仅用一句话带过（如"前文提到…"），回答主体必须是增量信息

【Q&A 写作规范】

▌问题设计（3个问题）
问题必须来自目标读者真实会有的疑惑，不是写作者自问自答的知识点。
选题原则：
- Q1：正文未展开的常见误区或困惑（如日常操作中的细节疑问）
- Q2：最实用的操作性问题（「我应该怎么做」类型，正文未详述的具体场景）
- Q3：最有争议或最让人担心的问题（正文未覆盖的顾虑或特殊情况）

问题的语气：
- 用普通读者的口吻提问，不用书面语
- ✅ 「血糖高了，自己能不能先控制饮食，不去看医生？」
- ❌ 「血糖升高时是否可以通过饮食干预代替药物治疗？」

▌回答规范
每个问题的回答结构：
① 直接给出核心答案（1-2句，先说结论）
② 简短解释原因（2-3句）
③ 给出实用建议或注意事项（1-2句）

回答语气：{audience['tone']}
回答句长：{audience['sentence']}
Q&A 部分总字数：{_section_word_target(state) or '250-400字'}，每个问答 80-150 字

▌禁止事项
- 不得重复正文已详细阐述的内容（这是最重要的规则）
- 问题不能过于专业（目标读者不会这样问）
- 回答不能模糊（不能只说「请咨询医生」而不给任何信息）
- 不能出现具体药物名称或剂量
- 回答末尾可以引导就医，但不能以「去看医生」作为唯一答案

请直接输出3个Q&A，格式为：
**Q：[问题]**
[回答内容]

每个回答不超过 {per_qa} 字，3个合计不超过 {qa_wt}。
"""


# ═══ 问答科普（7 章节：引入→问答1·入门→问答2·入门→问答3·进阶→问答4·实操→问答5·特殊→总结） ═══

def get_qa_intro(state: dict) -> str:
    """问答科普引言：极简开场，告诉读者这里有什么。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    skip = set(state.get("skip_sections") or [])
    total_qa = sum(1 for k in ["qa_1", "qa_2", "qa_3", "qa_4", "qa_5"] if k not in skip)
    wt = _section_word_target(state) or "40-70字"
    return f"""请为问答科普文章撰写引言部分。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
问答数量：{total_qa} 个

【写作任务】
极度精简，2-3句话完成两件事：
① 一句话引出话题（共情读者的疑惑）
② 一句话说明价值（"整理了最常被问到的{total_qa}个问题，直接给答案"）

✅ "关于{state.get('topic', '')}，很多人心里都有些说不清的疑惑。这里整理了{total_qa}个最常被问到的问题，直接给你明确的答案。"
❌ 不在引言里开始讲任何知识点，不用论文式写法

【输出禁区（零容忍）】
- 绝对不输出 [共识]、[推断]、[[待补充]] 等任何方括号标注
- 不超过3句话

字数：{wt}（严格执行）
风格：{audience['tone']}
请直接输出引言正文。
"""


def get_qa_single(state: dict, section_type: str = "qa_1") -> str:
    """问答科普单题，按问题链层级分配角度。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    qa_idx = int(section_type.replace("qa_", "")) if section_type and "qa_" in section_type else 1

    skip = set(state.get("skip_sections") or [])
    total = sum(1 for k in ["qa_1", "qa_2", "qa_3", "qa_4", "qa_5"] if k not in skip)

    level_map = {
        1: ("入门级", "大众最关心的基础认知问题——'这个东西是什么/严不严重/要不要紧'类型的疑问，聚焦于对疾病/健康问题的基本判断"),
        2: ("入门级", "另一个高频但不同角度的基础问题——如果Q1问的是'严不严重'，Q2就问'会不会传染/遗传/影响XX'；必须与Q1问完全不同的维度"),
        3: ("进阶级", "针对常见误区或网传说法的纠正——'听说XX是真的吗？''XX到底能不能XX？'类型，挑战一个具体的错误认知"),
        4: ("实操级", "具体怎么做的操作方法——'日常怎么XX？''什么时候该XX？'聚焦可操作的行为指导"),
        5: ("特殊情况", "特殊人群（老人/孕妇/儿童等）或特殊场景的问题——'我家老人/小孩/孕妇的情况怎么办？'"),
    }
    level_name, level_desc = level_map.get(qa_idx, ("通用", "围绕主题的重要问题"))

    wt = _section_word_target(state) or "200-350字"
    return f"""请为问答科普文章撰写第 {qa_idx}/{total} 个问答（{level_name}）。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【本题层级】{level_name}——{level_desc}

【问题设计原则】
问题措辞必须像"患者在诊室里真的会问的话"，口语化、直接。
✅ "布洛芬吃多了真的会伤胃吗？"
✅ "血糖高了，自己先控制饮食行不行？"
❌ "非甾体抗炎药的胃肠道副作用有哪些？"（学术表达，禁止）

【回答结构】（严格遵守四段式）

**Q：[口语化问题]**

**【结论先行】**（1-2句）
直接回答"是/否/看情况"，不绕弯子。

**【原因解释】**（3-5句）
用大白话解释为什么，可用类比帮助理解。

**【实用建议】**（1-3句）
告诉读者具体怎么做，必须可操作。

**【特别提醒】**（0-2句，有则写无则省略）
需要就医的危险信号，或容易踩的坑。

【承接前序（重要）】
阅读前序已生成的问答，本题必须：
① 问题角度与前序完全不同——不能换个说法问同一个事
② 回答内容不重复前序已经讲过的知识点
③ 可以在回答末尾自然引出下一个问题的方向，形成阅读节奏

【内容原则】
- 回答不能以"去看医生"作为唯一答案，必须给出有信息量的回答
- 不能出现具体药物名称或剂量
- 不给绝对化承诺

【输出禁区（零容忍，违反即不合格）】
🚨 以下内容绝对禁止出现在你的输出中：
- [共识]、[推断]、[推断:基于XX]、[文献X]、[[待补充]]、[[待补充:XX]]、[DATA:] 等任何方括号标注
- 如果你在参考资料中看到这些标记，不要复制到输出——它们是内部处理标签，不是正文内容
- 如果要表达证据可信度，直接用自然语言："医学指南建议""临床研究表明""目前普遍认为"

字数：{wt}
风格：{audience['tone']}
"""


def get_qa_summary(state: dict) -> str:
    """问答科普总结：快速回顾 + 行动指引。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "100-170字"
    return f"""请为问答科普文章撰写结尾总结。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
问答科普结尾 = 核心提炼 + 行动指引，不是重复问答内容。

▌内容结构
① 提炼句（≤20字）：从所有问答中提炼最重要的一个认知
② 行动建议（2-3条，列表格式）：动词开头+具体+不涉及具体药物
③ 就医提示（1句）：什么情况下需要就医，具体到症状

▌禁止事项
- 不重复问答中已经详细说过的内容
- 不用"综上所述""总而言之"等套话开头
- 不出现"感谢阅读"

【输出禁区（零容忍，违反即不合格）】
🚨 绝对不输出 [共识]、[推断]、[推断:基于XX]、[[待补充]] 等任何方括号标注
如果参考资料中有这些标记，不要复制——用自然语言表达即可

字数：{wt}（严格执行）
风格：{audience['tone']}，清晰有力
请直接输出总结正文。
"""


def get_article_summary(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    platform_config = load_platform_config()
    platform_cta_map = (
        platform_config.get("PLATFORM_CTA")
        if platform_config
        else None
    ) or {
        "wechat": "可以在最后引导读者分享给家人朋友，或关注公众号获取更多内容",
        "xiaohongshu": "可以用「收藏这篇，关键时刻用得上」结尾",
        "journal": "正式的学术风格收尾，引导读者保持健康习惯",
        "offline": "温暖的结尾，给读者信心和行动力",
        "douyin": "强行动号召，「今天就去做XXX」",
    }
    platform_cta = platform_cta_map.get(state.get("platform", "wechat"), "简洁有力的总结，鼓励行动")
    tpl = load_task("article_summary")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform_cta=platform_cta,
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    sum_wt = _section_word_target(state) or '150-250字'

    return f"""请为以下医学科普文章撰写健康小结（结尾部分）。

🚨🚨🚨 最重要的规则——字数限制 🚨🚨🚨
小结全文必须控制在 {sum_wt} 之间。
升华 1-2 句 + 行动要点 2-3 条（每条一句话）+ 就医提示 1 句 + 情感收束 1 句，合计不超过 {sum_wt}。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【小结必须是增量信息，严禁复述正文】
小结的价值不是"再说一遍"，而是帮读者记住最关键的 2-3 件事。
- 正文中已详细解释的知识点、类比、数据，绝不能在小结中重新出现
- 正文中出现过的具体建议，小结中不得原样或换句话重复
- 如果正文已经讲了"怎么做"，小结只需用一句话点题（如"按上文方法调整饮食"），主体必须是正文未覆盖的新角度

【小结写作规范】

▌结构要求（按顺序，总字数 {sum_wt}）

① 一句话升华（1-2句）
   - 从正文的多个知识点中提炼出一个更高层次的认知
   - 用正文中没有出现过的新表述，不是正文结论的复制
   - 示例：正文讲了具体食物和运动 → 升华为"管理血糖本质上是管理生活方式"

② 行动要点（2-3 条，极简）
   - 每条一句话，动词开头
   - 必须具体：❌ 「保持良好生活习惯」 ✅ 「每天走路30分钟，分3次完成也可以」
   - 如果正文已有行动建议，这里只挑最核心的 2-3 条并用更精炼的新语言表达
   - 注意：只涉及生活方式，不涉及用药

③ 就医提示（1-2句）
   - 简洁说明什么情况应该看医生
   - 语气是关怀提醒，不是吓唬

④ 情感收束（1句）
   - 给读者信心和温暖
   - {platform_cta}

▌语言要求
风格：{audience['tone']}
句长：{audience['sentence']}

▌禁止事项
- 不用「总之」「综上所述」「让我们回顾一下」等套话开头
- 不重复引言或正文的原句、原段
- 不出现「感谢阅读」
- 不展开解释正文已讲过的概念（如正文解释了 GI，小结不要再解释一遍）
- 健康建议不涉及具体药物

请直接输出小结内容，可以自行添加小标题。全文不超过 {sum_wt}。
"""


# ═══ 辟谣文（7 章节：谣言还原→真相判定→拆解1→拆解2→拆解3→正确做法→防骗指南） ═══

def get_debunk_rumor_present(state: dict) -> str:
    """谣言还原：完整呈现谣言原文或典型传播场景，同时生成辟谣型标题。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "100-200字"
    return f"""请为辟谣文撰写【标题】+【谣言还原】部分。

【文章信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【一、标题生成】
标题类型三选一（根据话题自动选择最合适的）：
  A. 质疑型：「XX是真的吗？」
  B. 警醒型：「别再信了！XX根本不靠谱」
  C. 揭秘型：「关于XX的真相」
标题中必须包含谣言的核心关键词，让读者一眼就知道本文辟什么谣。
禁止使用「震惊」「速看」「转发」等标题党词汇。

【二、谣言还原】
完整、客观地呈现这条谣言，让读者一读就说"对对对，我见过这个！"
必须涵盖三个要素：
① 谣言的原始说法（尽量还原其在传播中的措辞，如果是口语化的就用口语）
② 传播场景（家族群/短视频/养生号/朋友圈转发/邻居口口相传等）
③ 为什么它"听起来有道理"（抓住读者的心理共鸣点——常识偏差、恐惧心理、经验主义等）

【语气原则】
- 零嘲讽：不嘲笑相信谣言的人，很多谣言确实"看起来合理"
- 像朋友在客厅里帮你还原事情经过，不是法官在审问
- 让读者感到被理解：「你见过这种说法吗？我也见过。」

【谣言重复控制（重要）】
本章节是全文唯一完整呈现谣言原文的地方。后续章节只能简短指代，不再完整重复。

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[推断:基于XX]、[文献X]、[[待补充]]、[[待补充:XX]] 等任何内部标注
- 不输出任何中括号或双中括号标记

字数：{wt}
风格：{audience['tone']}
输出格式：先输出标题行（## 标题），空一行后输出谣言还原正文。
"""


def get_debunk_verdict(state: dict) -> str:
    """真相判定：一句话结论前置，让急性子读者先拿到答案。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "50-100字"
    return f"""请为辟谣文撰写【真相判定】部分。

【文章信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【承接前序】
前面的"谣言还原"已经完整呈现了谣言。本章节的任务是立刻给出结论——让没耐心的读者在最短时间内拿到核心答案。

【输出格式】（严格遵守）
**真相：** [从以下四种判定中选择最准确的一种]
- 纯属谣言
- 有一定道理但严重夸大
- 张冠李戴（把A的结论套在B上）
- 过时信息（曾经正确但已被新证据推翻）

**一句话结论：** [用1句话简洁有力地给出正确认知，不超过40字]

【要求】
- 判定必须准确、有据，不能为了戏剧效果而夸大判定结果
- 一句话结论必须信息密度高：读者只看这一句就能知道真相是什么
- 不添加额外的解释或展开——详细拆解留给后续章节
- 不重复谣言原文，用简短指代即可

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注
- 结论后面不加任何中括号标记，直接用句号结尾

字数：{wt}
风格：{audience['tone']}（简洁、干脆、权威）
"""


def get_debunk_point(state: dict, section_type: str = "debunk_1") -> str:
    """逐条拆解：每个漏洞独立成段，拆解谣言的逻辑漏洞。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    point_num = int(section_type.replace("debunk_", "")) if "debunk_" in section_type else 1

    skip = set(state.get("skip_sections") or [])
    total_points = sum(1 for k in ["debunk_1", "debunk_2", "debunk_3"] if k not in skip)

    angle_hints = {
        1: "优先选择最直观的事实性错误（如数据/含量/剂量与实际严重不符）",
        2: "优先选择逻辑谬误类漏洞（如偷换概念、因果倒置、以偏概全）——必须与漏洞1的角度完全不同",
        3: "优先选择认知偏差或传播机制类漏洞（如恐惧心理利用、断章取义、过时引用）——必须与漏洞1和漏洞2的角度完全不同",
    }
    angle_hint = angle_hints.get(point_num, "")

    wt = _section_word_target(state) or "130-260字"
    return f"""请撰写辟谣文的【逐条拆解·漏洞{point_num}】（共{total_points}个漏洞）。

【文章信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【承接前序】
"谣言还原"已呈现谣言全貌，"真相判定"已给出一句话结论。
本章节的任务是深入拆解第 {point_num} 个逻辑漏洞——为读者解释"这个说法到底错在哪里"。

🚨 反重复强制检查：阅读前序已生成的拆解内容（如有），你选择的漏洞类型、论点、类比、证据必须与已有拆解完全不同。如果前序已经用了"偷换概念"，本条必须选择其他类型。

【本条拆解角度指引】
{angle_hint}

【严格输出格式】
**漏洞{point_num}：[漏洞类型名称]——[一句话概括本质]**

**谣言说法：** [简短指代谣言中与本漏洞相关的具体说法，不完整重复谣言原文]

**事实是：** [2-4句话，用通俗语言解释真实情况，优先使用类比帮助理解]

**证据来源：** [用自然语言标明证据来源——如"世界卫生组织的饮用水标准指出……"；无可靠来源时直接省略此行，不使用占位符]

【内容原则】
① 每个漏洞必须拆解谣言的一个独立逻辑问题——严禁与其他漏洞重复同一论点或同一类比
② "事实是"部分用读者听得懂的话说，类比优先，禁止堆砌学术术语
③ 证据用自然语言表述来源，不使用 [共识]、[DATA:] 等标记
④ 不完整重复谣言原文——用"前述说法""该谣言声称"等简短指代
⑤ 保持客观理性，不添加情绪化评价词

【漏洞类型清单（必须选择与其他漏洞不同的类型）】
- 事实错误：关键数据/含量/剂量与实际严重不符
- 偷换概念：A 和 B 不是一回事（如"含有"≠"有害"）
- 剂量忽略：离开剂量谈毒性，忽略了安全阈值
- 以偏概全：个别案例/条件不能代表普遍规律
- 因果倒置：先后关系不等于因果关系
- 断章取义：只取了研究/报道的部分结论
- 过时引用：引用的数据/结论已经被新研究推翻
- 恐惧利用：利用"致癌""有毒"等恐惧词汇制造焦虑

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]]、[DATA:] 等任何内部标注
- 不使用中括号或双中括号标记

字数：{wt}
风格：{audience['tone']}
"""


def get_debunk_correct_practice(state: dict) -> str:
    """正确做法：告诉读者应该怎么做。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "200-300字"
    return f"""请为辟谣文撰写【正确做法】部分。

🚨🚨🚨 最重要的规则——字数限制 🚨🚨🚨
本章节中文正文必须控制在 {wt} 之间。超过即删减，宁可每条建议更简短也不可超字。

【文章信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【承接前序】
前面已经完成了谣言还原、真相判定和逐条拆解。读者现在知道"谣言错在哪里"了。
本章节的任务是回答「那我到底该怎么做？」——精炼、实用。

【输出内容（两个部分，精简）】

① **正确的做法：**
   [3条具体、可操作的建议，用编号列表]
   - 每条建议一句话搞定，不展开论述
   - 不涉及具体药物名称、剂量、疗程

② **什么情况下需要就医：**
   [1-2个明确的就医信号]

【语气原则】
- 从"纠错"转向"赋能"——让读者感到掌握了正确知识后更有信心
- 不说教，给建议

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注
- 不输出"权威参考"小标题——如需提及来源，自然融入建议语句中

字数：{wt}（严格遵守，超过即为失败）
风格：{audience['tone']}
"""


def get_debunk_anti_fraud(state: dict) -> str:
    """防骗指南：教读者辨别类似谣言的通用方法。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "100-150字"
    return f"""请为辟谣文撰写【防骗指南】部分。

【文章信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【承接前序】
全文已完成谣言拆解和正确做法指引。本章节是收尾——不再针对本文具体谣言，
而是教读者一套通用的"谣言识别方法"，提升信息素养，防止下次再被骗。

【输出格式】
**遇到类似说法，记住这几点：**
1. [第1条辨别方法]
2. [第2条辨别方法]
3. [第3条辨别方法]

【内容原则】
① 3条为佳，最多4条——精炼比全面更重要
② 每条方法必须通用，适用于辨别各种健康类谣言，不局限于本文主题
③ 引导读者养成"看到就想一想"的习惯，而不是"看到就害怕"
④ 语气温和鼓励，不居高临下

【参考方向（选择最适合读者的）】
- 看来源：正规医疗机构/学术期刊 vs 营销号/无署名文章
- 看措辞：绝对化用词（一定、必须、百分百）往往是谣言信号
- 看逻辑：个案不代表普遍规律，相关不等于因果
- 看时间：信息是否过时，医学认知在不断更新
- 看动机：是否在推销产品或制造恐慌以获取流量

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注
- 不添加任何中括号或双中括号标记

字数：{wt}
风格：{audience['tone']}
"""


# ═══ 科普故事（7 章节：引子→发展→转折·就医→科普核心→结局→行动清单→结尾金句） ═══
# 写作总纲：
# - 主角设定要具体（年龄、职业、生活习惯），避免"某患者"
# - 医学知识通过故事中的对话、医生解释自然带出，不要突然切换成"科普模式"
# - 结局不必都是圆满的，适度的遗憾更有警示力
# - 对话控制在2-3轮，避免写成剧本
# - 推荐字数 1500-2500字


def get_story_hook(state: dict) -> str:
    """引子：用具体场景或人物开场，快速建立代入感。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    word_hint = _section_word_target(state)
    tpl = load_task("story_hook")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            specialty=state.get("specialty", ""),
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            word_hint=word_hint,
        )
    return f"""请为医学科普故事撰写【标题 + 引子】。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
目标读者：{audience['desc']}
专科：{state.get('specialty', '')}

【标题写作规范】
先输出一行标题，标题必须是故事型，禁止使用学术论文式标题。
- 悬念型："那个总说'没事'的年轻人，确诊了……"
- 反转型："每天晨练的阿姨，血糖'达标'了，却进了急诊"
- 共情型："妈，我好像摸到一点门道了"
- ❌ 禁止："XX疾病的新趋势：从A到B""XX管理的最新进展"等学术标题

标题后空一行，接引子正文。

【引子写作规范】

引子需要在{word_hint or '100-200字'}内完成以下任务：
用一个具体场景或人物开场，快速建立代入感。

▌必备四要素
① 谁 — 具体的人（年龄、职业、生活习惯），不能是"某患者"
② 在哪 — 生活化的场景（办公室、厨房、地铁上……）
③ 发生了什么 — 一个日常事件
④ 一个"不对劲"的信号 — 让读者开始担心

▌示例
"32岁的小林（化名）最近总觉得胸口闷，但他想'年轻人哪有什么心脏病'，
直到那天开会时，他突然眼前一黑……"

▌叙事原则
- 用第三人称叙述，贴近人物感受
- 场景要具体——「阳台上晒太阳」比「某个下午」好
- 人物用化名，注明「（化名）」
- 开头从场景或动作开始，不要从心理描写开始
- 用动作和感官细节呈现，不用旁白式总结
  ✅ "她站起来，扶住桌角，等了好几秒眼前才恢复清明。"
  ❌ "她感到身体出现了异常，意识到可能有问题。"
- 结尾留一个悬念钩子，让读者想知道「后来怎样了」

▌叙事语言禁区
- 不输出任何学术标注（如[共识]、[推断]、[文献]等）——你在讲故事，不是写论文
- 不使用"研究显示""医学上""据统计"等学术表达
- 不出现任何医学术语的学术定义

▌语言风格
风格：{audience['tone']}
句长：{audience['sentence']}

请先输出标题，空一行，再输出引子正文。
"""


def get_story_development(state: dict) -> str:
    """发展：主角遭遇问题，尝试自行解决但失败或加重。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    word_hint = _section_word_target(state)
    tpl = load_task("story_development")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            word_hint=word_hint,
        )
    return f"""请为医学科普故事撰写【发展】部分。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
目标读者：{audience['desc']}

【发展部分写作规范】

在{word_hint or '300-500字'}内完成以下叙事推进：

▌核心任务：主角遭遇问题 → 尝试自行解决 → 失败或加重
写清楚三件事：
① 主角最初的想法是什么？（常见误区/错误认知）
② 他/她做了什么错误的应对？（拖延就医 / 民间偏方 / 自行用药）
③ 出现了什么危险信号？（症状加重 / 新症状出现）

▌情感节奏
侥幸/不以为然 → 困惑/不安 → 恐惧/焦虑

▌叙事技巧
- 通过主角的行为和想法展现常见误区，而非旁白直接纠正
  ✅ "他在网上搜了一圈，觉得可能是最近加班累的，买了两盒维生素就不管了。"
  ❌ "很多人都有一个误区，认为年轻人不会得心脏病，这是不对的。"
- 对话控制在 1-2 轮，避免写成剧本
- 人物的错误应对要真实可信，让读者代入后反思自身

▌禁止事项
· 不在这一节出现医生角色（医生在"转折·就医"才出场）
· 不直接纠正误区（让读者自己感到"这样做不对"）
· 不出现知识性讲解

▌承接前序（重要）
- 你必须使用引子中已出场的主角（同一姓名、年龄、职业），不能换人
- 本节开头自然承接引子最后的情节状态——主角刚发现了什么"不对劲"
- 情感从引子的"初现端倪"过渡到"侥幸/忽视 → 逐步恶化"

▌叙事语言禁区
- 不输出任何学术标注（如[共识]、[推断]、[文献]等）——你在讲故事，不是写论文
- 不使用"研究显示""医学上""据统计"等学术表达
- 用动作和感官细节传达情绪，不用旁白式心理总结
  ✅ "她的手开始发抖，筷子夹不稳菜。"
  ❌ "她感到十分恐惧和不安。"

▌语言风格
风格：{audience['tone']}
句长：{audience['sentence']}

请直接输出发展部分正文，不需要标注章节标题。
"""


def get_story_turning_point(state: dict) -> str:
    """转折·就医：关键转折点，进入医疗场景。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    word_hint = _section_word_target(state)
    tpl = load_task("story_turning_point")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            word_hint=word_hint,
        )
    return f"""请为医学科普故事撰写【转折·就医】部分。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【转折·就医写作规范】

在{word_hint or '200-400字'}内完成故事的关键转折：

▌核心三要素
① 就医契机 — 是什么促使主角终于去了医院？
   可以是：症状突然加重 / 家人强烈要求 / 偶然事件（体检、朋友患病等）
② 医生的关键一句话 — 短短一句，让主角意识到问题的严重性
   ✅ "医生翻了翻记录本，皱了下眉：'你这个情况，不太对。'"
   ✅ "医生的笔停了一下：'这个，不能再拖了。'"
   注意：这句话只是制造紧张感，不能包含任何医学解释或新概念
③ 初步诊断 — 只说结论（如"你这是XX"），不解释为什么

▌叙事要求
- 就医场景要有画面感——用感官细节呈现（候诊室的塑料椅、消毒水味、叫号声）
- 通过动作和细节传达情绪，不用旁白式心理总结
  ✅ "她攥紧了手里的挂号单，指尖已经被汗浸透。"（通过动作表现紧张）
  ❌ "她感到十分紧张和后悔。"（旁白式总结）
  ❌ "她既后悔没早点来，又庆幸终于迈出了这一步。"（作者在替读者做总结）
- 对话控制在 1-2 轮，医生说话要像真人——简短、口语、有个性

▌情感节奏
叙事在这里有一个明确的"拐点"，从日常生活切换到医疗场景。
用场景和细节让读者自己感受到：「幸好来了」或「早该来的」

▌知识零容忍（最重要的禁令）
本节是纯粹的情节转折，绝对不能包含任何医学知识讲解：
· ❌ 医生不能解释任何医学概念（如"目标范围内时间""TIR"等）
· ❌ 医生不能科普发病机制或治疗方案
· ❌ 不能出现"简单来说就是……""通俗地说……"等科普句式
· ❌ 不能出现任何英文缩写或专业术语的解释
· 所有知识讲解必须留给下一节"科普核心"
· 本节医生最多只能说出诊断名称 + 一句"我给你好好说说"的预告
· 不过度戏剧化（不要出现急救/抢救等夸张场面，除非题材确实涉及急症）

▌叙事语言禁区
- 不输出任何学术标注（如[共识]、[推断]、[文献]等）
- 不使用"研究显示""医学上""据统计"等学术表达

▌场景边界（极其重要）
本节结束时，主角必须仍在诊室/医疗场景中，不能离开。
- 以诊断揭示、医生的一句关键判断、或主角的震惊/疑问作为本节收尾
- 留下一个"主角想继续了解"的悬念——让读者期待医生接下来的详细解释
- ❌ 绝对禁止写"走出诊室""离开医院""回到家"等离场动作
- ❌ 绝对禁止在本节末尾做总结性收束（如"这次就医让她意识到……"）
- ✅ 正确的结尾："她愣了半天，才问出一句：'那……我这个还能治吗？'"
- ✅ 正确的结尾："医生看了看检查报告，表情变得严肃：'我给你详细说说这个病。'"

▌承接前序（重要）
- 主角是发展部分中同一个人（姓名、身份信息完全一致）
- 前序中主角已经出现了哪些症状/错误应对？本节的就医契机必须由这些已铺垫的恶化因素触发，不能凭空冒出新理由
- 情感从"发展"末尾的焦虑/害怕，自然过渡到"终于决定去医院"的心理转变
- 时间线要清晰——距离发展部分过了多久？用简短的时间标记衔接（如"那个周末""又拖了一周"）

▌语言风格
风格：{audience['tone']}，节奏在转折处略微加快
句长：{audience['sentence']}

请直接输出转折·就医部分正文，不需要标注章节标题。
"""


def get_story_science_core(state: dict) -> str:
    """科普核心：以医生口吻或旁白形式，自然嵌入核心知识。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    word_hint = _section_word_target(state)
    tpl = load_task("story_science_core")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            word_hint=word_hint,
        )
    return f"""请为医学科普故事撰写【科普核心】部分。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【科普核心写作规范】

在{word_hint or '400-600字'}内，通过医患对话自然嵌入核心医学知识。

▌定位：本节是全文唯一的知识输出窗口
前面的章节（引子、发展、转折·就医）不包含任何医学知识讲解。
本节承担着所有科普内容的传递。因此不要假设读者已经从前序章节了解了任何医学概念——这里是第一次、也是唯一一次系统讲解。

▌必须覆盖三个层面（但全部通过对话/场景呈现）
① 这个病/问题是什么？ — 医生用一句口语化的话向主角解释
② 为什么会发生？ — 医生用比喻向主角讲清机制
   ✅ 医生指着纸上画的图："你可以把血管想象成水管……"
   ❌ 旁白："动脉粥样硬化的发病机制涉及内皮细胞损伤……"
③ 常见误区纠正 — 主角说出自己的错误理解，医生温和纠正
   ✅ "'我以前觉得数字越低越好。' '这是很多人的误区……'"
   ❌ "大众最常见的误区是认为数字越低越好，正确的理解应该是……"（论文式）

▌知识嵌入方式（严格按优先级）
1. 最优：医生与主角的自然对话
   主角问 → 医生用比喻/日常语言回答 → 主角追问 → 医生深入一层
2. 次优：以叙事旁白过渡（保持人物视角）
   "后来她才知道，她一直以为的'小问题'，其实是……"
3. ❌ 绝对禁止：跳出故事的学术旁白
   "研究显示……""这是当前XX领域的一个主要研究热点""医学上认为……"

▌对话控制
- 医患对话 2-3 轮，像真实诊室对话
- 医生的解释要分层递进，每次只说一个点，等主角消化
- 主角的提问要像普通人——"那我以前那样做是不是错了？""那怎么办才好？"
  ❌ "请问医生这个病的发病机制是什么？"（没有普通人这样问）

▌禁止事项（零容忍）
· 不突然从叙事切换成学术/科普口吻——全程保持在"诊室对话"的场景中
· 不输出任何学术标注（如[共识]、[推断]、[文献]等）
· 不使用"研究显示""据统计""医学上""近年来"等学术表达
· 不在对话之外插入独立的知识总结段落
· 不堆砌专业术语（必须用术语时，由医生用口语解释）
· 不涉及具体药物名称或剂量
· 最后一段不能是学术旁白式总结——必须以对话或主角的感受/动作收尾

▌场景设定（极其重要）
本节场景直接延续"转折·就医"——主角此刻仍在诊室中，面对同一位医生。
- 不需要重新描写进入医院、挂号等场景——主角从未离开过诊室
- 开头直接从医患对话或医生进一步解释切入
- ✅ "医生调出了一张示意图，指着上面说……"
- ✅ "'这个问题说起来，你先别紧张。'医生靠回椅背，耐心地解释……"
- ❌ "第二天，她又去了医院"（主角从未离开）
- ❌ "回到诊室后，医生开始解释"（主角一直在诊室里）

▌承接前序（重要）
- 紧接"转折·就医"的最后一刻——主角刚拿到诊断，正等医生详细解释
- 科普知识应围绕前序诊断结果展开，而非跳到无关的话题
- 如前序中医生已说了某句关键的话，可以在此处展开解释其背后的医学原理
- 主角的疑问应基于前序情节中的真实困惑（如"为什么我年纪轻轻就会……""我之前以为是……"）
- 保持同一个医生角色（如前序已出场），姓名、性别、性格和说话方式完全一致

▌语言风格
风格：{audience['tone']}，在知识点处适当放慢节奏
句长：{audience['sentence']}

请直接输出科普核心部分正文，不需要标注章节标题。
"""


def get_story_resolution(state: dict) -> str:
    """结局：主角的结局，给读者希望或警示。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    word_hint = _section_word_target(state)
    tpl = load_task("story_resolution")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            word_hint=word_hint,
        )
    return f"""请为医学科普故事撰写【结局】部分。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【结局写作规范】

在{word_hint or '200-300字'}内完成故事收束：

▌核心任务
展示主角的改变 — 治愈/好转/遗憾，给读者希望或警示。
回答两个问题：
① 主角最终怎么样了？
② 如果早知道，结果会不同吗？

▌状态改变
✅ "三个月后的复查，小林的指标终于回到了正常范围。他给同事群发了一条消息：'别学我，不舒服真得早看。'"
❌ "从此小林过上了健康快乐的生活，再也不担心了。"（童话式，不真实）

▌留白收尾（1-2句）
好的故事结尾留有余韵，不把话说满。
✅ "那天离开诊室时，他给妈妈打了个电话：'妈，你上次说的那个体检，帮我也约一个。'"
❌ "通过这次经历，小林深刻认识到了定期体检的重要性……"（总结式，没有余韵）

▌结局类型选择（根据主题自然选择）
- 好转型：主角配合治疗，状态改善（适合可防可治的疾病）
- 警示型：主角因拖延留下了一些遗憾（适合需要强调早期筛查的话题）
- 注意：适度的遗憾比完美结局更有警示力

▌禁止事项
· 不在结局里插入新的知识点
· 不过度煽情（热泪盈眶/感恩戴德）
· 不做完美大团圆结局
· 不以悲剧或绝望结尾

▌承接前序（重要）
- 主角经历了引子→发展→就医→科普核心的完整旅程，结局是这条故事线的自然收束
- 科普核心结束时主角仍在诊室/医疗场景中——结局需要先完成离开场景的过渡
  ✅ "走出医院大门时，阳光正好。她深吸一口气……"
  ✅ "拿着医生开的方案，她在医院门口站了一会儿……"
- 结局中的"改变"必须是由前序情节驱动的——主角学到了什么、改变了什么行为
- 涉及的疾病/诊断/治疗方案必须与前序科普核心部分一致
- 时间跳跃需要有明确标记（"三个月后""复查那天"），不能悄悄跳到未来
- 如果前序出现了家人/朋友角色，可以在结局中呼应他们，增强情感闭环

▌叙事语言禁区
- 不输出任何学术标注（如[共识]、[推断]、[文献]等）
- 不使用"研究显示""医学上"等学术表达
- 不写旁白式总结（如"通过这次经历，她深刻认识到……"）
- 用细节和动作收尾，留有余韵

▌语言风格
风格：{audience['tone']}，温暖，有余韵
句长：{audience['sentence']}

请直接输出结局正文，不需要标注章节标题。
"""


def get_story_action_list(state: dict) -> str:
    """行动清单：给读者的实用建议，3-5条，可操作。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    word_hint = _section_word_target(state)
    tpl = load_task("story_action_list")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            word_hint=word_hint,
        )
    return f"""请为医学科普故事撰写【行动清单】部分。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
目标读者：{audience['desc']}

【行动清单写作规范】

在{word_hint or '100-200字'}内，给读者提供 3-5 条实用建议。

▌格式要求
用编号列表呈现，每条建议需要：
- 具体可操作（读者看完就知道怎么做）
- 不涉及具体药物或剂量
- 与故事中的知识点呼应

▌示例
1. 胸闷持续超过 3 天，别扛——挂个心内科
2. 每年至少做一次心电图，35 岁以上尤其重要
3. 熬夜 + 高压 + 久坐，三样占两样就该警惕
4. 家族里有心脏病史的，筛查频率翻倍
5. 突发胸痛、大汗、气短——立刻拨打 120

▌过渡方式（可选）
可以用一句从故事过渡到清单的引导句：
"如果你也有类似的情况，这几件事值得记住——"
或直接以清单开头。

▌禁止事项
· 不写空泛的建议（如"保持健康生活方式"）
· 不推荐具体品牌或产品
· 不写超过 5 条（信息过多读者记不住）

▌承接前序（重要）
- 行动清单的每条建议必须与前序故事中涉及的疾病/知识点直接相关
- 建议应回应故事中主角犯过的错误——如果主角拖延就医，清单里就应有"什么情况下应及时就医"
- 使用过渡句从故事自然切入清单，而非突然跳转

▌叙事语言禁区
- 不输出任何学术标注（如[共识]、[推断]、[文献]等）
- 不使用"研究显示""据最新研究"等学术表达
- 用口语化、有温度的语言写建议，像朋友叮嘱，不像医嘱
  ✅ "胸闷持续超过3天，别扛——挂个心内科"
  ❌ "如出现持续性胸闷症状，建议及时就诊[共识]"

▌语言风格
风格：{audience['tone']}，简洁直接

请直接输出行动清单内容。
"""


def get_story_closing_quote(state: dict) -> str:
    """结尾金句：点题升华，适合被截图转发。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    word_hint = _section_word_target(state)
    tpl = load_task("story_closing_quote")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            word_hint=word_hint,
        )
    return f"""请为医学科普故事撰写【结尾金句】。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
目标读者：{audience['desc']}

【结尾金句写作规范】

写 1-2 句点题升华的金句，适合被截图转发。

▌要求
- 与整篇故事的主题呼应
- 语言凝练、有力量感
- 读完后让人有被触动的感觉
- 适合单独拎出来作为转发文案

▌示例
"身体发出的每一个信号，都值得被认真对待。"
"你以为的'没事'，可能是身体最后一次提醒。"
"健康不是等出了问题再去修补，而是在还来得及的时候，多听一句。"

▌禁止事项
· 不写鸡汤式金句（"生命只有一次，请珍惜"）
· 不写说教式总结（"希望大家都能重视健康"）
· 不超过 2 句

▌承接前序（重要）
- 金句必须与整篇故事的核心主题呼应——主角经历了什么、读者应该记住什么
- 如果故事中有某个关键的比喻或概念，金句可以升华它
- 不要写与故事无关的泛泛而谈的健康箴言

▌叙事语言禁区
- 不输出任何学术标注
- 不写学术式总结

▌语言风格
风格：{audience['tone']}，凝练有力

请直接输出 1-2 句金句，不需要引号或其他格式标记。
"""


# ═══ 研究速读（7 章节：一句话摘要→研究信息卡→为什么值得关注→研究怎么做的→核心发现→对普通人意味着什么→注意事项·研究局限） ═══

def get_research_one_liner(state: dict) -> str:
    """一句话摘要：30字以内，大白话概括最重要的发现。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    return f"""请为研究速读文章撰写"一句话摘要"。

【文章信息】
研究主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【写作任务】
用一句大白话概括这项研究最重要的发现，让读者一秒钟抓住核心。

✅ "每天多走2000步，心血管死亡风险可能降低10%"
✅ "睡眠不足6小时的人，感冒风险翻倍"
❌ "本研究揭示了步行运动与心血管预后之间的剂量-反应关系"（学术腔）

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注
- 不超过30字
- 不用学术术语

字数：≤30字（严格执行）
风格：{audience['tone']}
请直接输出一句话，不需要标题。
"""


def get_research_study_card(state: dict) -> str:
    """研究信息卡：结构化呈现研究元数据。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    return f"""请为研究速读文章撰写"研究信息卡"。

【文章信息】
研究主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【写作任务】
以简洁的结构化格式呈现研究的基本元数据，帮助读者快速了解研究的"分量"。

▌输出格式（严格遵循）：
- **发表期刊**：[如有RAG来源则填写，否则写"待确认"]
- **发表时间**：[如有RAG来源则填写，否则写"待确认"]
- **研究类型**：[RCT / 队列研究 / Meta分析 / 横断面研究 / 病例报告 / 其他]
- **样本量**：[如有RAG来源则填写，否则写"待确认"]
- **研究人群**：[用通俗语言描述]

▌要求
- 基于RAG提供的文献信息如实填写，没有的信息标"待确认"
- 研究类型和研究人群用通俗语言，不用缩写
- 如果面向大众读者，在研究类型后可加简短注释（如"Meta分析（汇总多项研究的大型分析）"）

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注
- 不编造期刊名、样本量等具体数据

请直接输出信息卡内容。
"""


def get_research_why_matters(state: dict) -> str:
    """为什么值得关注：建立相关性，让读者想继续读。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "100-200字"
    return f"""请为研究速读文章撰写"为什么值得关注"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
回答读者的第一个问题："这个研究跟我有什么关系？为什么我要花时间读？"

▌内容结构（严格按顺序）
① 现状痛点（1-2句）：这个领域目前存在什么问题、争议或认知空白？
② 研究切入点（1句）：这项研究聚焦的具体问题。要具体，不说"研究了某某领域"，要说清楚研究了什么人、在什么条件下、看什么结果。
③ 与读者的关联（1句）：为什么这个发现可能影响到读者或其身边的人。

✅ "糖尿病影响着全球超过5亿人，但关于间歇性断食对血糖的长期影响，学界至今众说纷纭。这项研究首次在大规模人群中系统比较了几种常见断食模式的效果。"
❌ "近年来，随着医学科学的不断进步，越来越多的研究开始关注……"（套话，无信息量）

▌禁止事项
- 不在这里透露结论（结论留给"核心发现"）
- 不编造具体数据（无RAG来源时用定性描述）

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注

字数：{wt}
风格：{audience['tone']}
请直接输出正文。
"""


def get_research_methods(state: dict) -> str:
    """研究怎么做的：用通俗语言描述研究设计。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "150-250字"
    return f"""请为研究速读文章撰写"研究怎么做的"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
用通俗语言描述研究设计，让非专业读者也能理解研究是怎么做的。

▌内容结构（回答四个问题）
① 研究对象是谁？（1句）——用通俗语言描述，如"来自XX国家的XXX名成年人"
② 怎么分组/怎么观察的？（2-3句）——用类比帮助理解研究方法
   ✅ "研究者把参与者随机分成两组，就像抛硬币决定谁进哪一组"
   ✅ "研究者追踪观察了这些人的健康状况，就像长期跟踪记录"
③ 主要看什么指标？（1句）——说清楚衡量标准
④ 跟踪了多久？（1句）——研究持续时间

▌面向不同读者的调整
- 大众：完全避免统计术语，多用类比
- 医学生/专业人士：可保留关键方法学术语（如"随机对照""双盲""意向性治疗分析"），但仍需简洁

▌禁止事项
- 不编造具体数字（无RAG来源时用"一定数量的""多个国家的"等通用表述）
- 不在方法部分开始讨论结果

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注

字数：{wt}
风格：{audience['tone']}
请直接输出正文。
"""


def get_research_findings(state: dict) -> str:
    """核心发现：大白话呈现关键结果，搭配原始数据。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "200-300字"
    return f"""请为研究速读文章撰写"核心发现"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
用大白话呈现2-3个关键结果，每个结果先说通俗解读再给原始数据。

▌内容结构（每个发现遵循）
**发现N：[一句话通俗概括]**
通俗解读：用类比或生活化语言解释这个发现意味着什么
原始数据：如有RAG来源，引用关键数字（如"HR=0.90, 95%CI 0.85-0.96"）

▌统计概念翻译指南
- NNT=20 → "每治疗20个人，额外多帮到1个人"
- HR=0.90 → "风险降低了约10%"
- p<0.001 → "这个差异在统计上非常可靠"
- 95%CI → "我们有95%的把握认为真实值在这个范围内"
- 绝对风险降低 vs 相对风险降低：优先用绝对数字，避免误导

▌证据强度标注
- 如果是RCT/Meta分析：可以用"研究发现""结果表明"
- 如果是观察性研究：必须用"研究观察到""数据显示有关联"——不能说"导致""证明"
- 如果是初步/小样本：用"初步数据提示""小规模研究显示"

▌禁止事项
- 绝对不能把"相关"说成"导致"（观察性研究无法确定因果）
- 不夸大效应量（"革命性发现""彻底改变"）
- 不编造具体数字

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注

字数：{wt}
风格：{audience['tone']}
请直接输出正文。
"""


def get_research_implication(state: dict) -> str:
    """对普通人意味着什么：将研究结论转化为读者的实际意义。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "150-200字"
    audience_guide = {
        "public": "这个发现是否改变了日常生活建议？读者现在需要做什么不同的事？避免让读者恐慌。",
        "patient": "这个发现是否影响治疗选择或日常管理？是否值得和医生讨论？",
        "student": "这个发现如何更新了对疾病机制的理解？与教材内容有何不同？",
        "professional": "这个发现是否影响临床实践？现有指南是否需要审视？",
    }.get(state.get("target_audience", "public"), "说明对读者日常生活的实际影响。")
    return f"""请为研究速读文章撰写"对普通人意味着什么"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
受众解读重点：{audience_guide}

【写作任务】
把研究结论翻译成读者能用的信息——这一节是研究速读的价值核心。

▌内容结构
① 直接说结论对读者的影响（1-2句，不绕弯子）
② 可操作的建议（1-2条，如果研究支持）——如果尚早不适合行动，明确说明
③ 适用边界（1句）——这个结论适用于谁，不适用于谁

✅ "如果你有高血压，这项研究提示早晨服药可能比晚上效果更好——但在改变用药习惯前，请先咨询主治医生。"
❌ "这项研究具有重要的理论价值和现实意义。"（空话）

▌严格禁止
- "革命性发现""颠覆传统""重磅突破"等夸大表述
- 具体剂量的用药建议
- 把初步研究说成定论（用"初步显示""研究提示"）
- 让读者恐慌或感觉必须立刻行动

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注

字数：{wt}
风格：{audience['tone']}
请直接输出正文。
"""


def get_research_limitation(state: dict) -> str:
    """注意事项·研究局限：诚实指出研究不足，防止过度解读。"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    wt = _section_word_target(state) or "100-200字"
    return f"""请为研究速读文章撰写"注意事项·研究局限"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
帮助读者正确理解研究的边界，防止过度解读。这一节体现科学传播的诚信。

▌内容结构
① 研究局限性（2-3句）：用通俗语言说明主要局限
   常见局限类型（选择适用的）：
   · 样本量小 → "只观察了XXX人，结论还需要更大规模研究验证"
   · 观察性研究 → "只能说明'有关联'，不能证明'一个导致了另一个'"
   · 人群不够多样 → "研究对象主要为XX人群，是否适用于其他群体仍需研究"
   · 随访时间短 → "随访仅持续了X个月，长期效果尚不明确"
   · 混杂因素 → "可能存在其他未被考虑到的影响因素"

② 不应过度解读的点（1句）：明确读者最容易误读的地方

③ 行动建议（1句，必须包含）：在不确定性下读者该怎么做
   ✅ "在相关指南更新之前，建议维持现有的医疗建议，如有疑问请咨询医生。"

▌禁止事项
- 不用学术腔描述局限（读者看不懂）
- 不以恐吓式语气描述（"这个研究可能是错的！"）
- 不省略行动建议

【输出禁区（零容忍）】
- 不输出 [共识]、[推断]、[[待补充]] 等任何内部标注

字数：{wt}
风格：{audience['tone']}，语气更谨慎、客观
请直接输出正文。
"""


# 选题与大纲（供规划阶段调用）
def get_topic_plan(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("topic_plan")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform=state.get("platform", "wechat"),
        )
    return f"""请为以下医学科普文章进行选题分析和内容规划。

【基本信息】
主题：{state.get('topic', '')}
专科领域：{state.get('specialty', '')}
目标读者：{audience['desc']}
目标平台：{state.get('platform', 'wechat')}

【任务要求】
请生成一份科普选题分析，包含：

1. **选题价值分析**（100字以内）
   - 这个主题对目标读者的实际意义是什么？
   - 读者最关心的核心问题是什么？

2. **内容边界划定**
   - 本次科普应该覆盖的核心内容（3-5个要点）
   - 应该刻意回避的内容（容易引起误解或超出科普范围的内容）

3. **读者痛点梳理**
   - 目标读者对这个主题最常见的误解是什么？（2-3个）
   - 读者最希望知道的实用信息是什么？（2-3个）

4. **推荐写作角度**
   - 基于以上分析，推荐最适合的切入角度和叙述框架

【输出格式】
直接输出分析内容，使用 Markdown 格式，不需要重复问题标题。
"""


def get_outline(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    twc = state.get("target_word_count")
    platform = state.get("platform", "wechat")
    if twc:
        platform_word_guide = f"全文目标 {twc} 字"
    else:
        platform_word_guide = PLATFORM_WORD_GUIDE.get(platform, "整体建议 800-1500 字")
    tpl = load_task("outline")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform=platform,
            platform_word_guide=platform_word_guide,
        )
    return f"""请为以下医学科普文章生成详细大纲。

【文章基本信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
目标平台：{platform}（{platform_word_guide}）

【大纲要求】
请生成包含以下五个标准章节的详细大纲：

**章节一：引言（吸引读者）**
- 开头钩子：用什么场景/问题/数据/故事吸引读者
- 建立共鸣：为什么这个话题与读者相关
- 预告内容：读者读完这篇文章能得到什么

**章节二：正文（核心科普）**
- 核心知识点列表（3-4个，按逻辑顺序排列）
- 每个知识点的讲解思路
- 需要澄清的常见误区

**章节三：典型案例（故事化）**
- 案例人物设定（虚构，需说明为虚构）
- 案例如何体现核心知识点
- 案例的情感触点

**章节四：问答（实用信息）**
- 目标读者最可能提出的 3 个问题
- 每个问题的回答要点

**章节五：健康小结**
- 核心行动建议（2-3条，具体可操作）
- 结尾的情感收束

【输出格式】
使用结构化列表输出大纲，每个章节的各要素单独列出，字数参考见括号。
"""


# 口播脚本
_ORAL_TIME_RANGES = {
    "hook": ("00:00", "00:03"),
    "body_1": ("00:03", "00:15"),
    "body_2": ("00:15", "00:30"),
    "body_3": ("00:30", "00:45"),
    "summary": ("00:45", "00:55"),
    "cta": ("00:55", "01:00"),
}


def _oral_time_range(state: dict, section_type: str) -> tuple[str, str]:
    meta = state.get("format_meta", {})
    if meta.get("start_time") and meta.get("end_time"):
        return meta["start_time"], meta["end_time"]
    return _ORAL_TIME_RANGES.get(section_type, ("00:00", "01:00"))


def get_oral_hook(state: dict) -> str:
    st, et = _oral_time_range(state, "hook")
    hooks = {
        "wechat": "可以用反问句开头，或用一个读者身边可能发生的场景",
        "xiaohongshu": "用「你知道吗」或直接抛出一个让人惊讶的事实",
        "douyin": "第一句就是最强的观点或最惊人的事实，没有铺垫",
        "bilibili": "可以用悬念或「你可能不知道……」切入",
    }
    platform_hook = hooks.get(state.get("platform", "douyin"), hooks["douyin"])
    tpl = load_task("oral_hook")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            platform=state.get("platform", "douyin"),
            target_audience=state.get("target_audience", "public"),
            st=st,
            et=et,
            platform_hook=platform_hook,
        )
    return f"""请为口播短视频撰写开场钩子（前3秒内容）。

【视频信息】
主题：{state.get('topic', '')}
目标平台：{state.get('platform', 'douyin')}
目标受众：{state.get('target_audience', 'public')}

【格式要求（严格遵守）】
[{st}-{et}] 医生（口播）：[开场内容，≤50字，口语化，无停顿处可加"/"]

【钩子类型可任选其一】
- 悬念型：制造好奇，让人想知道答案
- 反转型：颠覆常识，让人惊讶
- 共鸣型：说出观众的心里话
- 数据型：用一个冲击力强的数字开场
- 场景型：描述一个具体画面

【平台风格】
{platform_hook}

【语言规范】
- 完全口语化，像说话不像写文章
- 短句为主，每句≤15字
- 第一个字不能是「我」（避免弱开场）

请直接输出开场钩子脚本行。
"""


def get_oral_body(state: dict, section_type: str = "body_1") -> str:
    st, et = _oral_time_range(state, section_type)
    meta = state.get("format_meta", {})
    seg = meta.get("segment_number") or (
        int(section_type.replace("body_", "")) if "body_" in section_type else 1
    )
    total = meta.get("total_segments", 3)
    tpl = load_task("oral_body")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            platform=state.get("platform", "douyin"),
            specialty=state.get("specialty", ""),
            seg=seg,
            total=total,
            st=st,
            et=et,
        )
    return f"""请为口播短视频撰写正文第 {seg}/{total} 段。

【视频信息】
主题：{state.get('topic', '')}
目标平台：{state.get('platform', 'douyin')}
专科：{state.get('specialty', '')}

【格式要求（严格遵守）】
[{st}-{et}] 医生（口播）：[本段内容，≤80字，口语化，无停顿处可加"/"]

【内容要求】
- 本段对应一个清晰的知识点或逻辑块
- 与前后段有自然过渡，不重复
- 口语化：短句、停顿自然，像在说话

【语言规范】
- 完全口语化，无书面语
- 每句≤15字，节奏快
- 可适当用「你看」「其实」「所以说」等口语连接

请直接输出本段脚本行。
"""


def get_oral_summary(state: dict) -> str:
    st, et = _oral_time_range(state, "summary")
    tpl = load_task("oral_summary")
    if tpl:
        return tpl.format(topic=state.get("topic", ""), st=st, et=et)
    return f"""请为口播短视频撰写总结段。

【视频信息】
主题：{state.get('topic', '')}

【格式要求（严格遵守）】
[{st}-{et}] 医生（口播）：[总结内容，≤60字]

【内容要求】
- 1-2句话提炼核心要点
- 给观众一个记忆锚点
- 不要重复前文原话，要升华

请直接输出总结段脚本行。
"""


def get_oral_cta(state: dict) -> str:
    st, et = _oral_time_range(state, "cta")
    tpl = load_task("oral_cta")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            platform=state.get("platform", "douyin"),
            st=st,
            et=et,
        )
    return f"""请为口播短视频撰写行动号召（CTA）。

【视频信息】
主题：{state.get('topic', '')}
目标平台：{state.get('platform', 'douyin')}

【格式要求（严格遵守）】
[{st}-{et}] 医生（口播）：[CTA内容，≤40字]

【内容要求】
- 明确、具体、可操作（如「点赞收藏」「转发给家人」）
- 语气亲切有力，不强硬
- 可结合平台特色（抖音：关注+点赞；B站：一键三连）

请直接输出 CTA 脚本行。
"""


# 情景剧本
def get_drama_scene_setup(state: dict) -> str:
    tpl = load_task("drama_scene_setup")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
        )
    return f"""请为情景短视频撰写场景设定。

【剧本信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}

【场景设定要求】
① 地点：具体且可拍摄（如家中客厅、医院候诊区）
② 人物：2-3人，角色明确（如患者、家属、医生/护士）
③ 情境：与医学主题相关的日常场景
④ 氛围：轻松、生活化，便于观众代入

【输出格式】
- 场景：[地点]
- 人物：[角色1]、[角色2]……
- 情境：[简要描述]
- 时长参考：约60秒

请直接输出场景设定。
"""


def get_drama_dialogue(state: dict, section_type: str = "scene_1") -> str:
    meta = state.get("format_meta", {})
    idx = meta.get("scene_index")
    if idx is None and section_type:
        if section_type == "ending":
            idx = 4
        elif section_type.startswith("scene_"):
            try:
                idx = int(section_type.replace("scene_", ""))
            except ValueError:
                idx = 1
        else:
            idx = 1
    idx = idx or 1
    scene_names = {1: "场景1（开场/引入）", 2: "场景2（发展）", 3: "场景3（高潮/转折）", 4: "结尾"}
    scene_name = scene_names.get(idx, f"场景{idx}")
    scene_requirement = "收束情境，点明知识点，给观众记忆点" if idx == 4 else "推进情节，融入医学知识"
    scene_setup_context = (state.get("scene_setup_context") or "").strip()
    scene_setup_block = f"\n【已确定场景设定（必须严格沿用）】\n{scene_setup_context}\n" if scene_setup_context else ""
    tpl = load_task("drama_dialogue")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            scene_name=scene_name,
            scene_idx=idx,
            scene_requirement=scene_requirement,
            scene_setup_context=scene_setup_context,
            scene_setup_block=scene_setup_block,
        )
    return f"""请为情景短视频撰写{scene_name}的台词与动作。

【剧本信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
{scene_setup_block}

【格式要求（严格遵守）】
人物名：（台词内容）
[动作说明用方括号，如：递上检查单]

【写作规范】
- 台词口语化，适合短视频演绎
- 每句台词≤30字，节奏明快
- 动作说明简洁，指导拍摄
- 医学知识点通过对话自然带出，不说教
- 不得新增与场景设定无关的人物、地点、关系设定

【场景{idx}要求】
{scene_name}：{scene_requirement}

请直接输出本场台词与动作。
"""


# 动画分镜 - 委托给 StoryboardWriter agent
def get_storyboard_section(state: dict, section_type: str = "anim_plan") -> str:
    from app.agents.storyboard.storyboard_agent import StoryboardWriter
    writer = StoryboardWriter(section_type)
    return writer.get_base_prompt(state)


# 播客脚本
def _audio_time_info(state: dict, section_type: str) -> str:
    """生成播客时间/字数参考信息（播音约 150 字/分钟）"""
    meta = state.get("format_meta", {})
    dur_sec = meta.get("duration_sec", 180)
    words = int(dur_sec / 60 * 150) if dur_sec else 300
    mins, secs = divmod(int(dur_sec), 60)
    return f"预计时长约 {mins} 分 {secs} 秒，字数约 {words} 字（按 150 字/分钟）"


def get_audio_opening(state: dict) -> str:
    tpl = load_task("audio_opening")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            time_info=_audio_time_info(state, "opening"),
        )
    return f"""请为医学播客撰写开场。

【内容信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}

【开场要求】
- 问候听众，点明本期主题
- 制造期待，说明本期的价值
- 自然过渡到话题引入

{_audio_time_info(state, "opening")}
风格：亲切、专业但不严肃
请直接输出开场文案。
"""


def get_audio_topic_intro(state: dict) -> str:
    tpl = load_task("audio_topic_intro")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            time_info=_audio_time_info(state, "topic_intro"),
        )
    return f"""请为医学播客撰写话题引入。

【内容信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}

【引入要求】
- 说明为什么这个话题值得关注
- 建立与听众的关联
- 为深入讲解做铺垫

{_audio_time_info(state, "topic_intro")}
请直接输出话题引入文案。
"""


def get_audio_deep_dive(state: dict) -> str:
    tpl = load_task("audio_deep_dive")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            time_info=_audio_time_info(state, "deep_dive"),
        )
    return f"""请为医学播客撰写深入讲解部分（核心内容）。

【内容信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}

【讲解要求】
- 展开核心医学知识点，层次清晰
- 用类比和例子帮助理解
- 口语化表达，像在聊天
- 适当留「钩子」保持听众注意力

{_audio_time_info(state, "deep_dive")}
请直接输出深入讲解文案。
"""


def get_audio_extension(state: dict) -> str:
    tpl = load_task("audio_extension")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            time_info=_audio_time_info(state, "extension"),
        )
    return f"""请为医学播客撰写延伸内容。

【内容信息】
主题：{state.get('topic', '')}

【延伸要求】
- 拓展相关实用信息或常见误区
- 与核心内容有联系但不重复
- 可包含「很多人会问……」类互动感

{_audio_time_info(state, "extension")}
请直接输出延伸内容。
"""


def get_audio_closing(state: dict) -> str:
    tpl = load_task("audio_closing")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            time_info=_audio_time_info(state, "closing"),
        )
    return f"""请为医学播客撰写收尾。

【内容信息】
主题：{state.get('topic', '')}

【收尾要求】
- 总结核心要点
- 给出行动建议或思考
- 自然结束，可引导订阅/关注

{_audio_time_info(state, "closing")}
请直接输出收尾文案。
"""


# 知识卡片
CARD_COLOR_GUIDANCE = {
    "blue": "蓝色系，专业感强，适合机制解释类",
    "green": "绿色系，健康积极，适合预防/建议类",
    "orange": "橙色系，温暖活泼，适合行动类/儿科",
    "purple": "紫色系，权威感，适合数据/研究类",
    "red": "红色系，警示感，适合风险提示类",
}


def get_card_content(state: dict, section_type: str = "card_1") -> str:
    meta = state.get("format_meta", {})
    card_index = meta.get("card_index") or (
        int(section_type.replace("card_", "")) if section_type and "card_" in section_type else 1
    )
    total = meta.get("total_cards", 5)
    card_title = meta.get("card_title", "")
    color_scheme = meta.get("color_scheme", "blue")
    audience = AUDIENCE_PROFILES.get(
        state.get("target_audience", "public"),
        AUDIENCE_PROFILES["public"],
    )
    color_guidance = CARD_COLOR_GUIDANCE.get(color_scheme, CARD_COLOR_GUIDANCE["blue"])
    card_title_line = f"本卡标题：{card_title}" if card_title else ""
    card_title_for_json = card_title or "本卡标题"
    tpl = load_task("card_content")
    if tpl:
        return tpl.format(
            card_index=card_index,
            total=total,
            topic=state.get("topic", ""),
            card_title_line=card_title_line,
            card_title_for_json=card_title_for_json,
            color_guidance=color_guidance,
            audience_desc=audience["desc"],
            audience_vocabulary=audience["vocabulary"],
        )
    return f"""请为医学科普知识卡片系列生成第 {card_index}/{total} 张卡片的内容。

【卡片信息】
整体主题：{state.get('topic', '')}
{f'本卡标题：{card_title}' if card_title else ''}
配色方案：{color_guidance}
目标受众：{audience['desc']}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "card_index": {card_index},
  "card_title": "{card_title or "本卡标题"}",
  "headline": "卡片最显眼的一句话（≤15字，浓缩本卡核心）",
  "body_text": "正文内容（中文，80-120字，本卡的核心知识点）",
  "key_takeaway": "划重点（≤20字，读者最应该记住的一句话）",
  "illustration_desc": "配图描述（英文，20-40词，描述卡片主视觉图，DALL·E 使用）",
  "icon_suggestions": ["图标1建议", "图标2建议"],
  "data_placeholder": "[[待补充：所需数据描述]] 或空字符串（如本卡需要数据支撑但无来源）"
}}

【内容规范】

headline（标题）：
- 要有张力，吸引人点进去看
- ✅ "血糖高了，先别急着吃药"
- ❌ "血糖管理的重要性"

body_text（正文）：
- 一张卡只讲一件事
- 分2-3个短段，每段1-2句
- 语言：{audience['vocabulary']}

illustration_desc：
- 这是给 DALL·E 的图像提示词，必须用英文
- 要配合本卡主题，不要太抽象
- 指明风格：flat design medical illustration, bright colors, white background

请直接输出 JSON，不要有任何其他文字。
"""


# 科普绘本
def get_picture_book_planner(state: dict) -> str:
    tpl = load_task("picture_book_planner")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
        )
    return f"""请为儿童医学科普绘本规划整体内容方案。

【绘本信息】
主题：{state.get('topic', '')}（面向儿童的科普）
专科：{state.get('specialty', '')}
目标年龄：3-12岁儿童

【规划要求】

请输出以下 JSON 格式：

{{
  "total_pages": 8,
  "story_title": "绘本故事标题（吸引儿童，有画面感）",
  "main_character": "主角设定（如：小红细胞/医生小熊/叫豆豆的小朋友）",
  "core_message": "全书最核心的一个知识点（儿童能理解的版本）",
  "pages": [
    {{
      "page_index": 1,
      "page_function": "开场/引入问题/展开/高潮/解决/结尾",
      "page_theme": "本页传递的内容",
      "emotion": "本页的情绪基调"
    }},
    ...
  ]
}}

【绘本规划原则】
- 页数：6-10页（每页一个场景）
- 主角：最好是拟人化的身体部件/动物/儿童（比成人角色更亲切）
- 叙事：有起承转合，不是知识点的罗列
- 结尾：解决问题，给儿童正向强化（不恐吓）

【特别要求】
本绘本面向儿童，所有内容必须：
- 不引起恐惧感
- 不出现任何血腥/手术/痛苦的画面
- 用好奇心和探索感驱动故事

请直接输出 JSON。
"""


def get_picture_book_page(state: dict, section_type: str = "page_1") -> str:
    meta = state.get("format_meta", {})
    page_index = meta.get("page_index") or (
        int(section_type.replace("page_", "")) if section_type and "page_" in section_type else 1
    )
    total = meta.get("total_pages", 8)
    page_theme = meta.get("page_theme", "")
    main_char = meta.get("main_character", "主角")
    planner_items = meta.get("planner_items", [])
    if planner_items and not page_theme:
        item = next((p for p in planner_items if p.get("page_index") == page_index), None)
        if not item and 0 < page_index <= len(planner_items):
            item = planner_items[page_index - 1]
        if item:
            page_theme = item.get("page_theme", "")
    planner_json = meta.get("planner_json", {})
    if planner_json:
        main_char = main_char if main_char != "主角" else planner_json.get("main_character", main_char)
        total = planner_json.get("total_pages", total)
    story_title = meta.get("story_title") or planner_json.get("story_title", "")
    core_message = meta.get("core_message") or planner_json.get("core_message", "")
    planner_block = ""
    if planner_json:
        import json as _json
        planner_block = f"\n【绘本规划总览（必须遵循）】\n{_json.dumps(planner_json, ensure_ascii=False, indent=2)}\n"
    tpl = load_task("picture_book_page")
    if tpl:
        return tpl.format(
            page_index=page_index,
            total=total,
            topic=state.get("topic", ""),
            page_theme=page_theme or "待补充",
            main_char=main_char,
        )
    return f"""请为儿童医学科普绘本生成第 {page_index}/{total} 页的内容。

【绘本信息】
整体主题：{state.get('topic', '')}
{f'故事标题：{story_title}' if story_title else ''}
本页主题：{page_theme or "待补充"}
主角：{main_char}
{f'核心信息：{core_message}' if core_message else ''}
目标年龄：3-12岁
{planner_block}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "page_index": {page_index},
  "page_text": "这页的文字（中文，≤20字，一句话，小学低年级可读）",
  "illustration_desc": "插图描述（英文，30-50词，非常详细，指明儿童绘本风格）",
  "sound_words": "拟声词或互动词（可选，如'哗啦啦！''你猜猜看？'）",
  "parent_note": "给家长的延伸引导（可选，帮助家长和孩子互动讨论）"
}}

【page_text 规范（最重要）】
- 最多20字，最少6字
- 只有一件事，不能有"并且"、"因此"、"所以"等连接词
- 用儿童的视角说话
- ✅ "小白细胞是身体里的小战士！"（12字，生动）
- ✅ "豆豆肚子疼，妈妈带他去医院。"（15字，叙事）
- ❌ "当体内的白细胞发现细菌时，会立即发动免疫反应保护身体。"（太长太复杂）

【illustration_desc 规范】
- 必须用英文
- 必须包含：主体+动作+表情+背景+风格说明
- 风格：children's picture book illustration, cute, bright colors, simple backgrounds, no scary elements, warm and friendly
- ✅ "A cheerful white blood cell character wearing a tiny shield, running happily through a colorful bloodstream, waving at red blood cells. Bright primary colors, children's book illustration style, no scary elements."

请直接输出 JSON，不要有任何其他文字。
"""


# 科普海报（分节生成，对齐规范）
def get_poster_headline(state: dict) -> str:
    return _poster_section_prompt(state, "main_title", "主标题", "≤10字，视觉最大，核心信息，路人3秒内明白这是关于什么的")

def get_poster_core_message(state: dict) -> str:
    return _poster_section_prompt(state, "sub_title + key_points", "副标题与核心要点", "副标题≤20字；要点2-3条，每条≤15字，用数字/动词开头")

def get_poster_data_points(state: dict) -> str:
    return _poster_section_prompt(state, "data_highlight", "数据亮点", "≤20字，有文献来源则写；否则用 [[待补充：所需数据]]")

def get_poster_cta(state: dict) -> str:
    return _poster_section_prompt(state, "call_to_action", "行动号召", "≤15字，如'发现症状，及时就医'")

def get_poster_visual_desc(state: dict) -> str:
    return _poster_section_prompt(state, "main_visual_desc + color_theme", "主视觉图描述与配色", "英文30-50词供图像生成；配色：blue_professional/green_health/red_alert/orange_warm")


def _poster_section_prompt(state: dict, part: str, label: str, spec: str) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("poster_section")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform=state.get("platform", "wechat"),
            label=label,
            spec=spec,
        )
    return f"""请为医学科普海报生成{label}部分。

【海报信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标受众：{audience['desc']}
使用场景：{state.get('platform', 'wechat')}（候诊室/宣传栏/线上转发）

【本部分要求】
{spec}

【文案原则】
- 海报字数极度精炼，每个字都要有价值
- 要点条目用数字/动词开头（❌"保持健康" ✅"每天走路30分钟"）
- 数据来源有保障才用，没有来源用 [[待补充：所需数据]]

请直接输出本部分内容。若需结构化输出，可用 JSON 格式。
"""


# 自测科普
def get_quiz_intro(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    meta = state.get("format_meta", {})
    total_q = meta.get("total_questions", 5)
    audience_style = {
        "public": ('轻松游戏感', '"来，测测你对XX了解多少？"'),
        "patient": ('实用感', '"了解自己的疾病，是管理好它的第一步"'),
        "student": ('挑战感', '"你以为你懂了？来验证一下"'),
        "children": ('探险感', '"小侦探出动！帮身体找到健康的秘密！"'),
        "professional": ('专业验证感', '"临床上的几个细节，你都清楚吗？"'),
    }.get(state.get("target_audience", "public"), ("轻松感", '"来测试一下"'))
    tpl = load_task("quiz_intro")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            total_q=total_q,
            audience_style_0=audience_style[0],
            audience_style_1=audience_style[1],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为医学科普自测文章撰写引言部分。

【文章信息】
测验主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
题目数量：{total_q} 道
引言风格：{audience_style[0]}（参考语气：{audience_style[1]}）

【写作任务】
引言需要完成三件事（按优先级）：
① 引发好奇（用与读者相关的场景或问题）
② 建立参与感（"来测测你"，不是"学习以下知识"）
③ 降低心理压力（"没有对错，测完你会有新收获"）

▌正例与反例
✅ 正确（public受众）："关于糖尿病，你觉得自己了解多少？来做5道题测测看——很多人以为自己清楚，结果发现有几个误区从没想过。"
❌ 错误："本文将测试您对糖尿病相关知识的掌握程度，请认真阅读每道题并选择最合适的答案。"（像考试通知，有压力感）

▌禁止事项
· 不要说"请如实作答"（有压力感）
· 不要说"本文将测试您的知识掌握程度"（太正式）
· 不要在引言里透露任何答案
· 不要超过3句话

▌语言要求
风格：{audience['tone']}  句长：{audience['sentence']}
▌字数：50-90字

请直接输出引言正文，不需要标注"引言"标题。
"""


QUIZ_QUESTION_TYPES = ["误区识别", "知识测试", "行为评估"]


def get_quiz_question(state: dict, section_type: str = "q_1") -> str:
    meta = state.get("format_meta", {})
    q_index = meta.get("question_index") or (
        int(section_type.replace("q_", "")) if section_type and "q_" in section_type else 1
    )
    q_type = meta.get("question_type", "误区识别")
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("quiz_question")
    if tpl:
        return tpl.format(
            q_index=q_index,
            q_type=q_type,
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
        )
    return f"""请为医学科普自测生成第 {q_index} 道题目。

【自测信息】
主题：{state.get('topic', '')}
题目类型：{q_type}
目标读者：{audience['desc']}

【输出格式（严格遵守，必须为合法 JSON）】

{{
  "question_index": {q_index},
  "question_type": "{q_type}",
  "question_text": "题目（≤40字，用读者自然会问的方式提问）",
  "options": [
    "A. 选项A（≤25字）",
    "B. 选项B（≤25字）",
    "C. 选项C（≤25字）",
    "D. 选项D（≤25字，可选，只有真正需要4个选项时才加）"
  ],
  "correct_answer": "A/B/C/D",
  "explanation": "答案解析（中文，80-120字，解释为什么正确答案是对的，错误选项为什么不对）",
  "key_learning": "本题核心知识点（≤20字，这道题最重要的一个收获）"
}}

【题目设计原则】

题目类型说明：
- 误区识别：设计一个读者可能相信的错误观念作为干扰项
  示例："以下关于糖尿病的说法，哪一个是正确的？"

- 知识测试：考查读者对疾病/健康知识的了解
  示例："正常成人空腹血糖应该低于多少？"（数据来自文献或 [[待补充：所需数据]]）

- 行为评估：评估读者的健康行为
  示例："你最近一次测量血压是什么时候？"

解析规范：
- 先说正确答案是对的（"B是正确的，因为……"）
- 再点评最常见的错误选项（"很多人选A，但其实……"）
- 语气温和，不批评选错的读者
- 结尾给出实用建议

请直接输出 JSON。
"""


def get_quiz_summary(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("quiz_summary")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为医学科普自测文章撰写结尾总结部分。

【文章信息】
测验主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
自测结尾的核心原则：不管答对几道，读者都应该有收获感，而不是受打击。

▌内容结构
① 成绩解读（不打分，给认知框架）：告诉读者这5道题覆盖了什么，而不是他答对了几道。
✅ "这5道题，覆盖了糖尿病管理中最容易被忽视的几个细节……不管你答对了几道，能重新思考这些问题本身就有价值。"
❌ "如果你全部答对，说明你是专家！如果你答错了3道以上……"（打分式，让答错的人受挫）

② 核心收获（1-2句话）：从整个测验提炼最重要的一个认知。
③ 行动建议（2-3条，具体可操作）：基于测验内容的立即可执行建议，不涉及具体药物。
④ 就医提示（1句，必须包含）：说明什么情况下需要寻求专业帮助。

▌禁止事项
· 不用打分的方式评价读者（避免让人受挫）
· 不重复测验中已经详细解释过的内容
· 行动建议不涉及具体药物或剂量

▌语言要求
风格：{audience['tone']}，积极正向，给读者信心
句长：{audience['sentence']}
▌字数：120-200字

请直接输出总结正文，可以有小标题（不要用"总结"这个标题）。
"""


# H5 大纲（分节生成，对齐规范）
def get_h5_page_cover(state: dict) -> str:
    return _h5_section_prompt(state, "封面页", "吸引点开的标题、视觉主图描述、分享文案雏形")

def get_h5_page(state: dict, section_type: str = "page_1") -> str:
    meta = state.get("format_meta", {})
    idx = meta.get("page_index")
    if idx is None and section_type and section_type.startswith("page_"):
        try:
            idx = int(section_type.replace("page_", ""))
        except ValueError:
            idx = 1
    return _h5_page_prompt(state, idx or 1)

def get_h5_page_end(state: dict) -> str:
    return _h5_section_prompt(state, "结束/分享页", "总结要点、分享引导、行动号召")


# 竖版长图
def get_long_image_planner(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    platform = state.get("platform", "wechat")
    platform_guide = {
        "wechat": "微信朋友圈/公众号，竖版滑动，推荐5-8个区块",
        "xiaohongshu": "小红书长图，视觉感强，推荐4-6个区块，每块信息量不宜过多",
    }.get(platform, "通用长图，推荐5-7个区块")
    tpl = load_task("long_image_planner")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform=platform,
            platform_guide=platform_guide,
        )
    return f"""请为竖版长图进行整体内容规划。

【长图信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
目标平台：{platform}（{platform_guide}）

【输出格式（严格遵守，必须为合法JSON）】
{{
  "total_sections": 6,
  "color_theme": "blue_professional",
  "layout_style": "card_stack",
  "story_line": "一句话说明整体叙事逻辑",
  "sections": [{{"section_index": 1, "section_type": "cover|hook|knowledge|tip|data|warning|cta", "section_theme": "本区块主题", "estimated_chars": 30}}]
}}

区块类型：cover封面(1个) / hook钩子 / knowledge知识(每区块1个知识点) / tip实用技巧 / data数据(需RAG来源) / warning警示 / cta行动号召(1个,最后)
色彩主题：blue_professional / green_health / orange_warm / red_alert / purple_authority

▌禁止事项
· 不在一个区块内堆砌多个知识点
· cover和cta区块各只有一个
· data区块无RAG来源时不设此类型

请直接输出JSON。
"""


def get_long_image_cover(state: dict) -> str:
    """竖版长图封面区"""
    meta = {
        "section_index": 1,
        "section_type": "cover",
        "section_theme": "封面区：主标题+副标题+视觉钩子",
        "total_sections": 6,
    }
    return get_long_image_section({**state, "format_meta": {**state.get("format_meta", {}), **meta}}, "cover")


def get_long_image_section(state: dict, section_type: str = "section_1") -> str:
    meta = state.get("format_meta", {})
    section_index = meta.get("section_index") or (
        int(section_type.replace("section_", "")) if "section_" in section_type else 1
    )
    total = meta.get("total_sections", 6)
    block_type = meta.get("section_type", "knowledge")
    section_theme = meta.get("section_theme", "")
    color_theme = meta.get("color_theme", "blue_professional")
    planner_items = meta.get("planner_items", [])
    if planner_items and not section_theme:
        item = next((p for p in planner_items if p.get("section_index") == section_index), None)
        if not item and 0 < section_index <= len(planner_items):
            item = planner_items[section_index - 1]
        if item:
            section_theme = item.get("section_theme", "")
            if not block_type or block_type == "knowledge":
                block_type = item.get("section_type", block_type)
    planner_json = meta.get("planner_json", {})
    if planner_json:
        color_theme = color_theme if color_theme != "blue_professional" else planner_json.get("color_theme", color_theme)
        total = planner_json.get("total_sections", total)
    story_line = meta.get("story_line") or planner_json.get("story_line", "")
    planner_block = ""
    if planner_json:
        import json as _json
        planner_block = f"\n【整体规划总览（必须遵循）】\n{_json.dumps(planner_json, ensure_ascii=False, indent=2)}\n"
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("long_image_section")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            section_theme=section_theme,
            section_type=block_type,
            section_index=section_index,
            total_sections=total,
            audience_desc=audience["desc"],
            color_theme=color_theme,
            audience_vocabulary=audience["vocabulary"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为竖版长图生成第 {section_index}/{total} 个区块的内容。

【长图信息】
整体主题：{state.get('topic', '')}
{f'整体叙事线：{story_line}' if story_line else ''}
本区块主题：{section_theme}
区块类型：{block_type}
目标读者：{audience['desc']}
整体配色：{color_theme}
{planner_block}

【输出格式（合法JSON）】
{{
  "section_index": {section_index},
  "section_type": "{block_type}",
  "main_text": "主要文案内容（中文）",
  "highlight_words": ["关键词1", "关键词2"],
  "image_prompt": "配图描述（英文，20-35词）",
  "layout_notes": "排版建议（≤30字）"
}}

【image_prompt必须英文】
✅ "Simple flat design illustration of vegetables on a plate, blue and white professional color scheme"
❌ "先吃蔬菜的图片"（中文无效）

【禁止事项】
· data类型：无RAG来源时main_text不出现具体数值
· 不在main_text里出现具体药物名称或剂量

请直接输出JSON。
"""


def get_long_image_footer(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    platform = state.get("platform", "wechat")
    platform_cta = {
        "wechat": "引导转发给家人朋友，或关注公众号获取更多科普",
        "xiaohongshu": "引导收藏+点赞，「收藏备用，关键时刻用得上」",
    }.get(platform, "引导读者采取健康行动或就医")
    tpl = load_task("long_image_footer")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            platform=platform,
            platform_cta=platform_cta,
            audience_tone=audience["tone"],
        )
    return f"""请为竖版长图撰写结尾区文案。

【长图信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}
目标平台：{platform}
行动号召方向：{platform_cta}

【输出格式（JSON）】
{{
  "summary_line": "核心总结（≤20字）",
  "action_items": ["行动建议1（≤25字）", "行动建议2"],
  "medical_reminder": "就医提示（≤30字，包含具体症状）",
  "share_copy": "分享文案（≤35字）",
  "footer_image_prompt": "结尾配图描述（英文，15-25词）"
}}

▌禁止事项
· action_items不涉及具体药物
· medical_reminder不能用恐吓式表达
· share_copy不能是无聊的"欢迎关注"

请直接输出JSON。
"""


def _h5_section_prompt(state: dict, page_label: str, spec: str) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("h5_section")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            page_label=page_label,
            spec=spec,
        )
    return f"""请为医学科普 H5 互动页面生成{page_label}的大纲内容。

【H5 信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}
传播渠道：微信朋友圈/公众号

【本页要求】
{spec}

【H5 设计原则】
- 每页只传达一个核心信息
- 移动端阅读，文案精炼（≤60字/页）
- 互动类型建议：知识问答、滑动解锁、点击展开、测验结果

请直接输出本页内容。
"""


def _h5_page_prompt(state: dict, page_index: int) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("h5_page")
    if tpl:
        return tpl.format(
            page_index=page_index,
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
        )
    return f"""请为医学科普 H5 互动页面生成第 {page_index} 页的大纲内容。

【H5 信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}
传播渠道：微信朋友圈/公众号

【本页要求】
- page_type：知识页|互动页|结果页 等
- page_title：本页标题（≤15字）
- page_content：本页文案（≤60字）
- interaction：无|点击|滑动|测验|动画
- interaction_desc：互动方式的具体描述
- visual_desc：本页视觉描述（英文，给设计师参考）

【设计原则】
- 每页只传达一个核心信息
- 必须有互动元素（纯文字翻页体验差）
- 互动类型：知识问答、滑动解锁、点击展开、测验结果

请直接输出本页内容，可用 JSON 或结构化文本。
"""


# 通用 fallback
def get_fallback_prompt(state: dict, section_type: str) -> str:
    tpl = load_task("fallback")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            target_audience=state.get("target_audience", "public"),
            platform=state.get("platform", "wechat"),
            section_type=section_type,
        )
    return f"""请为医学科普内容撰写本章节。

【基本信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{state.get('target_audience', 'public')}
平台：{state.get('platform', 'wechat')}
章节类型：{section_type}

要求：语言通俗，不给出具体医学建议或剂量。遵循防编造规则。
"""


# 路由表：content_format -> section_type -> 函数
TASK_PROMPT_FUNCS = {
    "article": {
        "topic": get_topic_plan,
        "outline": get_outline,
        "intro": get_article_intro,
        "body": get_article_body,
        "case": get_article_case,
        "qa": get_article_qa,
        "summary": get_article_summary,
    },
    "debunk": {
        "rumor_present": get_debunk_rumor_present,
        "verdict": get_debunk_verdict,
        "debunk_1": lambda s: get_debunk_point(s, "debunk_1"),
        "debunk_2": lambda s: get_debunk_point(s, "debunk_2"),
        "debunk_3": lambda s: get_debunk_point(s, "debunk_3"),
        "correct_practice": get_debunk_correct_practice,
        "anti_fraud": get_debunk_anti_fraud,
    },
    "qa_article": {
        "qa_intro": get_qa_intro,
        "qa_1": lambda s: get_qa_single(s, "qa_1"),
        "qa_2": lambda s: get_qa_single(s, "qa_2"),
        "qa_3": lambda s: get_qa_single(s, "qa_3"),
        "qa_4": lambda s: get_qa_single(s, "qa_4"),
        "qa_5": lambda s: get_qa_single(s, "qa_5"),
        "qa_summary": get_qa_summary,
    },
    "story": {
        "hook": get_story_hook,
        "development": get_story_development,
        "turning_point": get_story_turning_point,
        "science_core": get_story_science_core,
        "resolution": get_story_resolution,
        "action_list": get_story_action_list,
        "closing_quote": get_story_closing_quote,
    },
    "research_read": {
        "one_liner": get_research_one_liner,
        "study_card": get_research_study_card,
        "why_matters": get_research_why_matters,
        "methods": get_research_methods,
        "findings": get_research_findings,
        "implication": get_research_implication,
        "limitation": get_research_limitation,
    },
    "oral_script": {
        "script_plan": lambda s: "oral_script_plan",
        "golden_hook": lambda s: "oral_golden_hook",
        "problem_setup": lambda s: "oral_problem_setup",
        "core_knowledge": lambda s: "oral_core_knowledge",
        "practical_tips": lambda s: "oral_practical_tips",
        "closing_hook": lambda s: "oral_closing_hook",
        "extras": lambda s: "oral_extras",
    },
    "drama_script": {
        "drama_plan": lambda s: "drama_plan",
        "cast_table": lambda s: "drama_cast_table",
        "act_1": lambda s: "drama_act_1",
        "act_2": lambda s: "drama_act_2",
        "act_3": lambda s: "drama_act_3",
        "act_4": lambda s: "drama_act_4",
        "act_5": lambda s: "drama_act_5",
        "finale": lambda s: "drama_finale",
        "filming_notes": lambda s: "drama_filming_notes",
    },
    "storyboard": {
        "anim_plan": get_storyboard_section,
        "char_design": get_storyboard_section,
        "reel_1": get_storyboard_section,
        "reel_2": get_storyboard_section,
        "reel_3": get_storyboard_section,
        "reel_4": get_storyboard_section,
        "reel_5": get_storyboard_section,
        "prod_notes": get_storyboard_section,
    },
    "audio_script": {
        "opening": get_audio_opening,
        "topic_intro": get_audio_topic_intro,
        "deep_dive": get_audio_deep_dive,
        "extension": get_audio_extension,
        "closing": get_audio_closing,
    },
    "card_series": {
        "series_plan": get_card_content,
        "cover_card": get_card_content,
        "card_1": get_card_content,
        "card_2": get_card_content,
        "card_3": get_card_content,
        "card_4": get_card_content,
        "card_5": get_card_content,
        "card_6": get_card_content,
        "card_7": get_card_content,
        "ending_card": get_card_content,
    },
    "picture_book": {
        "book_plan": get_picture_book_planner,
        "cover": get_picture_book_page,
        "spread_1": get_picture_book_page,
        "spread_2": get_picture_book_page,
        "spread_3": get_picture_book_page,
        "spread_4": get_picture_book_page,
        "spread_5": get_picture_book_page,
        "spread_6": get_picture_book_page,
        "spread_7": get_picture_book_page,
        "back_cover": get_picture_book_page,
    },
    "poster": {
        "poster_brief": get_poster_headline,
        "headline": get_poster_headline,
        "body_visual": get_poster_visual_desc,
        "cta_footer": get_poster_cta,
        "design_spec": get_poster_visual_desc,
    },
    "long_image": {
        "image_plan": get_long_image_planner,
        "title_block": get_long_image_cover,
        "intro_block": get_long_image_cover,
        "core_1": lambda s: get_long_image_section({**s, "format_meta": {**s.get("format_meta", {}), "section_index": 1, "section_type": "knowledge"}}, "core_1"),
        "core_2": lambda s: get_long_image_section({**s, "format_meta": {**s.get("format_meta", {}), "section_index": 2, "section_type": "knowledge"}}, "core_2"),
        "core_3": lambda s: get_long_image_section({**s, "format_meta": {**s.get("format_meta", {}), "section_index": 3, "section_type": "knowledge"}}, "core_3"),
        "core_4": lambda s: get_long_image_section({**s, "format_meta": {**s.get("format_meta", {}), "section_index": 4, "section_type": "knowledge"}}, "core_4"),
        "tips_block": get_long_image_footer,
        "warning_block": get_long_image_footer,
        "summary_cta": get_long_image_footer,
        "footer_info": get_long_image_footer,
    },
    "quiz_article": {
        "quiz_intro": get_quiz_intro,
        "q_1": get_quiz_question,
        "q_2": get_quiz_question,
        "q_3": get_quiz_question,
        "q_4": get_quiz_question,
        "q_5": get_quiz_question,
        "summary": get_quiz_summary,
    },
    "h5_outline": {
        "page_cover": get_h5_page_cover,
        "page_1": get_h5_page,
        "page_2": get_h5_page,
        "page_3": get_h5_page,
        "page_end": get_h5_page_end,
    },
    "patient_handbook": {
        "handbook_plan": lambda s: _get_handbook_prompt(s, "handbook_plan"),
        "cover": lambda s: _get_handbook_prompt(s, "cover"),
        "disease_know": lambda s: _get_handbook_prompt(s, "disease_know"),
        "treatment": lambda s: _get_handbook_prompt(s, "treatment"),
        "daily_care": lambda s: _get_handbook_prompt(s, "daily_care"),
        "followup": lambda s: _get_handbook_prompt(s, "followup"),
        "emergency": lambda s: _get_handbook_prompt(s, "emergency"),
        "faq": lambda s: _get_handbook_prompt(s, "faq"),
        "back_cover": lambda s: _get_handbook_prompt(s, "back_cover"),
    },
}


def _get_handbook_prompt(state: dict, section_type: str) -> str:
    from app.agents.handbook.handbook_agent import HandbookSectionAgent
    writer = HandbookSectionAgent(section_type)
    return writer.get_base_prompt(state)


def get_task_prompt(content_format: str, section_type: str, state: dict) -> str | None:
    """获取任务提示词，无则返回 None（使用 FORMAT_SECTION_PROMPTS fallback）"""
    funcs = TASK_PROMPT_FUNCS.get(content_format, {})
    func = funcs.get(section_type)
    if func:
        import inspect
        sig = inspect.signature(func)
        if "section_type" in sig.parameters:
            return func(state, section_type)
        return func(state)
    return None

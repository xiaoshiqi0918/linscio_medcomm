"""
Layer 3：任务提示词
按 content_format + section_type 返回详细任务指令
优先从 prompt-example/prompts/task/*.txt 加载，不存在时使用内置 f-string
"""
from app.agents.prompts.audiences import AUDIENCE_PROFILES
from app.agents.prompts.loader import load_platform_config, load_task

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
引言部分总字数：150-250字（抖音/小红书：50-100字）

▌禁止事项
- 不用「众所周知」「大家都知道」等开头
- 不用「本文将介绍」等论文式写法
- 不用感叹号密集的标题党风格
- 不要在引言里就开始讲知识点

请直接输出引言正文，不需要标注「引言」标题。
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
    return f"""请为以下医学科普文章撰写正文核心部分。

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

▌内容要求
① 知识点讲解（每个知识点独立一节）
   - 先给出结论，再展开解释（金字塔原则）
   - 每个知识点用一个具体的类比或例子说明
   - 如有争议的观点，明确说明「目前学界的主流观点认为」

② 误区澄清（至少 1 处）
   - 用「很多人以为……但实际上……」的结构
   - 纠正误区时语气平和，不批评读者

③ 数据处理
   - 如需引用数据但无 RAG 来源支撑，使用 [DATA: 描述] 占位
   - 有数据支撑时，以通俗方式表达（如「大约相当于10个人中有1个」）

④ 专业术语处理
   - 首次出现的专业术语：通俗说法（医学名称）
   - 示例：「血糖（简单说就是血液里的糖分含量）」

▌格式要求
{platform_format}
正文字数：400-800字（抖音：100-200字）

▌严格禁止
- 不给出具体用药剂量
- 不引用具体指南或研究名称（除非 RAG 提供了确切来源）
- 不使用「一定会」「绝对」等绝对化表述
- 不出现「……请咨询度娘」等导流表述

请直接输出正文内容，可以包含小标题，不需要在开头写「正文」两字。
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
    return f"""请为以下医学科普文章撰写常见问题解答（Q&A）部分。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【Q&A 写作规范】

▌问题设计（3个问题）
问题必须来自目标读者真实会有的疑惑，不是写作者自问自答的知识点。
选题原则：
- Q1：最常见的疑惑（通常是基础概念的误解）
- Q2：最实用的操作性问题（「我应该怎么做」类型）
- Q3：最有争议或最让人担心的问题（打消顾虑或澄清误区）

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
每个 Q&A 总字数：80-150字

▌禁止事项
- 问题不能过于专业（目标读者不会这样问）
- 回答不能模糊（不能只说「请咨询医生」而不给任何信息）
- 不能出现具体药物名称或剂量
- 回答末尾可以引导就医，但不能以「去看医生」作为唯一答案

请直接输出3个Q&A，格式为：
**Q：[问题]**
[回答内容]
"""


# 问答科普（qa_article 格式：独立引言/单题/总结）
def get_qa_intro(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    meta = state.get("format_meta", {})
    total_qa = meta.get("total_questions", 3)
    tpl = load_task("qa_intro")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            total_qa=total_qa,
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为问答科普文章撰写引言部分。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
问答数量：{total_qa} 组

【写作任务】
问答科普引言的黄金原则：极度精简，2-3句话完成以下两件事：
① 一句话定位（这里有什么）
② 一句话说明价值（读完你能得到什么）

✅ 正确示范："关于糖尿病，很多患者心里都有说不清楚的疑惑。这里整理了最常被问到的5个问题，直接给你明确的答案。"
❌ 错误示范（太长）："高血压是一种以收缩压和/或舒张压持续升高为特征的慢性疾病……"（不像问答引言）

▌禁止事项
· 不超过3句话（读者来这里找答案，不是看文章）
· 不在引言里开始讲任何知识点
· 不用"本文将介绍"的论文式写法

▌语言要求
风格：{audience['tone']}，极度简洁
句长：{audience['sentence']}
▌字数：40-70字（严格执行）

请直接输出引言正文，不需要标注"引言"标题。
"""


def get_qa_single(state: dict, section_type: str = "qa_1") -> str:
    """问答科普单题（qa_1, qa_2, qa_3）"""
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    meta = state.get("format_meta", {})
    qa_idx = meta.get("question_index") or (
        int(section_type.replace("qa_", "")) if section_type and "qa_" in section_type else 1
    )
    total = meta.get("total_questions", 3)
    tpl = load_task("qa_single")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            qa_idx=qa_idx,
            total=total,
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为问答科普文章撰写第 {qa_idx}/{total} 个问题与回答。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【问题设计】
问题类型分配：Q1最常见认知误区 / Q2最实用操作性问题 / Q3最让人担心的问题
问题的语气：用普通读者真实会问的口吻。
✅ "血糖高了，自己能不能先控制饮食，不去看医生？"
❌ "血糖升高时是否可以通过饮食干预代替药物治疗？"（学术表达）

【回答规范】
① 直接给核心答案（1-2句，先说结论）
② 简短解释原因（1-2句）
③ 实用建议或注意事项（1句）
每个Q&A总字数：70-150字

【禁止事项】
· 回答末尾不能以"去看医生"作为唯一答案
· 不能模糊回避（必须给出有信息量的回答）
· 不能出现具体药物名称或剂量

请直接输出，格式：**Q：[问题]** [回答内容]
"""


def get_qa_summary(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("qa_summary")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为问答科普文章撰写结尾总结。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
问答科普结尾 = 快速回顾 + 行动指引，不是重复问答内容。

▌内容结构
① 提炼句（≤20字）：从所有问答中提炼最重要的一个认知
② 行动建议（2-3条，列表格式）：每条必须动词开头+具体+不涉及具体药物
③ 就医提示（1句，必须包含）：什么情况下需要寻求专业帮助，要具体到症状
④ 延伸资源（可选）：如需了解更多，去哪里找可靠信息

▌禁止事项
· 不重复问答中已经详细说过的内容
· 不用"综上所述""总而言之"等套话开头
· 不出现"感谢阅读"

▌语言要求
风格：{audience['tone']}，清晰有力
句长：{audience['sentence']}
▌字数：100-170字

请直接输出总结正文，可以有小标题（不用"总结"这个词）。
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
    return f"""请为以下医学科普文章撰写健康小结（结尾部分）。

【文章信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【小结写作规范】

▌结构要求（按顺序）

① 核心要点总结（不是简单重复，是升华）
   - 用 2-3 句话提炼全文最重要的 1-2 个认知
   - 语言比正文更有力度，是读者最后记住的话

② 行动清单（最重要的部分）
   - 给出 2-3 条具体可操作的健康建议
   - 格式：简短动词开头（检查、减少、咨询、记录……）
   - 必须具体：❌ 「保持良好生活习惯」 ✅ 「每天走路30分钟，分3次完成也可以」
   - 注意：建议只涉及生活方式，不涉及用药

③ 就医提示（必须包含）
   - 明确说明什么情况下应该去看医生
   - 语气是关怀提醒，不是吓唬

④ 情感收束（1-2句）
   - 给读者信心和温暖
   - {platform_cta}

▌语言要求
风格：{audience['tone']}
句长：{audience['sentence']}
整体字数：150-250字

▌禁止事项
- 不用「总之」「综上所述」等套话开头
- 不重复引言的内容
- 不出现「感谢阅读」
- 健康建议不涉及具体药物

请直接输出小结内容，可以自行添加小标题（如「记住这几点」）。
"""


# 辟谣文
def get_debunk_intro(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("debunk_intro")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
        )
    return f"""请为辟谣文撰写引言。

【文章信息】
主题：{state.get('topic', '')}（关于此主题的常见医学误区）
目标读者：{audience['desc']}

【写作要求】
引言需要完成两件事：
① 建立共同经历：「很多人都会有这样的想法……」（不批评，而是理解）
② 预告价值：「今天我们来认真说清楚这几个误区」

语气原则：
- 不批判、不说教
- 像朋友帮你纠正一个小误解，而不是老师批评学生
- 让读者感到「原来我这样想是很正常的，但确实需要了解真相」

字数：80-130字
风格：{audience['tone']}
请直接输出引言内容。
"""


def get_debunk_myth(state: dict, section_type: str = "myth_1") -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    meta = state.get("format_meta", {})
    myth_num = meta.get("myth_number") or (
        int(section_type.replace("myth_", "")) if section_type and "myth_" in section_type else 1
    )
    total = meta.get("total_myths", 3)
    tpl = load_task("debunk_myth")
    if tpl:
        return tpl.format(
            myth_num=myth_num,
            total=total,
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
        )
    return f"""请撰写辟谣文的第 {myth_num}/{total} 条误区内容。

【文章信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【固定输出格式】（严格遵守，不得改变结构）

❌ 误区{myth_num}：[用目标读者的口吻陈述这个误区，像真实的人会说的话]

✅ 真相：[一句话直接给出正确认知，简洁有力]

📖 为什么是这样：
[2-4句话解释真相背后的科学原因，使用类比帮助理解]
[最后1句提醒：如何避免陷入这个误区，或者正确做法是什么]

【内容要求】
- 误区陈述：要真实，是读者真的会说的话，不要太学术
  ✅ 「血压高了多喝水就能降下来吧？」
  ❌ 「高血压患者认为增加饮水量可以稀释血液从而降低血压」

- 真相表述：直接、确定、有力，但不绝对化
  ✅ 「饮水量与血压没有直接关系，血压控制需要综合管理」
  ❌ 「血压绝对不会因为喝水而降低」（绝对化）

- 解释部分：用类比让人明白，不用图表数据（无 RAG 来源时用 [DATA:] 占位）

语气：{audience['tone']}
单条字数：120-200字
请直接输出本条误区的三段内容。
"""


def get_debunk_action(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("debunk_action")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
        )
    return f"""请为辟谣文撰写结尾行动建议部分。

【文章信息】
主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【写作要求】
经过前面的误区澄清，结尾需要给读者明确的行动方向：

① 一句话总结（核心认知升华）
   不是重复误区，而是给读者一个记忆锚点

② 正确做法清单（2-3条）
   - 具体可操作的建议
   - 不涉及具体药物或剂量

③ 就医信号提示
   「如果出现以下情况，请及时就医：……」

④ 鼓励性结尾（1句）
   让读者感到「了解真相让我更有掌控感」

字数：100-150字
风格：{audience['tone']}
请直接输出行动建议内容。
"""


# 科普故事
def get_story_opening(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("story_opening")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            specialty=state.get("specialty", ""),
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为医学科普故事撰写开篇。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
目标读者：{audience['desc']}
专科：{state.get('specialty', '')}

【开篇写作规范】

故事开篇需要在100-150字内完成：
① 建立叙事场景（时间/地点/人物，具体而生活化）
② 引入核心矛盾或困惑（与医学主题相关）
③ 吸引读者想知道「后来怎样了」

叙事原则：
- 用第三人称叙述，但要贴近人物的感受
- 场景要具体，不要抽象（「阳台上晒太阳」比「某个下午」好）
- 人物用化名，注明「（化名）」
- 开头不能是心理描写，要从场景或动作开始

语言风格：{audience['tone']}
句子长度：{audience['sentence']}
请直接输出故事开篇，不需要标题。
"""


def get_story_development(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("story_development")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为医学科普故事撰写发展部分（中段）。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
目标读者：{audience['desc']}

【发展部分写作规范】

发展段需要完成的任务（200-300字）：
① 故事推进：人物遭遇困境或寻求帮助的过程
② 知识融入：通过人物对话或医生解释，自然带出医学知识
   - 知识点不能突兀地「插入」，要从情节中生长出来
   - 医生说话要口语化，不能像教科书
   - 患者/主角的疑问要真实，像普通人会问的

③ 情感节奏：困惑→理解→释然的情绪变化

叙事技巧：
- 医学解释通过对话呈现，而不是旁白介绍
  ✅ 「张医生拿出一张图说：『你看，这就像……』」
  ❌ 「医学上，该疾病的发病机制为……」

风格：{audience['tone']}
句长：{audience['sentence']}
请直接输出故事发展内容。
"""


def get_story_climax(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("story_climax")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为医学科普故事撰写高潮/转折部分（第三节）。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【高潮节的三个条件（全部满足才算合格）】
① 情节上：有清晰的转变（从误解→理解，从困境→出路，从忽视→重视）
② 知识上：核心医学知识点在这里以最自然的方式出现
③ 情感上：读者有"原来如此"或"我理解了"的感受

▌触发事件（30-50字）：什么事情触发了主角的认知转变？触发必须自然，可以是医生的一句话/一次检查结果/一个意外发现/一次对话。

▌核心转折（50-80字）：主角理解了什么？医学知识通过"主角的领悟"自然传递，而不是作者直接讲解。
✅ 正确："王阿姨盯着那张血糖变化曲线，终于明白了：不是米饭害了她，是她吃饭的顺序……"
❌ 错误："医生向王阿姨介绍了进食顺序对血糖的影响机制，指出根据研究……"（作者直接讲知识，打破叙事感）

▌情绪落点（20-30字）：主角此刻的感受——不要戏剧化，要真实。

▌禁止事项
· 不在高潮节突然切换成科普口吻（"医学上，该疾病的机制为……"）
· 不让医生一次性倾倒所有知识（用对话层层递进）
· 不让主角的领悟凭空而来（必须有触发事件支撑）
· 不给慢性病做虚假治愈承诺

▌语言要求
风格：{audience['tone']}，叙事节奏在这里略微放慢
句长：{audience['sentence']}
视角：第三人称，贴近主角内心
▌字数：110-180字

请直接输出高潮/转折正文，不需要标注节标题。
"""


def get_story_resolution(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("story_resolution")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为医学科普故事撰写结局部分（第四节）。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
叙事收束，展示主角的改变，给读者希望和带走感。

▌状态改变（40-60字）：主角的处境或心态发生了什么变化？
✅ 正确："三个月后的复查，她的血糖终于进入了正常范围。医生说，后面主要靠自己管理，她说，她现在有把握了。"
❌ 错误："从此王阿姨过上了健康快乐的生活，再也不为血糖担心了。"（童话式，不真实）

▌留白收尾（1-2句）：好的故事结尾留有余韵，不把话说满。
✅ "那天离开诊室时，她给女儿发了一条消息：'妈学会了一件事。'"
❌ "通过这次经历，王阿姨深刻认识到了健康管理的重要性……"（说满了）

▌禁止事项
· 不在结局里插入新的知识点
· 不过度煽情（热泪盈眶/感恩戴德）
· 不做完美大团圆结局
· 不以悲剧结尾

▌语言要求
风格：{audience['tone']}，温暖，有余韵
句长：{audience['sentence']}
▌字数：80-130字

请直接输出结局正文，不需要标注节标题。
"""


def get_story_lesson(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("story_lesson")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请为医学科普故事撰写结尾和知识提炼。

【故事信息】
主题/医学知识点：{state.get('topic', '')}
目标读者：{audience['desc']}

【结尾写作规范】

结尾需要完成（150-200字）：
① 故事收束：人物状态改变，给出有温度的结局
   - 结局不必「完美」，但要给读者希望
   - 用细节收尾，不用大道理收尾

② 知识提炼（自然过渡，不生硬）：
   「（人物名）的经历让我们看到……」
   或直接过渡到「医生说，对于我们每个人来说……」

③ 行动提示（1-2条，轻量级）：
   不是清单，是融入叙述的建议

风格：温暖、有余韵，读完后让人感到有所获得
句长：{audience['sentence']}
请直接输出故事结尾。
"""


# 研究速读
def get_research_finding(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("research_finding")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
        )
    return f"""请将医学研究发现转化为大众可读的科普内容。

【内容信息】
研究主题：{state.get('topic', '')}
目标读者：{audience['desc']}

【研究速读写作规范】

研究速读需要回答读者最关心的三个问题：

**① 这个研究发现了什么？**（50-80字）
- 用最简单的语言说出核心发现
- 避免：「该研究采用随机对照实验……」
- 改为：「科学家们发现……」或「一项新研究表明……」
- 如果无 RAG 来源确认具体研究，用 [DATA: 描述研究发现]

**② 这对我意味着什么？**（80-120字）
- 翻译研究意义：这个发现对普通人的日常生活有什么影响
- 解释为什么这个发现重要
- 用类比帮助理解研究机制

**③ 我现在应该做什么（或不做什么）？**（60-100字）
- 实用的行动建议
- 注意：研究发现≠临床建议，需要明确说「这仍需要更多研究」或「应在医生指导下……」

【注意事项】
- 不夸大研究的意义（避免「颠覆性发现」等表述）
- 不简化研究的局限性（应提及「这项研究的样本量/时间/范围……」）
- 不把初步研究当定论（用「初步研究显示」而非「已证实」）

语气：{audience['tone']}
句长：{audience['sentence']}
总字数：200-300字
请直接输出研究速读内容。
"""


def get_research_background(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    specialty_ctx = state.get("specialty_context", "")
    specialty_context_line = f"\n学科背景：{specialty_ctx}" if specialty_ctx else ""
    tpl = load_task("research_background")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            audience_vocabulary=audience["vocabulary"],
            specialty_context_line=specialty_context_line,
        )
    return f"""请为医学研究速读文章撰写"研究背景"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科领域：{state.get('specialty', '')}
目标读者：{audience['desc']}
{f'学科背景：{specialty_ctx}' if specialty_ctx else ''}

【写作任务】
研究背景回答读者的第一个问题："这个研究是研究什么的？为什么要研究它？"

▌内容结构（严格按顺序）
① 现状痛点（40-60字）：描述这个领域目前存在什么问题或争议。
② 研究切入点（30-50字）：说明这项研究关注的具体问题。要具体：不说"研究了某某领域"，要说"研究了某某人群在某某条件下的某某结果"。
③ 为什么值得关注（20-40字）：一句话建立与读者的相关性，让他继续读下去。

▌正例与反例
✅ 正确："糖尿病是全球最常见的慢性病之一，但关于某些饮食模式对血糖的长期影响，学界至今仍存在争论。"
❌ 错误："近年来，随着医学科学的不断进步，越来越多的研究开始关注……"（套话开场，无实质信息）

▌禁止事项
· 不用"据研究/据报道"开头却无来源支撑
· 不编造具体样本量或研究机构名称（无RAG来源时用通用表述）
· 不在背景部分就开始说结论（结论留到发现部分）

▌语言要求
风格：{audience['tone']}  句长：{audience['sentence']}  词汇：{audience['vocabulary']}
▌字数：90-150字

请直接输出研究背景正文，不需要标注标题。
"""


def get_research_implication(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    audience_guide = {
        "public": "重点：这个发现是否改变了日常生活建议？读者现在需要做什么不同的事？避免：让读者感觉现在必须立刻改变什么。",
        "patient": "重点：这个发现是否影响患者的治疗选择或日常管理？是否值得和医生讨论？语气：给予希望，但不夸大。",
        "student": "重点：这个发现如何更新了对疾病机制的理解？与教材内容有何不同或补充？可以讨论方法学意义。",
        "professional": "重点：这个发现是否影响临床实践？现有指南建议是否需要重新审视？证据级别评估。",
        "children": "注意：研究速读不适合儿童受众。如果受众为儿童，请生成一段简单的'这个发现告诉我们……'总结，不需要讨论临床意义。",
    }.get(state.get("target_audience", "public"), "重点说明对读者日常生活的实际影响。")
    tpl = load_task("research_implication")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_guide=audience_guide,
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            audience_vocabulary=audience["vocabulary"],
        )
    return f"""请为医学研究速读文章撰写"这对你意味着什么"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
受众解读重点：{audience_guide}

【写作任务】
这一节是研究速读的价值核心——把研究结论翻译成读者能用的信息。

▌内容要求
① 直接说结论（不绕弯子）
✅ "简单说，如果你有高血压，早晨服药可能比晚上效果更好——但在改变用药习惯前，请先咨询你的主治医生。"
❌ "这项研究具有重要的理论价值和现实意义，值得广泛关注。"（完全没有说对读者意味着什么）

② 可操作的建议（如果有）：如果研究结论可以转化为具体行动，给出1-2条具体建议。如果尚早、不适合直接行动，明确说明："目前这项研究还处于初步阶段，不建议根据此结论改变现有的……"

③ 边界说明（1句）：研究结论适用于哪些人，哪些人不适用。点出核心局限。

▌严格禁止
· 夸大研究意义（"革命性发现""颠覆传统认知""重磅突破"）
· 给出涉及具体剂量的用药建议
· 把初步研究说成定论（须用"初步显示""研究提示"）
· 让读者感到恐慌或必须立刻行动

▌语言要求
风格：{audience['tone']}  句长：{audience['sentence']}  词汇：{audience['vocabulary']}
▌字数：90-150字

请直接输出正文，不需要标注节标题。
"""


def get_research_caution(state: dict) -> str:
    audience = AUDIENCE_PROFILES.get(state.get("target_audience", "public"), AUDIENCE_PROFILES["public"])
    tpl = load_task("research_caution")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            audience_tone=audience["tone"],
            audience_sentence=audience["sentence"],
            audience_vocabulary=audience["vocabulary"],
        )
    return f"""请为医学研究速读文章撰写"注意事项"部分。

【文章信息】
研究主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}

【写作任务】
帮助读者正确理解研究的边界，防止过度解读。这一节体现了科学传播的诚信。

▌内容结构
① 研究局限性（1-2句）：用通俗语言说明这项研究的主要局限。
   · 样本量小：✅ "这项研究只观察了XXX人，结论还需要更大规模的研究来验证"
   · 随访时间短：✅ "随访仅持续了X个月，长期效果尚不明确"
   · 研究人群特定：✅ "研究对象主要为XX人群，结论是否适用于其他群体仍需研究"
   · 观察性研究：✅ "这是观察性研究，只能说明'有关联'，不能证明'一个导致了另一个'"
   如无RAG来源支撑具体局限，使用通用表述："如同所有医学研究，这项研究也有其局限性，结论仍需更多研究验证。"

② 行动建议（1句，必须包含）：在不确定性下读者应该怎么做。
✅ "在相关指南更新之前，建议维持现有的医疗建议，如有疑问请咨询医生。"

▌禁止事项
· 不用学术腔描述局限性（读者看不懂）
· 不以恐吓式语气描述局限（"这个研究结论可能是错的！"）
· 不省略行动建议（读者需要知道在不确定下怎么做）

▌语言要求
风格：{audience['tone']}，这一节语气更谨慎、客观
句长：{audience['sentence']}
关键语气词：可能、初步、仍需、建议咨询医生
▌字数：60-100字

请直接输出注意事项正文，不需要标注节标题。
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
    platform_word_guide = PLATFORM_WORD_GUIDE.get(
        state.get("platform", "wechat"),
        "整体建议 800-1500 字",
    )
    tpl = load_task("outline")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            audience_desc=audience["desc"],
            platform=state.get("platform", "wechat"),
            platform_word_guide=platform_word_guide,
        )
    return f"""请为以下医学科普文章生成详细大纲。

【文章基本信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
目标读者：{audience['desc']}
目标平台：{state.get('platform', 'wechat')}（{platform_word_guide}）

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


# 动画分镜
def get_storyboard_planner(state: dict) -> str:
    tpl = load_task("storyboard_planner")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
        )
    return f"""请为医学科普动画撰写分镜规划方案。

【内容信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}

【规划要求】
① 总镜头数：建议 4-6 个
② 每镜时长：约 8-15 秒
③ 结构：开场吸引→知识点展开→转折/高潮→收尾升华
④ 每镜主题：为每个镜头拟定一句话主题（便于后续单镜撰写）

【输出格式】
请按以下格式输出分镜规划：

| 镜头 | 时长 | 主题 |
|------|------|------|
| 1 | 10s | [主题] |
| 2 | 12s | [主题] |
| ... | ... | ... |

每镜主题要具体、可视觉化，便于后续撰写画面描述与旁白。
"""


def get_storyboard_frame(state: dict, section_type: str = "frame_1") -> str:
    meta = state.get("format_meta", {})
    idx = meta.get("frame_index")
    if idx is None and section_type and section_type.startswith("frame_"):
        try:
            idx = int(section_type.replace("frame_", ""))
        except ValueError:
            idx = 1
    else:
        idx = idx or 1
    total = meta.get("total_frames", 6)
    duration = meta.get("duration", "10s")
    theme = meta.get("frame_theme", "")
    planner_items = meta.get("planner_items", [])
    if not theme and planner_items:
        item = next((p for p in planner_items if p.get("panel_index") == idx or p.get("frame_index") == idx or (isinstance(p, dict) and int(p.get("镜头", p.get("frame", 0))) == idx)), None)
        if not item and 0 < idx <= len(planner_items):
            item = planner_items[idx - 1]
        if item:
            theme = item.get("主题") or item.get("theme") or item.get("panel_theme") or item.get("frame_theme", "")
            if not duration or duration == "10s":
                duration = item.get("时长") or item.get("duration") or duration
    theme_line = f"本镜主题：{theme}" if theme else ""
    planner_overview = ""
    planner_json = meta.get("planner_json", {})
    if planner_json:
        import json as _json
        planner_overview = f"\n【分镜规划总览（必须遵循）】\n{_json.dumps(planner_json, ensure_ascii=False, indent=2)}\n"
    tpl = load_task("storyboard_frame")
    if tpl:
        return tpl.format(
            topic=state.get("topic", ""),
            specialty=state.get("specialty", ""),
            idx=idx,
            total=total,
            duration=duration,
            theme_line=theme_line,
        )
    return f"""请为医学科普动画撰写第 {idx}/{total} 个分镜。

【内容信息】
主题：{state.get('topic', '')}
专科：{state.get('specialty', '')}
本镜时长：{duration}
{theme_line}
{planner_overview}

【输出要求】
① 画面描述：本镜视觉呈现（场景、人物、动画效果），80字以内
② 旁白/台词：本镜配音文案，口语化，与画面同步
③ 节奏提示：如有重点信息需强调，可注明
- 必须严格遵循分镜规划中本镜的主题，不得偏离

【格式】
画面：[描述]
旁白：[文案]
节奏：[可选]

请直接输出本镜内容。
"""


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
  "data_placeholder": "[DATA:] 或空字符串（如本卡需要数据支撑但无来源）"
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
    return _poster_section_prompt(state, "data_highlight", "数据亮点", "≤20字，有RAG来源则写；否则用 [DATA:]")

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
- 数据来源有保障才用，没有来源用 [DATA:]

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
  示例："正常成人空腹血糖应该低于多少？"（数据来自 RAG 或 [DATA:]）

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
        "myth_intro": get_debunk_intro,
        "myth_1": get_debunk_myth,
        "myth_2": get_debunk_myth,
        "myth_3": get_debunk_myth,
        "action_guide": get_debunk_action,
    },
    "qa_article": {
        "qa_intro": get_qa_intro,
        "qa_1": lambda s: get_qa_single(s, "qa_1"),
        "qa_2": lambda s: get_qa_single(s, "qa_2"),
        "qa_3": lambda s: get_qa_single(s, "qa_3"),
        "qa_summary": get_qa_summary,
    },
    "story": {
        "opening": get_story_opening,
        "development": get_story_development,
        "climax": get_story_climax,
        "resolution": get_story_resolution,
        "lesson": get_story_lesson,
    },
    "research_read": {
        "background": get_research_background,
        "finding": get_research_finding,
        "implication": get_research_implication,
        "caution": get_research_caution,
    },
    "oral_script": {
        "hook": get_oral_hook,
        "body_1": get_oral_body,
        "body_2": get_oral_body,
        "body_3": get_oral_body,
        "summary": get_oral_summary,
        "cta": get_oral_cta,
    },
    "drama_script": {
        "scene_setup": get_drama_scene_setup,
        "scene_1": get_drama_dialogue,
        "scene_2": get_drama_dialogue,
        "scene_3": get_drama_dialogue,
        "ending": get_drama_dialogue,
    },
    "storyboard": {
        "planner": get_storyboard_planner,
        "frame_1": get_storyboard_frame,
        "frame_2": get_storyboard_frame,
        "frame_3": get_storyboard_frame,
        "frame_4": get_storyboard_frame,
        "frame_5": get_storyboard_frame,
        "frame_6": get_storyboard_frame,
    },
    "audio_script": {
        "opening": get_audio_opening,
        "topic_intro": get_audio_topic_intro,
        "deep_dive": get_audio_deep_dive,
        "extension": get_audio_extension,
        "closing": get_audio_closing,
    },
    "card_series": {
        "card_1": get_card_content,
        "card_2": get_card_content,
        "card_3": get_card_content,
        "card_4": get_card_content,
        "card_5": get_card_content,
    },
    "picture_book": {
        "planner": get_picture_book_planner,
        "page_1": get_picture_book_page,
        "page_2": get_picture_book_page,
        "page_3": get_picture_book_page,
        "page_4": get_picture_book_page,
        "page_5": get_picture_book_page,
    },
    "poster": {
        "headline": get_poster_headline,
        "core_message": get_poster_core_message,
        "data_points": get_poster_data_points,
        "cta": get_poster_cta,
        "visual_desc": get_poster_visual_desc,
    },
    "long_image": {
        "planner": get_long_image_planner,
        "cover": get_long_image_cover,
        "section_1": lambda s: get_long_image_section({**s, "format_meta": {**s.get("format_meta", {}), "section_index": 1, "section_type": "knowledge"}}, "section_1"),
        "section_2": lambda s: get_long_image_section({**s, "format_meta": {**s.get("format_meta", {}), "section_index": 2, "section_type": "knowledge"}}, "section_2"),
        "section_3": lambda s: get_long_image_section({**s, "format_meta": {**s.get("format_meta", {}), "section_index": 3, "section_type": "knowledge"}}, "section_3"),
        "footer": get_long_image_footer,
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
}


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

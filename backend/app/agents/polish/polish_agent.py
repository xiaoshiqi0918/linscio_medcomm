"""润色与适配 Agent - 通俗化润色、平台适配"""
from app.agents.base import BaseAgent
from app.agents.prompts.audiences import AUDIENCE_PROFILES
from app.agents.prompts.loader import load_polish


class LanguagePolishAgent(BaseAgent):
    """通俗化润色 Agent，输出 Track Changes 格式 JSON"""

    module = "polish"

    def get_base_prompt(self, state: dict) -> str:
        target_audience = state.get("target_audience", "public")
        audience = AUDIENCE_PROFILES.get(
            target_audience, AUDIENCE_PROFILES["public"]
        )
        content = state.get("content", "")
        tpl = load_polish("language_polish")
        if tpl:
            return tpl.format(
                audience_desc=audience["desc"],
                audience_vocabulary=audience["vocabulary"],
                audience_sentence=audience["sentence"],
                audience_tone=audience["tone"],
                content=content,
            )
        return _default_language_polish(audience, content)


def _default_language_polish(audience: dict, content: str) -> str:
    return f"""请对以下医学科普内容进行通俗化润色，使其更适合目标读者。

【润色目标】
目标读者：{audience['desc']}
词汇标准：{audience['vocabulary']}
句长标准：{audience['sentence']}
风格标准：{audience['tone']}

【润色任务】
请对原文进行通俗化改写，输出 Track Changes 格式（JSON数组）：

[
  {{
    "change_type": "replace",
    "original": "原文片段（≤50字）",
    "revised": "改写后的内容",
    "reason": "改写原因（≤20字，如：句子过长/术语未解释/语气生硬）"
  }},
  ...
]

【润色优先级（从高到低）】
① 专业术语未解释（最高优先级）
   原文："患者出现胰岛素抵抗"
   改写："患者身体对胰岛素越来越不敏感（医学上叫胰岛素抵抗）"

② 句子过长（超过受众标准）
   原文："长句需要拆分"
   改写：拆分为两个短句

③ 被动语态/书面语
   原文："可以进行……处理"
   改写："可以……"

④ 绝对化表述（必须修改）
   检查并修改所有违反防编造规则的表述

⑤ 语气调整
   根据受众风格标准调整整体语气

【注意事项】
- 保持医学内容的准确性，不改变医学事实
- 只修改真正需要改的地方，不过度润色
- 每处修改要说明原因

【原文】
{content}

请直接输出 JSON 数组，不要有任何其他文字。如无需修改，返回 []。
"""


PLATFORM_SPECS = {
    "wechat": {
        "word_range": (800, 2000),
        "format": "小标题（##）分段，段落+列表混合，图片穿插",
        "tone_adjust": "可以更口语化，允许适当感情色彩",
        "special": '适合在段落间加「小结」或「划重点」的框框',
    },
    "xiaohongshu": {
        "word_range": (300, 800),
        "format": "短段落为主（每段2-4句），可适当使用emoji（不超过每段1个）",
        "tone_adjust": "更个人化、分享感强，像朋友在分享经验",
        "special": "开头第一句必须非常抓人，结尾引导收藏/评论",
    },
    "douyin": {
        "word_range": (200, 400),
        "format": "纯段落，每段1-2句，像在说话",
        "tone_adjust": "最口语化，节奏最快，每隔几句要有一个钩子",
        "special": "第一句即核心价值，结尾强行动号召",
    },
    "bilibili": {
        "word_range": (800, 2000),
        "format": "详细段落，允许展开细节，结构清晰",
        "tone_adjust": "可以更深度，受众接受度高，允许一定专业性",
        "special": "可加「番外」或「延伸阅读」部分",
    },
    "journal": {
        "word_range": (1500, 3000),
        "format": "段落为主，减少列表，略正式",
        "tone_adjust": "保持通俗但稍正式，语言更严谨",
        "special": "可以有参考来源说明",
    },
    "offline": {
        "word_range": (800, 1500),
        "format": "段落为主，适合印刷阅读的排版节奏",
        "tone_adjust": "温暖亲切，像医院的健康宣教材料",
        "special": "结尾加医院/科室联系方式占位符",
    },
    "universal": {
        "word_range": (600, 1200),
        "format": "通用格式",
        "tone_adjust": "通用语气",
        "special": "无特殊要求",
    },
}


class PlatformAdaptAgent(BaseAgent):
    """平台适配 Agent，输出适配后的完整内容 JSON"""

    module = "polish"

    def get_base_prompt(self, state: dict) -> str:
        platform = state.get("platform", "universal")
        spec = PLATFORM_SPECS.get(
            platform,
            PLATFORM_SPECS["universal"],
        )
        lo, hi = spec["word_range"]
        content = state.get("content", "")
        tpl = load_polish("platform_adapt")
        if tpl:
            return tpl.format(
                platform=platform,
                word_lo=lo,
                word_hi=hi,
                format=spec["format"],
                tone_adjust=spec["tone_adjust"],
                special=spec["special"],
                content=content,
            )
        return _default_platform_adapt(platform, spec, content)


def _default_platform_adapt(platform: str, spec: dict, content: str) -> str:
    lo, hi = spec["word_range"]
    return f"""请将以下医学科普内容适配到 {platform} 平台的格式和风格。

【平台规格】
字数范围：{lo}-{hi}字
格式要求：{spec['format']}
语气调整：{spec['tone_adjust']}
特殊要求：{spec['special']}

【适配输出格式（JSON）】

{{
  "adapted_content": "适配后的完整内容（Markdown格式）",
  "word_count": 实际字数,
  "changes_summary": "主要改动说明（≤50字）",
  "platform_tips": ["针对该平台的额外建议1", "建议2"]
}}

【适配原则】
- 保持医学内容的准确性，不改变医学事实
- 格式适配不等于内容删减（除非原文超出字数上限太多）
- 风格调整要自然，不留"硬改"的痕迹

【原文】
{content}

请直接输出 JSON，不要有任何其他文字。
"""


# ─── v2.2 形式专属润色 Agent ────────────────────────────────────────

class ScriptPolishAgent(BaseAgent):
    """
    脚本类专属润色（v2.2）
    适用于：oral_script / drama_script / audio_script
    """

    module = "polish"

    def get_base_prompt(self, state: dict) -> str:
        content_format = state.get("content_format", "oral_script")
        target_audience = state.get("target_audience", "public")

        children_note = ""
        if target_audience == "children":
            children_note = (
                "【特别说明：儿童受众脚本润色】\n"
                "① 绝对禁止任何可能引起儿童恐惧的内容（最高优先级）\n"
                "② 每句≤10字（比普通口播更短）\n"
                "③ 语气活泼有趣，像讲故事\n"
                "④ 用儿童熟悉的比喻替换所有医学表达\n\n"
            )

        format_specific = {
            "oral_script": {
                "priority": "口语化 > 信息密度 > 文字美感",
                "rules": [
                    "每句≤15字，超过15字必须拆分（不能只是加逗号）",
                    "删除所有书面连接词：此外、然而、综上所述、值得注意的是、首先/其次/最后",
                    "将被动语态改为主动语态：'已被证明'→'研究证明'；'需要注意的是'→'注意'",
                    "加入口语节奏词（适量，每段≤1个）：你知道吗、说真的、划重点",
                    "检查时间戳是否合理：每30秒约90字（3字/秒）",
                ],
                "positive": "✅ 润色前：'血糖升高主要是由于胰岛素分泌不足或细胞对胰岛素不敏感导致的。'\n✅ 润色后：'血糖升高，根本原因只有一个——胰岛素出了问题。/要么分泌不够，要么细胞不买账了。'",
                "negative": "❌ 错误润色：'血糖升高，主要是因为胰岛素分泌不足或细胞对其不敏感。'（只改了开头，句子仍然太长，书面语'对其'仍在）",
                "forbidden": "不要因为追求优美而让句子变长；不要把'划重点'等语气词用超过1次/段",
            },
            "drama_script": {
                "priority": "对话真实感 > 信息传递 > 戏剧张力",
                "rules": [
                    "每句台词≤20字，超出必须分句或拆成两轮对话",
                    "检查每个角色是否有辨识度（医生和患者说话方式应该明显不同）",
                    "添加括号内的动作指示：（皱眉看报告）（笑着解释）（拿出一张图）",
                    "医生台词：专业但口语，不用'根据医学研究表明'这类表达",
                    "患者台词：有情绪（担心/疑惑/不配合），不是完美配合的模板患者",
                ],
                "positive": "✅ 润色前：（患者）'请问医生，我这个血糖值是否需要立即用药？'\n✅ 润色后：（患者）（皱眉看报告）'这个数字……要吃药了吗？'",
                "negative": "❌ 台词仍然太礼貌：'您好医生，请问我的血糖需要注意什么？'（真实患者在紧张时不会这么说话）",
                "forbidden": "不要让患者说出学术化的问题；不要让医生像在背课件",
            },
            "audio_script": {
                "priority": "听觉节奏 > 信息深度 > 口语化",
                "rules": [
                    "每2-3分钟插入一个路标：'好，我们刚才说了……，接下来……'",
                    "重要信息重复两遍（播客听众可能在开车，无法回听）",
                    "用语言制造画面感：'想象你面前有一条河……'（替代图表说明）",
                    "适当加停顿标记（…）给主持人留呼吸空间",
                    "每段不超过200字，每段结束前给一个小结",
                ],
                "positive": "✅ 润色前：'接下来介绍第三个知识点，关于运动对血糖的影响。'\n✅ 润色后：'好，刚才我们说完了进食顺序。……（停顿）那问题来了——除了吃饭，运动怎么帮你控血糖？这就是接下来要聊的。'",
                "negative": "❌ 路标过于生硬：'第三点，运动。运动对血糖的影响如下……'（像PPT切换，不像播客说话）",
                "forbidden": "不要让脚本读起来像文章；路标不要用'第一/第二/第三'列举",
            },
        }.get(
            content_format,
            {"priority": "口语化 > 其他", "rules": ["按口播脚本标准润色"], "positive": "", "negative": "", "forbidden": "避免书面语"},
        )

        rules_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(format_specific["rules"]))
        return f"""{children_note}请对以下{content_format}脚本进行专项润色。

【脚本内容】
{{content}}

【润色优先级】
{format_specific['priority']}

【逐条检查规则（每条都要检查）】
{rules_text}

【质量示范】
{format_specific['positive']}
{format_specific['negative']}

【绝对禁止】
{format_specific['forbidden']}
医学安全不降级：不能删除就医提示，不能把"可能"改成"一定"

【输出格式（Track Changes JSON数组，每次最多输出15条修改）】
[
  {{"change_type": "replace | delete | insert", "original": "原文片段（≤60字）", "revised": "改写后内容（delete时为空字符串）", "rule_ref": "对应上方规则编号", "reason": "改写原因（≤20字）"}}
]

注意：最多输出15条修改记录，只改真正需要改的地方。

请直接输出JSON数组。
"""


class VisualPolishAgent(BaseAgent):
    """
    图示类专属润色（v2.2）
    适用于：comic_strip / card_series / picture_book / poster
    """

    module = "polish"

    def get_base_prompt(self, state: dict) -> str:
        content_format = state.get("content_format", "comic_strip")

        format_specific = {
            "comic_strip": {
                "char_limits": "对白≤30字（理想≤20字），旁白≤20字",
                "image_desc_rules": [
                    "scene_desc 必须是英文，30-50词",
                    "必须包含：主体（who）+ 动作（doing）+ 背景（where）+ 风格（style）",
                    "删除中文内容，若有则翻译为英文",
                    "补充风格标注：flat design / cartoon / medical illustration style",
                ],
                "content_rules": [
                    "对白要像真实对话，不是知识点搬运",
                    "每格只传递一个信息，过多则建议拆分",
                    "检查格间是否有故事连贯性（人物/场景是否一致）",
                ],
                "positive": "✅ 润色前 scene_desc：'一个女人在厨房看血糖仪'\n✅ 润色后 scene_desc：'A middle-aged woman in pajamas holding a blood glucose meter with a confused expression, sitting at a kitchen table, warm morning light, clean flat illustration style, Chinese home setting'",
                "negative": "❌ 润色后仍为中文 scene_desc：'中年女性拿着血糖仪，在厨房，表情困惑'（必须改为英文才能送入图像生成）",
            },
            "card_series": {
                "char_limits": "headline≤15字，body_text 80-120字，key_takeaway≤20字",
                "image_desc_rules": [
                    "illustration_desc 必须是英文，20-40词",
                    "风格标注：flat design medical illustration, bright colors, white background",
                    "描述的画面要与卡片内容高度匹配",
                ],
                "content_rules": [
                    "headline 要能单独成立（不看正文也能明白主题）",
                    "key_takeaway 是行动指引，不是正文摘要",
                    "删除重复信息（headline 和 key_takeaway 不应该说同一件事）",
                    "一张卡只讲一件事，发现多个知识点时建议拆分",
                ],
                "positive": "✅ 润色前 key_takeaway：'血压正常值是120/80以下'\n✅ 润色后 key_takeaway：'早晨起床后立刻量血压，最准'（从知识摘要改为行动指引）",
                "negative": "❌ headline 和 key_takeaway 重复",
            },
            "picture_book": {
                "char_limits": "page_text 6-20字，一句话，一件事",
                "image_desc_rules": [
                    "illustration_desc 必须是英文，30-50词",
                    "风格（必须包含）：children's picture book illustration, warm colors, cute, simple",
                    "安全要求（必须包含）：no scary elements, no needles, no blood",
                    "描述要具体到动作和表情，不能模糊",
                ],
                "content_rules": [
                    "page_text 只有一件事（不允许并且/但是/因为）",
                    "动词开头更生动：'小红细胞跳进血管里！'",
                    "检查全书是否有故事弧线（不是知识点罗列）",
                ],
                "positive": "✅ 润色前 page_text：'白细胞能够识别并消灭入侵人体的病原体'\n✅ 润色后 page_text：'小白细胞发现了坏蛋！'\n✅ 润色前 illustration_desc：'白细胞战斗'\n✅ 润色后 illustration_desc：'A cheerful white blood cell character waving its arms excitedly, chasing a small silly-looking germ villain, bright primary colors, children's picture book style, no scary elements'",
                "negative": "❌ page_text 太长且有从句：'当白细胞发现细菌时，它会立刻冲上去把细菌消灭掉。'（'当……时'从句让6岁儿童很难读）",
            },
            "poster": {
                "char_limits": "main_title≤10字，sub_title≤20字，key_point≤15字/条",
                "image_desc_rules": [
                    "main_visual_desc 必须是英文，30-50词",
                    "风格：professional health poster style, clean layout, readable",
                ],
                "content_rules": [
                    "每个 key_point 以动词开头，具体可操作",
                    "data_highlight 有来源才填，否则删除或改为非数字表述",
                    "call_to_action 具体到一个行动，不是口号",
                    "检查整张海报文案是否5秒内被路人理解",
                ],
                "positive": "✅ 润色前 call_to_action：'关注健康，关爱家人'\n✅ 润色后 call_to_action：'发现症状，挂内分泌科'（从口号改为具体行动）",
                "negative": "❌ key_point 无法执行：'保持良好的饮食结构'（应改为：'每餐主食不超过一个拳头'）",
            },
        }.get(
            content_format,
            {
                "char_limits": "极度精简，每个字都要有意义",
                "image_desc_rules": ["描述必须用英文，风格标注要明确"],
                "content_rules": ["极度精简，信息密度高"],
                "positive": "",
                "negative": "",
            },
        )

        img_rules = "\n".join(f"{i+1}. {r}" for i, r in enumerate(format_specific["image_desc_rules"]))
        cnt_rules = "\n".join(f"{i+1}. {r}" for i, r in enumerate(format_specific["content_rules"]))
        return f"""请对以下{content_format}内容进行专项润色。

【内容】
{{content}}

【图示类润色核心原则】
图示类内容配合图像呈现，文字为图像让路。
优先级：字数精简 > 画面可生成性（英文+具体）> 信息完整性 > 文字优美

【字数限制】
{format_specific['char_limits']}

【图像描述规则（image_desc_rules）】
{img_rules}

【内容规则】
{cnt_rules}

【质量示范】
{format_specific['positive']}
{format_specific['negative']}

【输出格式（Track Changes JSON数组，每次最多12条修改）】
[
  {{"change_type": "replace | delete | insert", "field": "修改的字段名", "panel_index": "条漫时标注第几格", "original": "原内容", "revised": "修改后内容", "reason": "修改原因（≤20字）"}}
]

注意：最多输出12条修改记录，优先处理图像描述的中→英翻译和字数超标问题。

请直接输出JSON数组。
"""


class HandbookPolishAgent(BaseAgent):
    """
    患者手册专属润色（v2.2）
    """

    module = "polish"

    def get_base_prompt(self, state: dict) -> str:
        return """请对以下患者教育手册内容进行专项润色。

【手册内容】
{content}

【患者手册润色优先级（严格按序执行）】

P1（必须修复，影响患者安全）：
  · 出现具体剂量（mg/ml/片/粒/次/天 + 数字）→ 删除或改为"遵医嘱"
  · 出现自行调药建议（减少剂量/停药/换药）→ 改为"请咨询医生"
  · 出现绝对化治疗承诺（完全治愈/彻底根治）→ 改为概率性表述

P2（建议修复，影响使用准确性）：
  · 【注意】【医嘱】【警告】三种标注混用或误用
  · 就医指征不具体（"身体不舒服去看医生"→"出现XX症状时就医"）

P3（建议优化，影响可读性）：
  · 行动建议不可操作（"保持良好习惯"→"每天走路30分钟"）
  · 术语首次出现未解释
  · 医学腔调浓（"如出现以下症状"→"如果你发现"）

【质量示范（P3优化）】
✅ 润色前：'患者应注意控制饮食，保持规律运动。'
✅ 润色后：'每餐主食不超过一个拳头大小；每天散步30分钟，分2次完成也可以。'

❌ 错误润色（不能因为语言优化而删除安全信息）：
原文：'出现低血糖症状（出汗/手抖/心跳加快）时，立即进食15g糖分。'
错误润色后：'感觉不舒服时，可以吃点东西。'（原文提供了具体指导，润色后变得模糊，降低了安全性）

【输出格式（JSON）】
{{
  "changes": [
    {{"change_type": "replace | delete | insert", "priority": "P1|P2|P3", "original": "原文片段（≤80字）", "revised": "修改后内容", "reason": "具体原因（≤25字）"}}
  ],
  "overall_risk_level": "safe|caution|high_risk",
  "p1_count": 0,
  "p2_count": 0,
  "estimated_word_count_after": 0
}}

【overall_risk_level 判断标准】
safe：P1 问题数为 0
caution：P1 问题数 1-2 个
high_risk：P1 问题数 3+ 个（建议人工全面审核）

【字数说明】
estimated_word_count_after：润色后预估字数（原字数 +/- 增删的字数）
患者手册单节标准字数：150-400字（润色后应在此范围内）

请直接输出JSON，优先处理 P1 问题。
"""

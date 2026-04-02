"""
写作质量自评提示词（v2.3）
FORMAT_SPECIFIC_CHECKS：各形式的专属检查项，供质量自评/人工评审使用
SOP_QUALITY_CHECKS：基于《医学科普文章写作与出版专家共识》的通用质量检查项
"""
from app.agents.prompts.loader import load_verification, load_writing_sop

_FORMAT_SPECIFIC_CHECKS = {
    "article": (
        "检查叙事类文章特有问题：\n"
        "· 是否以套话开头（'随着医学的发展''众所周知'等）？\n"
        "· 案例是否标注了（化名）？\n"
        "· 是否有'感谢阅读'等不必要的结束语？\n"
        "· 比喻是否科学准确？是否存在夸大疗效、简化机制、制造恐慌/绝望的比喻？（参考比喻三不原则：不夸大疗效、不简化机制、不制造恐慌或绝望）"
    ),
    "oral_script": (
        "检查口播脚本特有问题：\n"
        "· 每句是否≤15字？超出的句子需要拆分\n"
        "· 是否包含书面连接词（此外/然而/综上所述）？\n"
        "· 时间戳是否存在且格式正确（[MM:SS-MM:SS]）？"
    ),
    "comic_strip": (
        "检查条漫格特有问题：\n"
        "· JSON 格式是否合法？所有必填字段是否存在？\n"
        "· scene_desc 是否为英文？是否有足够的画面细节（主体+动作+背景）？\n"
        "· dialogue 是否≤30字？是否是真实对话而非知识搬运？"
    ),
    "picture_book": (
        "检查绘本特有问题：\n"
        "· page_text 是否≤20字且只有一件事？\n"
        "· illustration_desc 是否为英文？是否明确无恐惧元素？\n"
        "· 是否有任何可能引起儿童恐惧的内容（针头/血液/手术/痛苦）？"
    ),
    "patient_handbook": (
        "检查患者手册特有问题：\n"
        "· 是否包含具体剂量或自行调药建议（最高优先级）？\n"
        "· 警示框标注（【注意】【医嘱】【警告】）是否使用正确？\n"
        "· 每条日常建议是否具体可操作（有动词+量化标准）？"
    ),
    # v2.3 新增五种形式
    "long_image": (
        "检查竖版长图特有问题：\n"
        "· JSON 格式是否合法？所有必填字段（main_text / image_prompt / layout_notes）是否存在？\n"
        "· image_prompt 是否为英文？是否包含风格标注（flat design / color scheme）？\n"
        "· data 类型区块：是否有无来源支撑的具体数值？（违反防编造规则一）\n"
        "· main_text 字数是否符合区块类型要求（cover≤45字，knowledge 60-100字）？"
    ),
    "quiz_article": (
        "检查自测科普特有问题：\n"
        "· JSON 格式是否合法？correct_answer 是否在 options 范围内（A/B/C）？\n"
        "· explanation 是否温和（不批评选错的读者，语气'很多人选B，因为……'）？\n"
        "· key_learning 是否是行动指引（不是知识摘要）？\n"
        "· 正确答案是否真的正确（医学事实核查）？"
    ),
    "h5_outline": (
        "检查H5大纲特有问题：\n"
        "· JSON 格式是否合法？interaction 字段是否完整？\n"
        "· quiz 类型页面：feedback_correct/wrong 是否有解释原因（不只是'正确/错误'）？\n"
        "· reveal 类型页面：myth_text 是否是读者真实会相信的误区？\n"
        "· share_copy 是否有具体的传播动机（不是'欢迎关注'）？"
    ),
    "audio_script": (
        "检查播客脚本特有问题：\n"
        "· 每2-3分钟内是否有路标式小结（'好，我们刚才说了……'）？\n"
        "· 是否有需要视觉呈现才能理解的内容（图表/数据对比）？需要改为语言画面感表达\n"
        "· 重要信息是否重复了两遍（播客听众的记忆机制）？\n"
        "· 每段是否≤200字？"
    ),
    "storyboard": (
        "检查动画分镜特有问题：\n"
        "· 画面描述（Scene/Action/Style/Color）四要素是否完整？\n"
        "· 旁白字数是否与帧时长匹配（每秒约3字）？\n"
        "· 旁白是否是完整的句子（不是残缺的短语）？\n"
        "· 镜头类型是否明确（全景/中景/特写/推镜/拉镜）？"
    ),
}


def get_format_specific_checks(content_format: str) -> str:
    """获取指定形式的专属检查项"""
    return _FORMAT_SPECIFIC_CHECKS.get(
        content_format,
        "检查内容是否符合该形式的通用规范。"
    )


def get_analogy_check_reference() -> str:
    """
    获取多学科比喻反例库，供质量自评与人工评审参照。
    """
    return load_verification("analogy_anti_examples") or ""


SOP_QUALITY_CHECKS = (
    "【基于《医学科普文章写作与出版专家共识》的通用质量检查】\n"
    "· 科学性：内容是否基于可靠科学证据？是否存在将存疑证据表述为确定性结论的情况？\n"
    "· 证据分级：引用证据时是否使用了与证据级别匹配的程度副词（很可能/可能/可能性较小）？\n"
    "· 无损害性：是否包含具体用药剂量或个性化治疗方案？案例中是否泄露患者真实身份？\n"
    "· 通俗性：专业术语是否附有通俗解释？语言是否适合目标受众？\n"
    "· 原创性：是否存在内容同质化或套话开头（'随着医学的发展''众所周知'等）？\n"
    "· 公正性：是否包含商业推广或广告？个人观点是否明确标注？\n"
    "· 结构完整性：是否包含科普背景、主要内容、证据总结、作者建议等要素？\n"
    "· 视觉安全：是否存在可能引起非医学背景受众不适的视觉暴力描述？\n"
    "· 逻辑连贯：正文是否脉络清晰、逻辑连贯、各部分不重复？"
)


def get_sop_quality_checks() -> str:
    """获取基于专家共识的通用质量检查项"""
    return SOP_QUALITY_CHECKS

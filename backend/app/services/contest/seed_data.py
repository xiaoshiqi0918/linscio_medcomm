"""
参赛图文科普种子数据 — 冷启动所需的风格预设、负向词库、画意范例、赛制包

运行方式：python -m app.services.contest.seed_data
或在应用启动时通过 ensure_contest_seed_data() 自动执行
"""
from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.painting_intent import StylePreset, PaintingIntentExample, NegativeWordSet
from app.models.contest import ContestPack

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
#  6 个风格预设
# ══════════════════════════════════════════════════════════════

STYLE_PRESETS = [
    {
        "name": "infographic",
        "display_name": "信息图",
        "description": "数据可视化、流程图、对比图，适合呈现统计数据和关键指标",
        "medium_zh": "信息图表设计",
        "medium_en": "infographic design",
        "quality_tags_zh": "清晰，专业，简洁排版，数据可视化",
        "quality_tags_en": "clean, professional, clear layout, data visualization, vector style",
        "prompt_template_zh": {"style": "扁平化信息图风格，清晰的图标和数据展示"},
        "prompt_template_en": {"style": "flat infographic style, clean icons and data presentation"},
        "negative_words": {
            "zh": ["杂乱", "手绘风", "写实照片"],
            "en": ["cluttered", "hand-drawn", "photorealistic", "3d render"],
        },
        "default_composition": "全景",
        "default_lighting": "均匀照明",
        "default_color": "蓝白主色调",
    },
    {
        "name": "process_diagram",
        "display_name": "流程示意",
        "description": "步骤流程、操作指南、诊疗路径，适合说明操作顺序",
        "medium_zh": "流程示意图",
        "medium_en": "process diagram illustration",
        "quality_tags_zh": "步骤清晰，逻辑明确，专业医疗插画",
        "quality_tags_en": "clear steps, logical flow, professional medical illustration",
        "prompt_template_zh": {"style": "步骤式流程图风格，带有序号标注和箭头引导"},
        "prompt_template_en": {"style": "step-by-step process diagram, numbered annotations with arrow guides"},
        "negative_words": {
            "zh": ["抽象", "模糊", "无序"],
            "en": ["abstract", "blurry", "chaotic", "disorganized"],
        },
        "default_composition": "全景",
        "default_lighting": "均匀照明",
        "default_color": "清新色调",
    },
    {
        "name": "comic_narrative",
        "display_name": "轻漫画叙事",
        "description": "Q版人物、对话气泡、场景叙事，适合讲故事和情景还原",
        "medium_zh": "轻漫画插画",
        "medium_en": "light comic illustration",
        "quality_tags_zh": "可爱，温馨，Q版人物，清晰线条",
        "quality_tags_en": "cute, warm, chibi characters, clean linework, manga style",
        "prompt_template_zh": {"style": "轻松可爱的漫画风格，Q版人物造型"},
        "prompt_template_en": {"style": "cute comic style, chibi character design, warm colors"},
        "negative_words": {
            "zh": ["写实", "恐怖", "暴力", "血腥"],
            "en": ["realistic", "horror", "violence", "gore", "dark"],
        },
        "default_composition": "中景",
        "default_lighting": "明亮柔和",
        "default_color": "温暖色调",
    },
    {
        "name": "metaphor_scene",
        "display_name": "隐喻场景",
        "description": "用日常物品或自然场景隐喻医学概念，适合抽象概念可视化",
        "medium_zh": "概念隐喻插画",
        "medium_en": "conceptual metaphor illustration",
        "quality_tags_zh": "创意构思，寓意深刻，艺术性强",
        "quality_tags_en": "creative concept, meaningful metaphor, artistic, thought-provoking",
        "prompt_template_zh": {"style": "概念性隐喻插画风格，用生活场景比喻医学概念"},
        "prompt_template_en": {"style": "conceptual metaphor illustration, everyday objects representing medical concepts"},
        "negative_words": {
            "zh": ["直白", "无创意", "纯文字"],
            "en": ["literal", "plain", "text-only", "boring"],
        },
        "default_composition": "中景",
        "default_lighting": "柔和自然光",
        "default_color": "柔和色调",
    },
    {
        "name": "realistic_photo",
        "display_name": "写实摄影感",
        "description": "接近真实摄影的风格，适合展示真实医疗场景和人物",
        "medium_zh": "写实摄影风格插画",
        "medium_en": "photorealistic illustration",
        "quality_tags_zh": "高清，写实，自然光影，专业医疗场景",
        "quality_tags_en": "photorealistic, high detail, natural lighting, professional medical setting, 8k",
        "prompt_template_zh": {"style": "写实摄影风格，真实自然的医疗场景"},
        "prompt_template_en": {"style": "photorealistic style, natural medical setting, professional photography"},
        "negative_words": {
            "zh": ["卡通", "Q版", "夸张", "变形"],
            "en": ["cartoon", "chibi", "exaggerated", "deformed", "anime"],
        },
        "default_composition": "中景",
        "default_lighting": "自然光",
        "default_color": "真实色彩",
    },
    {
        "name": "flat_illustration",
        "display_name": "扁平插画",
        "description": "现代扁平设计风格，简洁几何形状，适合通用科普配图",
        "medium_zh": "扁平风格数字插画",
        "medium_en": "flat design digital illustration",
        "quality_tags_zh": "简洁，现代，扁平设计，色彩鲜明",
        "quality_tags_en": "clean, modern, flat design, vibrant colors, vector art",
        "prompt_template_zh": {"style": "现代扁平插画风格，简洁几何图形，鲜明配色"},
        "prompt_template_en": {"style": "modern flat illustration style, simple geometric shapes, vibrant color palette"},
        "negative_words": {
            "zh": ["复杂纹理", "写实", "3D渲染"],
            "en": ["complex textures", "photorealistic", "3d render", "detailed shading"],
        },
        "default_composition": "中景",
        "default_lighting": "柔和自然光",
        "default_color": "鲜明色调",
    },
]

# ══════════════════════════════════════════════════════════════
#  全局负向词库（4 个类别）
# ══════════════════════════════════════════════════════════════

NEGATIVE_WORD_SETS = [
    {
        "category": "compliance",
        "scope": "global",
        "words_zh": [
            "医务人员未戴口罩", "未规范着装", "未戴手套",
            "不符合诊疗规范", "违规操作", "不安全注射",
        ],
        "words_en": [
            "medical staff without mask", "improper medical attire", "no gloves",
            "non-compliant medical practice", "unsafe injection",
        ],
    },
    {
        "category": "aesthetic",
        "scope": "global",
        "words_zh": [
            "过于真实的伤口", "血液特写", "器官特写", "注射针头特写",
            "恐怖画面", "令人不适的画面",
        ],
        "words_en": [
            "realistic wound closeup", "blood closeup", "organ closeup",
            "needle closeup", "horror", "disturbing imagery", "gore",
        ],
    },
    {
        "category": "scientific",
        "scope": "global",
        "words_zh": [
            "错误解剖结构", "违反生理常识", "错误的人体比例",
            "不科学的医疗器械", "伪科学元素",
        ],
        "words_en": [
            "wrong anatomy", "incorrect physiology", "bad proportions",
            "unrealistic medical equipment", "pseudoscience elements",
        ],
    },
    {
        "category": "brand",
        "scope": "global",
        "words_zh": [
            "可识别药品包装", "医院logo", "医疗器械品牌标识",
            "商标", "广告元素",
        ],
        "words_en": [
            "identifiable drug packaging", "hospital logo", "medical device brand",
            "trademark", "advertising elements", "brand name",
        ],
    },
]

# ══════════════════════════════════════════════════════════════
#  选题级负向词（scope=topic，补充全局词库之外的领域禁忌）
# ══════════════════════════════════════════════════════════════

TOPIC_NEGATIVE_WORD_SETS = [
    {
        "category": "scientific",
        "scope": "topic",
        "topic_category": "hypertension",
        "words_zh": ["血管爆裂", "心脏爆炸", "头部充血特写", "恐怖血压计"],
        "words_en": ["bursting blood vessels", "exploding heart", "head congestion closeup", "scary sphygmomanometer"],
    },
    {
        "category": "scientific",
        "scope": "topic",
        "topic_category": "diabetes",
        "words_zh": ["血腥注射器", "截肢特写", "溃烂伤口", "恐怖胰岛素针头"],
        "words_en": ["bloody syringe", "amputation closeup", "festering wound", "scary insulin needle"],
    },
    {
        "category": "aesthetic",
        "scope": "topic",
        "topic_category": "child_vaccine",
        "words_zh": ["儿童哭闹特写", "暴力注射", "针头扎入皮肤特写", "恐惧表情特写"],
        "words_en": ["crying child closeup", "violent injection", "needle penetrating skin closeup", "terrified face closeup"],
    },
    {
        "category": "scientific",
        "scope": "topic",
        "topic_category": "maternal_health",
        "words_zh": ["分娩血腥场景", "剖腹产切口特写", "胎儿解剖图", "产后抑郁恐怖画面"],
        "words_en": ["bloody delivery scene", "c-section incision closeup", "fetal anatomy dissection", "postpartum depression horror"],
    },
    {
        "category": "aesthetic",
        "scope": "topic",
        "topic_category": "mental_health",
        "words_zh": ["自残画面", "自杀暗示", "精神病院铁栏", "束缚衣", "恐怖精神科场景"],
        "words_en": ["self-harm imagery", "suicide implication", "asylum bars", "straitjacket", "horror psychiatric scene"],
    },
    {
        "category": "scientific",
        "scope": "topic",
        "topic_category": "cancer_screening",
        "words_zh": ["肿瘤切除血腥特写", "恐怖癌细胞拟人", "化疗脱发恐怖场景", "末期患者痛苦特写"],
        "words_en": ["bloody tumor removal closeup", "horror cancer cell personification", "chemo hair loss horror", "terminal patient suffering closeup"],
    },
    {
        "category": "aesthetic",
        "scope": "topic",
        "topic_category": "first_aid",
        "words_zh": ["大量出血特写", "骨折畸形特写", "溺水窒息恐怖", "烧伤创面特写"],
        "words_en": ["massive bleeding closeup", "fracture deformity closeup", "drowning suffocation horror", "burn wound closeup"],
    },
    {
        "category": "compliance",
        "scope": "topic",
        "topic_category": "medication_safety",
        "words_zh": ["可识别药品名称", "处方药包装特写", "过量服药场景", "药物滥用暗示"],
        "words_en": ["identifiable drug name", "prescription drug packaging closeup", "overdose scene", "drug abuse implication"],
    },
    {
        "category": "aesthetic",
        "scope": "topic",
        "topic_category": "elderly_health",
        "words_zh": ["老年人跌倒血腥场景", "骨折畸形特写", "卧床不起痛苦特写", "衰老恐怖化"],
        "words_en": ["elderly fall bloody scene", "fracture deformity closeup", "bedridden suffering closeup", "aging horror"],
    },
    {
        "category": "aesthetic",
        "scope": "topic",
        "topic_category": "oral_eye_health",
        "words_zh": ["蛀牙烂牙恶心特写", "拔牙血腥特写", "眼球手术特写", "口腔溃疡恐怖"],
        "words_en": ["decayed teeth disgusting closeup", "bloody tooth extraction", "eyeball surgery closeup", "mouth ulcer horror"],
    },
]

# ══════════════════════════════════════════════════════════════
#  10 个选题的画意范例（每选题 × 3 条示例，覆盖不同风格）
# ══════════════════════════════════════════════════════════════

INTENT_EXAMPLES = [
    # ── 高血压管理 ──────────────────────────────────────────────
    # infographic
    {"topic": "hypertension", "style": "infographic", "intent": "高血压分级标准对照表，展示正常/临界/一级/二级血压值范围"},
    {"topic": "hypertension", "style": "infographic", "intent": "高血压常见并发症器官损害地图：心/脑/肾/眼底"},
    {"topic": "hypertension", "style": "infographic", "intent": "DASH 饮食法一日三餐搭配推荐信息图"},
    # process_diagram
    {"topic": "hypertension", "style": "process_diagram", "intent": "新发现高血压后的就医确诊流程：初筛→24h 动态→明确分级→治疗方案"},
    {"topic": "hypertension", "style": "process_diagram", "intent": "降压药物调整步骤：起始→2 周评估→达标维持→长期随访"},
    {"topic": "hypertension", "style": "process_diagram", "intent": "血压突然升高时的家庭应急处理流程"},
    # comic_narrative
    {"topic": "hypertension", "style": "comic_narrative", "intent": "老年人忘记吃降压药后血压飙升的漫画小故事"},
    {"topic": "hypertension", "style": "comic_narrative", "intent": "年轻上班族体检意外发现高血压后改变生活方式的四格漫画"},
    {"topic": "hypertension", "style": "comic_narrative", "intent": "爷爷用「管住嘴迈开腿」向孙子解释降压秘诀的温馨漫画"},
    # metaphor_scene
    {"topic": "hypertension", "style": "metaphor_scene", "intent": "血管比喻成水管，压力过大导致水管膨胀破裂的场景"},
    {"topic": "hypertension", "style": "metaphor_scene", "intent": "减盐如同给过载的气球慢慢放气的隐喻"},
    {"topic": "hypertension", "style": "metaphor_scene", "intent": "长期高血压像暗流侵蚀河堤，看似平静实则危险的概念画面"},
    # realistic_photo
    {"topic": "hypertension", "style": "realistic_photo", "intent": "老年患者晨起使用上臂式血压计规范自测的真实场景"},
    {"topic": "hypertension", "style": "realistic_photo", "intent": "社区家庭医生上门随访高血压患者并记录数据的场景"},
    {"topic": "hypertension", "style": "realistic_photo", "intent": "低盐健康餐桌实景：少油少盐的蔬菜杂粮搭配"},
    # flat_illustration
    {"topic": "hypertension", "style": "flat_illustration", "intent": "居家自测血压的正确姿势示意图，包含坐姿、袖带位置和注意事项"},
    {"topic": "hypertension", "style": "flat_illustration", "intent": "每日运动 30 分钟有助降压的扁平人物运动场景"},
    {"topic": "hypertension", "style": "flat_illustration", "intent": "高钠食物 vs 低钠替代食物的对比扁平插画"},

    # ── 糖尿病管理 ──────────────────────────────────────────────
    # infographic
    {"topic": "diabetes", "style": "infographic", "intent": "常见食物升糖指数（GI 值）对照表"},
    {"topic": "diabetes", "style": "infographic", "intent": "1 型 vs 2 型糖尿病核心差异对照信息图"},
    {"topic": "diabetes", "style": "infographic", "intent": "糖尿病并发症风险与对应筛查频次一览表"},
    # process_diagram
    {"topic": "diabetes", "style": "process_diagram", "intent": "糖尿病患者日常血糖监测流程：测量→记录→调整→复诊"},
    {"topic": "diabetes", "style": "process_diagram", "intent": "低血糖发作时的紧急处理三步法：识别→补糖→观察"},
    {"topic": "diabetes", "style": "process_diagram", "intent": "新确诊 2 型糖尿病患者的分阶段管理路径"},
    # comic_narrative
    {"topic": "diabetes", "style": "comic_narrative", "intent": "糖友聚餐时巧妙选择低 GI 菜品的幽默四格漫画"},
    {"topic": "diabetes", "style": "comic_narrative", "intent": "小朋友用超级英雄比喻胰岛素帮身体打败「糖怪兽」的漫画"},
    {"topic": "diabetes", "style": "comic_narrative", "intent": "老伯第一次学用血糖仪被孙女手把手教会的温馨漫画"},
    # metaphor_scene
    {"topic": "diabetes", "style": "metaphor_scene", "intent": "胰岛素像钥匙打开细胞大门让葡萄糖进入的隐喻场景"},
    {"topic": "diabetes", "style": "metaphor_scene", "intent": "血糖像过山车般波动，稳态饮食让曲线变平缓的概念画面"},
    {"topic": "diabetes", "style": "metaphor_scene", "intent": "糖化血红蛋白像年轮记录树木生长，记录过去 3 个月血糖的隐喻"},
    # realistic_photo
    {"topic": "diabetes", "style": "realistic_photo", "intent": "患者使用指尖血糖仪自测的规范操作真实特写"},
    {"topic": "diabetes", "style": "realistic_photo", "intent": "糖尿病友早餐：全麦面包、鸡蛋、蔬菜的健康搭配实景"},
    {"topic": "diabetes", "style": "realistic_photo", "intent": "社区健康讲座中护士讲解糖尿病足护理的现场场景"},
    # flat_illustration
    {"topic": "diabetes", "style": "flat_illustration", "intent": "餐盘法则：1/2 蔬菜 + 1/4 蛋白质 + 1/4 碳水的扁平配餐图"},
    {"topic": "diabetes", "style": "flat_illustration", "intent": "适合糖尿病患者的运动方式图标集：快走、游泳、骑行、瑜伽"},
    {"topic": "diabetes", "style": "flat_illustration", "intent": "胰岛素注射部位轮换示意扁平人体图"},

    # ── 儿童疫苗与常见传染病 ────────────────────────────────────
    # infographic
    {"topic": "child_vaccine", "style": "infographic", "intent": "0-6 岁儿童免疫规划疫苗接种时间表"},
    {"topic": "child_vaccine", "style": "infographic", "intent": "一类疫苗 vs 二类疫苗区别对比信息图"},
    {"topic": "child_vaccine", "style": "infographic", "intent": "常见儿童传染病（手足口/水痘/流感）传播途径与预防措施对照表"},
    # process_diagram
    {"topic": "child_vaccine", "style": "process_diagram", "intent": "儿童接种前后注意事项流程：预约→接种当日→留观 30 min→回家观察"},
    {"topic": "child_vaccine", "style": "process_diagram", "intent": "疫苗接种后不良反应的家庭观察与处理流程"},
    {"topic": "child_vaccine", "style": "process_diagram", "intent": "入学入托补种疫苗的办理流程"},
    # comic_narrative
    {"topic": "child_vaccine", "style": "comic_narrative", "intent": "小朋友勇敢打疫苗的温馨漫画场景，护士温柔鼓励"},
    {"topic": "child_vaccine", "style": "comic_narrative", "intent": "疫苗小战士在体内打败病毒大军的趣味漫画"},
    {"topic": "child_vaccine", "style": "comic_narrative", "intent": "妈妈带双胞胎打疫苗，一个哭一个笑的生活漫画"},
    # metaphor_scene
    {"topic": "child_vaccine", "style": "metaphor_scene", "intent": "疫苗像给身体穿上隐形铠甲抵御病毒箭雨的隐喻"},
    {"topic": "child_vaccine", "style": "metaphor_scene", "intent": "群体免疫如同伞阵保护中间的婴儿不被雨淋到的概念场景"},
    {"topic": "child_vaccine", "style": "metaphor_scene", "intent": "免疫记忆细胞像哨兵驻守城门，随时识别入侵者的隐喻"},
    # realistic_photo
    {"topic": "child_vaccine", "style": "realistic_photo", "intent": "社区卫生服务中心护士为幼儿接种疫苗的温馨真实场景"},
    {"topic": "child_vaccine", "style": "realistic_photo", "intent": "家长查看儿童预防接种证上盖章记录的特写"},
    {"topic": "child_vaccine", "style": "realistic_photo", "intent": "幼儿接种后在留观区安静玩耍、家长陪伴的场景"},
    # flat_illustration
    {"topic": "child_vaccine", "style": "flat_illustration", "intent": "疫苗保护孩子远离病毒的盾牌概念插画"},
    {"topic": "child_vaccine", "style": "flat_illustration", "intent": "不同疫苗对应预防的疾病图标配对扁平插画"},
    {"topic": "child_vaccine", "style": "flat_illustration", "intent": "正确洗手七步法的儿童版扁平示意图"},

    # ── 孕产期保健 ──────────────────────────────────────────────
    # infographic
    {"topic": "maternal_health", "style": "infographic", "intent": "孕期体重增长推荐范围（按 BMI 分层）信息图"},
    {"topic": "maternal_health", "style": "infographic", "intent": "孕期关键营养素（叶酸/铁/钙/DHA）每日推荐量对照表"},
    {"topic": "maternal_health", "style": "infographic", "intent": "产后 42 天检查项目清单信息图"},
    # process_diagram
    {"topic": "maternal_health", "style": "process_diagram", "intent": "孕期产检时间线：每个阶段的重点检查项目"},
    {"topic": "maternal_health", "style": "process_diagram", "intent": "自然分娩产程三阶段示意：宫口扩张→胎儿娩出→胎盘娩出"},
    {"topic": "maternal_health", "style": "process_diagram", "intent": "母乳喂养建立流程：早接触→早吸吮→按需哺乳→乳量评估"},
    # comic_narrative
    {"topic": "maternal_health", "style": "comic_narrative", "intent": "准妈妈在医生指导下科学补充叶酸的温馨场景"},
    {"topic": "maternal_health", "style": "comic_narrative", "intent": "准爸爸陪产时手忙脚乱又温馨感动的四格漫画"},
    {"topic": "maternal_health", "style": "comic_narrative", "intent": "新手妈妈半夜喂奶又累又幸福的温馨漫画"},
    # metaphor_scene
    {"topic": "maternal_health", "style": "metaphor_scene", "intent": "子宫像安全温暖的港湾保护胎儿成长的隐喻场景"},
    {"topic": "maternal_health", "style": "metaphor_scene", "intent": "脐带像生命之绳传递营养和氧气的概念画面"},
    {"topic": "maternal_health", "style": "metaphor_scene", "intent": "母乳像定制配方不断适应宝宝需求的自然隐喻"},
    # realistic_photo
    {"topic": "maternal_health", "style": "realistic_photo", "intent": "孕妇在产科门诊做常规超声检查的温馨场景"},
    {"topic": "maternal_health", "style": "realistic_photo", "intent": "产后妈妈在病房进行母婴肌肤接触的真实温馨画面"},
    {"topic": "maternal_health", "style": "realistic_photo", "intent": "孕期瑜伽课堂，孕妇在专业指导下做安全伸展的场景"},
    # flat_illustration
    {"topic": "maternal_health", "style": "flat_illustration", "intent": "孕期均衡营养金字塔，标注各阶段重点营养素"},
    {"topic": "maternal_health", "style": "flat_illustration", "intent": "待产包必备物品清单扁平图标分类插画"},
    {"topic": "maternal_health", "style": "flat_illustration", "intent": "新生儿护理要点扁平图解：脐带护理、沐浴、抚触"},

    # ── 心理健康 ────────────────────────────────────────────────
    # infographic
    {"topic": "mental_health", "style": "infographic", "intent": "抑郁症的常见信号和寻求帮助的途径信息图"},
    {"topic": "mental_health", "style": "infographic", "intent": "焦虑自评量表（GAD-7）使用指南信息图"},
    {"topic": "mental_health", "style": "infographic", "intent": "睡眠卫生十条准则信息图"},
    # process_diagram
    {"topic": "mental_health", "style": "process_diagram", "intent": "情绪危机干预流程：识别→倾听→评估→转介→随访"},
    {"topic": "mental_health", "style": "process_diagram", "intent": "渐进式肌肉放松训练步骤：从脚到头逐步放松的操作流程"},
    {"topic": "mental_health", "style": "process_diagram", "intent": "失眠认知行为治疗（CBT-I）四周改善方案流程"},
    # comic_narrative
    {"topic": "mental_health", "style": "comic_narrative", "intent": "打工人用正念呼吸法化解开会焦虑的趣味四格漫画"},
    {"topic": "mental_health", "style": "comic_narrative", "intent": "小动物拟人化表现「向朋友倾诉后如释重负」的温馨漫画"},
    {"topic": "mental_health", "style": "comic_narrative", "intent": "学生考前焦虑，老师引导做深呼吸放松的校园漫画"},
    # metaphor_scene
    {"topic": "mental_health", "style": "metaphor_scene", "intent": "焦虑像一团乌云笼罩在头顶，阳光逐渐穿透乌云的隐喻"},
    {"topic": "mental_health", "style": "metaphor_scene", "intent": "抑郁像身处深水中，心理咨询如同伸出的救生圈的场景"},
    {"topic": "mental_health", "style": "metaphor_scene", "intent": "情绪如同天气变化，接纳「阴天」也是自我关怀的概念画面"},
    # realistic_photo
    {"topic": "mental_health", "style": "realistic_photo", "intent": "心理咨询室温馨环境中来访者与咨询师对话的场景"},
    {"topic": "mental_health", "style": "realistic_photo", "intent": "清晨公园里中年人独自慢跑缓解压力的真实场景"},
    {"topic": "mental_health", "style": "realistic_photo", "intent": "年轻人戴耳机闭眼冥想，周围光线柔和的放松场景"},
    # flat_illustration
    {"topic": "mental_health", "style": "flat_illustration", "intent": "五种简单的正念放松技巧示意图"},
    {"topic": "mental_health", "style": "flat_illustration", "intent": "情绪温度计：从绿到红标注不同情绪强度的扁平图解"},
    {"topic": "mental_health", "style": "flat_illustration", "intent": "健康社交网络支持系统的扁平人物关系图"},

    # ── 肿瘤早筛 ────────────────────────────────────────────────
    # infographic
    {"topic": "cancer_screening", "style": "infographic", "intent": "不同年龄段推荐的癌症筛查项目对照表"},
    {"topic": "cancer_screening", "style": "infographic", "intent": "中国高发癌种（肺/胃/肝/结直肠/乳腺）早期信号一览表"},
    {"topic": "cancer_screening", "style": "infographic", "intent": "HPV 疫苗接种年龄与剂次推荐信息图"},
    # process_diagram
    {"topic": "cancer_screening", "style": "process_diagram", "intent": "发现异常→就医→检查→确诊→治疗的标准流程"},
    {"topic": "cancer_screening", "style": "process_diagram", "intent": "肠镜筛查全流程：预约→肠道准备→检查→结果解读"},
    {"topic": "cancer_screening", "style": "process_diagram", "intent": "乳腺自检三步法操作流程图解"},
    # comic_narrative
    {"topic": "cancer_screening", "style": "comic_narrative", "intent": "大叔犹豫要不要做肠镜，医生幽默打消顾虑的漫画"},
    {"topic": "cancer_screening", "style": "comic_narrative", "intent": "闺蜜互相提醒按时做两癌筛查的温馨日常漫画"},
    {"topic": "cancer_screening", "style": "comic_narrative", "intent": "体检查出结节后从恐慌到理性就医的心路历程漫画"},
    # metaphor_scene
    {"topic": "cancer_screening", "style": "metaphor_scene", "intent": "早筛如同在暴风雨来前修补屋顶，防患于未然的隐喻"},
    {"topic": "cancer_screening", "style": "metaphor_scene", "intent": "癌细胞像杂草，早期发现如同刚冒芽就拔除的概念场景"},
    {"topic": "cancer_screening", "style": "metaphor_scene", "intent": "定期筛查像安全巡检员按时检查管道，守护身体运行的隐喻"},
    # realistic_photo
    {"topic": "cancer_screening", "style": "realistic_photo", "intent": "女性在医院乳腺超声检查室接受规范检查的场景"},
    {"topic": "cancer_screening", "style": "realistic_photo", "intent": "体检中心受检者有序排队等候抽血筛查的真实场景"},
    {"topic": "cancer_screening", "style": "realistic_photo", "intent": "医生在诊室向患者解读筛查报告并制定随访计划的场景"},
    # flat_illustration
    {"topic": "cancer_screening", "style": "flat_illustration", "intent": "定期体检是发现早期癌症最有效手段的概念插画"},
    {"topic": "cancer_screening", "style": "flat_illustration", "intent": "五大高发癌种对应推荐筛查手段的图标配对扁平图"},
    {"topic": "cancer_screening", "style": "flat_illustration", "intent": "防癌生活方式五要素扁平图解：戒烟、限酒、运动、膳食、筛查"},

    # ── 急救常识 ────────────────────────────────────────────────
    # infographic
    {"topic": "first_aid", "style": "infographic", "intent": "中风识别口诀「FAST」对应的四个快速判断动作"},
    {"topic": "first_aid", "style": "infographic", "intent": "家庭常见急救场景（烫伤/割伤/鼻出血）处理要点对照表"},
    {"topic": "first_aid", "style": "infographic", "intent": "AED 使用步骤与公共场所 AED 分布提示信息图"},
    # process_diagram
    {"topic": "first_aid", "style": "process_diagram", "intent": "心肺复苏（CPR）标准操作步骤：判断→呼救→按压→通气"},
    {"topic": "first_aid", "style": "process_diagram", "intent": "气道异物梗阻（海姆立克法）操作流程：成人 vs 婴儿"},
    {"topic": "first_aid", "style": "process_diagram", "intent": "溺水急救流程：脱离水面→判断意识→CPR→等待 120"},
    # comic_narrative
    {"topic": "first_aid", "style": "comic_narrative", "intent": "路人发现有人噎食后正确执行海姆立克急救法的场景"},
    {"topic": "first_aid", "style": "comic_narrative", "intent": "小学生在课间发现同学流鼻血正确处理的校园漫画"},
    {"topic": "first_aid", "style": "comic_narrative", "intent": "超市里顾客突然晕倒，热心市民取 AED 施救的正能量漫画"},
    # metaphor_scene
    {"topic": "first_aid", "style": "metaphor_scene", "intent": "黄金四分钟像沙漏中流逝的沙粒，每一秒都在决定生死的隐喻"},
    {"topic": "first_aid", "style": "metaphor_scene", "intent": "急救技能像灭火器，平时不用但关键时刻能救命的概念场景"},
    {"topic": "first_aid", "style": "metaphor_scene", "intent": "CPR 按压如同为停摆的时钟重新上发条的隐喻画面"},
    # realistic_photo
    {"topic": "first_aid", "style": "realistic_photo", "intent": "急救培训课上学员在模拟人上练习胸外按压的真实场景"},
    {"topic": "first_aid", "style": "realistic_photo", "intent": "公共场所 AED 设备箱及标识的实景展示"},
    {"topic": "first_aid", "style": "realistic_photo", "intent": "120 急救人员到达现场后交接救治的专业场景"},
    # flat_illustration
    {"topic": "first_aid", "style": "flat_illustration", "intent": "心肺复苏按压位置和深度的扁平人体示意图"},
    {"topic": "first_aid", "style": "flat_illustration", "intent": "烫伤五步处理法（冲脱泡盖送）扁平图标步骤图"},
    {"topic": "first_aid", "style": "flat_illustration", "intent": "家庭急救箱标配物品清单扁平图标分类插画"},

    # ── 用药安全 ────────────────────────────────────────────────
    # infographic
    {"topic": "medication_safety", "style": "infographic", "intent": "老年人常见的不合理用药行为及正确做法对照表"},
    {"topic": "medication_safety", "style": "infographic", "intent": "抗生素合理使用三原则信息图：不自行购买、不随意停药、不与他人共用"},
    {"topic": "medication_safety", "style": "infographic", "intent": "儿童常用退热药（对乙酰氨基酚/布洛芬）剂量与注意事项信息图"},
    # process_diagram
    {"topic": "medication_safety", "style": "process_diagram", "intent": "拿到处方后的安全用药流程：核对→阅读说明→正确服用→观察反应→复诊"},
    {"topic": "medication_safety", "style": "process_diagram", "intent": "家庭过期药品回收处理流程"},
    {"topic": "medication_safety", "style": "process_diagram", "intent": "药物不良反应发生后的报告与就医流程"},
    # comic_narrative
    {"topic": "medication_safety", "style": "comic_narrative", "intent": "孩子误食药物后家长正确应急处理的漫画故事"},
    {"topic": "medication_safety", "style": "comic_narrative", "intent": "奶奶把多种药混在一起吃被孙女及时阻止的趣味漫画"},
    {"topic": "medication_safety", "style": "comic_narrative", "intent": "感冒患者自行叠加多种感冒药差点出事的警示漫画"},
    # metaphor_scene
    {"topic": "medication_safety", "style": "metaphor_scene", "intent": "药物如同双刃剑，正确使用治病、滥用伤身的隐喻"},
    {"topic": "medication_safety", "style": "metaphor_scene", "intent": "抗生素耐药性像病菌穿上越来越厚的铠甲的概念场景"},
    {"topic": "medication_safety", "style": "metaphor_scene", "intent": "药品有效期像食物保质期，过期即失去保护力的类比隐喻"},
    # realistic_photo
    {"topic": "medication_safety", "style": "realistic_photo", "intent": "药师在药房窗口为患者讲解用药注意事项的真实场景"},
    {"topic": "medication_safety", "style": "realistic_photo", "intent": "家庭药箱分层整理、分类标签清晰的实景展示"},
    {"topic": "medication_safety", "style": "realistic_photo", "intent": "儿童安全药瓶盖设计特写，强调防误食设计"},
    # flat_illustration
    {"topic": "medication_safety", "style": "flat_illustration", "intent": "家庭药箱分类整理示意图，标注存放要点和有效期检查"},
    {"topic": "medication_safety", "style": "flat_illustration", "intent": "服药时间图标时钟：饭前/饭中/饭后/睡前的扁平图解"},
    {"topic": "medication_safety", "style": "flat_illustration", "intent": "药物相互作用警示：常见不能同服药物的扁平对比图"},

    # ── 老年健康 ────────────────────────────────────────────────
    # infographic
    {"topic": "elderly_health", "style": "infographic", "intent": "骨质疏松风险因素自评表及预防措施信息图"},
    {"topic": "elderly_health", "style": "infographic", "intent": "老年人跌倒高风险场景与改造建议对照表"},
    {"topic": "elderly_health", "style": "infographic", "intent": "认知障碍早期 10 大预警信号清单信息图"},
    # process_diagram
    {"topic": "elderly_health", "style": "process_diagram", "intent": "老年人防跌倒居家环境改造要点示意图"},
    {"topic": "elderly_health", "style": "process_diagram", "intent": "老年人跌倒后的正确自救和求助流程"},
    {"topic": "elderly_health", "style": "process_diagram", "intent": "认知功能筛查→诊断→干预→随访的管理流程"},
    # comic_narrative
    {"topic": "elderly_health", "style": "comic_narrative", "intent": "老两口互相提醒补钙晒太阳防骨质疏松的日常漫画"},
    {"topic": "elderly_health", "style": "comic_narrative", "intent": "爷爷在家险些滑倒后全家动员做适老化改造的漫画"},
    {"topic": "elderly_health", "style": "comic_narrative", "intent": "老人忘记刚说过的话被家人温柔引导就医的温馨漫画"},
    # metaphor_scene
    {"topic": "elderly_health", "style": "metaphor_scene", "intent": "骨骼像房屋地基，钙质流失如同地基被慢慢掏空的隐喻"},
    {"topic": "elderly_health", "style": "metaphor_scene", "intent": "记忆像书架上的书本逐渐褪色散落，早期干预如同修缮整理的场景"},
    {"topic": "elderly_health", "style": "metaphor_scene", "intent": "衰老如同四季轮转进入冬季，科学养护让冬日也有暖阳的隐喻"},
    # realistic_photo
    {"topic": "elderly_health", "style": "realistic_photo", "intent": "老年人在社区活动室做太极拳晨练的真实场景"},
    {"topic": "elderly_health", "style": "realistic_photo", "intent": "适老化改造后的卫生间：扶手、防滑垫、坐式淋浴的实景"},
    {"topic": "elderly_health", "style": "realistic_photo", "intent": "医生为老年患者做简易认知筛查（画钟测试）的诊室场景"},
    # flat_illustration
    {"topic": "elderly_health", "style": "flat_illustration", "intent": "适合老年人的四类运动方式插画：散步、太极、游泳、伸展"},
    {"topic": "elderly_health", "style": "flat_illustration", "intent": "老年人每日钙摄入来源扁平食物图标集"},
    {"topic": "elderly_health", "style": "flat_illustration", "intent": "居家防跌倒改造对照扁平图：改造前 vs 改造后"},

    # ── 口腔与眼健康 ────────────────────────────────────────────
    # infographic
    {"topic": "oral_eye_health", "style": "infographic", "intent": "儿童近视预防「20-20-20」护眼法则信息图"},
    {"topic": "oral_eye_health", "style": "infographic", "intent": "各年龄段口腔保健重点与推荐检查频次对照表"},
    {"topic": "oral_eye_health", "style": "infographic", "intent": "近视防控「一增一减」（增加户外、减少近距离用眼）数据信息图"},
    # process_diagram
    {"topic": "oral_eye_health", "style": "process_diagram", "intent": "正确刷牙方法巴氏刷牙法的步骤分解图"},
    {"topic": "oral_eye_health", "style": "process_diagram", "intent": "儿童涂氟防龋流程：检查→清洁→涂氟→注意事项"},
    {"topic": "oral_eye_health", "style": "process_diagram", "intent": "发现孩子视力异常后的就医与矫正流程"},
    # comic_narrative
    {"topic": "oral_eye_health", "style": "comic_narrative", "intent": "小朋友不爱刷牙被「蛀虫怪」缠上后醒悟的趣味漫画"},
    {"topic": "oral_eye_health", "style": "comic_narrative", "intent": "全家人一起做眼保健操的温馨日常漫画"},
    {"topic": "oral_eye_health", "style": "comic_narrative", "intent": "孩子第一次戴眼镜从抗拒到接受的成长漫画"},
    # metaphor_scene
    {"topic": "oral_eye_health", "style": "metaphor_scene", "intent": "牙齿像城墙，牙菌斑像敌军不断侵蚀城砖的隐喻"},
    {"topic": "oral_eye_health", "style": "metaphor_scene", "intent": "眼睛像精密相机，近视是镜头对焦系统出了偏差的概念场景"},
    {"topic": "oral_eye_health", "style": "metaphor_scene", "intent": "乳牙像占位符为恒牙保留空间，过早脱落导致排列紊乱的隐喻"},
    # realistic_photo
    {"topic": "oral_eye_health", "style": "realistic_photo", "intent": "儿童在口腔科接受窝沟封闭术的真实诊疗场景"},
    {"topic": "oral_eye_health", "style": "realistic_photo", "intent": "学校视力筛查现场，孩子排队用视力表检测的场景"},
    {"topic": "oral_eye_health", "style": "realistic_photo", "intent": "家长指导孩子正确握笔姿势保护视力的家庭场景"},
    # flat_illustration
    {"topic": "oral_eye_health", "style": "flat_illustration", "intent": "定期口腔检查和洗牙的重要性概念插画"},
    {"topic": "oral_eye_health", "style": "flat_illustration", "intent": "护眼好习惯扁平图标集：户外 2h、台灯、坐姿、眼保健操"},
    {"topic": "oral_eye_health", "style": "flat_illustration", "intent": "牙齿发育时间线：乳牙萌出到恒牙替换的扁平时间轴"},
]

# ══════════════════════════════════════════════════════════════
#  种子赛制包
# ══════════════════════════════════════════════════════════════

SEED_CONTEST_PACKS = [
    {
        "name": "健康中国行动知识普及科普大赛",
        "organizer": "国家卫生健康委员会",
        "level": "national",
        "word_limit": 3000,
        "file_format": "docx+pdf",
        "ai_disclosure": "recommended",
        "image_format": "jpg",
        "naming_template": "作品名-单位-第一作者",
        "source_note": "种子数据 — 请以官方最新通知为准",
    },
    {
        "name": "中华医学会健康科普大赛",
        "organizer": "中华医学会",
        "level": "national",
        "word_limit": 2000,
        "file_format": "docx",
        "ai_disclosure": "required",
        "image_format": "jpg",
        "naming_template": "单位-科室-第一作者-作品名",
        "source_note": "种子数据 — 请以官方最新通知为准",
    },
    {
        "name": "省级健康科普作品征集活动",
        "organizer": "省卫生健康委员会",
        "level": "provincial",
        "word_limit": 2500,
        "file_format": "docx+pdf",
        "ai_disclosure": "none",
        "image_format": "jpg",
        "naming_template": "单位-科室-作品名",
        "source_note": "种子数据模板 — 请按所在省份的实际通知修改",
    },
    {
        "name": "中国医师协会健康传播大赛",
        "organizer": "中国医师协会",
        "level": "association",
        "word_limit": 2000,
        "file_format": "docx",
        "ai_disclosure": "recommended",
        "image_format": "jpg",
        "naming_template": "单位-科室-第一作者-作品名",
        "source_note": "种子数据 — 请以官方最新通知为准",
    },
    {
        "name": "护理学会科普作品大赛",
        "organizer": "中华护理学会",
        "level": "association",
        "word_limit": 1500,
        "file_format": "docx",
        "ai_disclosure": "none",
        "image_format": "jpg",
        "naming_template": "第一作者-作品名",
        "source_note": "种子数据 — 请以官方最新通知为准",
    },
]


async def ensure_contest_seed_data(db: AsyncSession) -> None:
    """确保种子数据存在，幂等执行"""

    # 1. 风格预设
    existing = await db.execute(select(StylePreset.name))
    existing_names = {r[0] for r in existing}
    for sp in STYLE_PRESETS:
        if sp["name"] not in existing_names:
            db.add(StylePreset(**sp))
    await db.flush()

    # 2. 负向词库（全局 + 选题级）
    existing_neg = await db.execute(
        select(NegativeWordSet.category, NegativeWordSet.scope, NegativeWordSet.topic_category)
    )
    existing_neg_keys = {(r[0], r[1], r[2]) for r in existing_neg}
    for nws in NEGATIVE_WORD_SETS + TOPIC_NEGATIVE_WORD_SETS:
        key = (nws["category"], nws["scope"], nws.get("topic_category"))
        if key not in existing_neg_keys:
            db.add(NegativeWordSet(**nws))
    await db.flush()

    # 3. 画意范例
    existing_count = await db.execute(
        select(sa_func.count()).select_from(PaintingIntentExample)
    )
    count = existing_count.scalar() or 0
    if count == 0:
        preset_map = {}
        preset_version_map = {}
        presets = await db.execute(select(StylePreset))
        for p in presets.scalars():
            preset_map[p.name] = p.id
            preset_version_map[p.name] = p.version or 1
        for ex in INTENT_EXAMPLES:
            style_name = ex["style"]
            db.add(PaintingIntentExample(
                topic_category=ex["topic"],
                style_preset_id=preset_map.get(style_name),
                preset_version=preset_version_map.get(style_name, 1),
                intent_text=ex["intent"],
            ))
    await db.flush()

    # 4. 赛制包
    existing_packs = await db.execute(select(ContestPack.name))
    existing_pack_names = {r[0] for r in existing_packs}
    for pack in SEED_CONTEST_PACKS:
        if pack["name"] not in existing_pack_names:
            db.add(ContestPack(**pack))

    await db.commit()
    logger.info("Contest seed data ensured")


# 需要 from sqlalchemy import func as sa_func
from sqlalchemy import func as sa_func

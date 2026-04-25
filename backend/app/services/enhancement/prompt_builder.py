"""
四层 Prompt 架构增强提示词构建（v4.0）
参照《医学科普写作系统—四层Prompt架构》设计：
  Layer 0-1 — System Message（宪法层，在 base.py 中组装；文本见 prompt-example/prompts/layer0/、layer1/）
  Part 1   — 写作能力增强（语言转化 + 结构模板 + 段落节奏 + 术语 + 学科 + 规范）
  Part 2   — 内容事实来源（结构化文献注入 + 分析报告，唯一事实依据）
  Part 3   — 写作任务（文章元信息 + 前序章节 + 任务指令 + 回指）
"""
import json
from typing import Optional
from app.services.enhancement.rag_retriever import RAGRetriever
from app.services.enhancement.example_retriever import ExampleRetriever
from app.services.enhancement.term_injector import TermInjector
from app.agents.prompts.loader import load_task_guideline, load_comic_guideline, load_handbook_guideline
from app.services.format_router import (
    FORMAT_NAMES,
    SECTION_TITLES,
    PLATFORM_NAMES,
    AUDIENCE_NAMES,
    SPECIALTY_NAMES,
)

rag_retriever = RAGRetriever()
example_retriever = ExampleRetriever()
term_injector = TermInjector()


def _infer_evidence_level(title: str, abstract: str, journal: str) -> str:
    """基于标题/摘要/期刊关键词推断证据等级，供模型匹配证据语言规则"""
    text = f"{title} {abstract}".lower()
    if any(k in text for k in ("guideline", "指南", "推荐", "共识", "consensus", "recommendation")):
        return "指南推荐"
    if any(k in text for k in ("meta-analysis", "meta analysis", "systematic review", "荟萃分析", "系统综述", "系统评价")):
        return "Meta分析"
    if any(k in text for k in (
        "randomized controlled", "randomised controlled", "rct",
        "随机对照", "随机双盲", "double-blind", "placebo-controlled",
    )):
        return "RCT"
    if any(k in text for k in ("cohort", "case-control", "cross-sectional", "队列", "病例对照", "横断面")):
        return "观察性研究"
    if any(k in text for k in ("expert opinion", "commentary", "editorial", "专家意见", "述评")):
        return "专家意见"
    if any(k in text for k in ("animal", "mouse", "rat", "in vitro", "cell line", "动物", "小鼠", "体外")):
        return "动物/体外实验"
    return "其他"


async def _fetch_binding_order(article_id: int | None) -> list[int]:
    """获取 binding 表中按 priority 排序的 paper_id 列表，保证编号与导出/前端一致"""
    if not article_id:
        return []
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.article import ArticleLiteratureBinding
    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ArticleLiteratureBinding.paper_id)
                .where(ArticleLiteratureBinding.article_id == article_id)
                .order_by(
                    ArticleLiteratureBinding.priority.asc(),
                    ArticleLiteratureBinding.id.asc(),
                )
            )
            result = await db.execute(stmt)
            seen = set()
            ordered = []
            for row in result.fetchall():
                pid = row[0]
                if pid not in seen:
                    seen.add(pid)
                    ordered.append(pid)
            return ordered
    except Exception:
        return []


async def _fetch_paper_meta(paper_ids: list[int]) -> dict[int, dict]:
    """批量获取文献元数据，返回 {paper_id: meta_dict}，含自动推断的证据等级"""
    if not paper_ids:
        return {}
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.literature import LiteraturePaper
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(LiteraturePaper).where(LiteraturePaper.id.in_(paper_ids))
            result = await db.execute(stmt)
            papers = result.scalars().all()
            meta = {}
            for p in papers:
                authors_raw = p.authors or "[]"
                try:
                    authors_list = json.loads(authors_raw) if isinstance(authors_raw, str) else (authors_raw or [])
                    author_names = [a.get("name", "") for a in authors_list if isinstance(a, dict) and a.get("name")]
                except Exception:
                    author_names = []
                title = p.title or ""
                abstract = p.abstract or ""
                journal = p.journal or ""
                meta[p.id] = {
                    "title": title,
                    "authors": author_names,
                    "journal": journal,
                    "year": p.year,
                    "volume": p.volume or "",
                    "issue": p.issue or "",
                    "pages": p.pages or "",
                    "doi": p.doi or "",
                    "url": p.url or "",
                    "abstract": abstract[:300],
                    "evidence_level": _infer_evidence_level(title, abstract, journal),
                }
            return meta
    except Exception:
        return {}


async def _personal_corpus_section(user_id: int = 1) -> str:
    from app.core.database import AsyncSessionLocal
    from app.services.personal_corpus_prompt import load_corpus_block

    async with AsyncSessionLocal() as db:
        return await load_corpus_block(db, user_id)

_BUILTIN_SPECIALTY_CONFIGS: dict[str, dict] = {
    "endocrine": {
        "specialty_context": "内分泌科专注于糖尿病、甲状腺疾病、代谢综合征、骨质疏松等内分泌和代谢性疾病的诊治。强调终身管理、用药依从性和三级预防（预防发生→早期干预→综合管理防并发症）。",
        "key_diseases": ["2型糖尿病", "甲状腺功能亢进/减退", "代谢综合征", "骨质疏松", "肥胖"],
        "avoid_topics": ["具体胰岛素注射剂量", "个性化降糖方案"],
        "hook_examples": [
            "体检单上的「空腹血糖 6.1」到底要不要紧？",
            "为什么吃得少了体重反而不降？",
            "脖子上的这条黑线，可能是糖尿病的预警信号",
        ],
        "children_analogies": [
            "胰岛素就像一把钥匙，帮助葡萄糖进入细胞的小房间",
            "甲状腺就像身体的小发电站，控制你的精力和体温",
        ],
    },
    "cardiology": {
        "specialty_context": "心内科覆盖冠心病、高血压、心律失常、心力衰竭、心肌病等心血管疾病。强调一级预防（危险因素控制）和二级预防（规范用药防复发），关注急性胸痛的识别和急救。",
        "key_diseases": ["冠心病", "高血压", "心房颤动", "心力衰竭", "高脂血症"],
        "avoid_topics": ["具体抗凝药物剂量", "介入手术具体操作"],
        "hook_examples": [
            "心脏在半夜叫醒你，可能是它在求救",
            "血压 130/85，处于高血压和正常之间的灰色地带",
            "胸口闷了 3 天还没好？别再以为是累的了",
        ],
        "children_analogies": [
            "心脏就像一个不停工作的小水泵，一天要跳 10 万次",
            "血管就像城市的水管，堵了水就送不到了",
        ],
    },
    "respiratory": {
        "specialty_context": "呼吸科涵盖哮喘、慢性阻塞性肺疾病(COPD)、肺炎、肺癌筛查和肺结节管理等呼吸系统疾病。强调吸入装置的正确使用、戒烟和肺功能监测。",
        "key_diseases": ["哮喘", "慢性阻塞性肺疾病(COPD)", "肺炎", "肺结节", "睡眠呼吸暂停"],
        "avoid_topics": ["具体吸入剂剂量方案", "肺癌化疗具体方案"],
        "hook_examples": [
            "咳嗽超过 8 周还没好？可能不只是感冒",
            "打呼噜不是睡得香，可能是呼吸在「罢工」",
            "体检发现肺结节，需要马上做手术吗？",
        ],
        "children_analogies": [
            "肺就像两个大气球，帮你把新鲜空气换进来",
            "哮喘发作时，气管就像被捏紧的吸管，空气很难通过",
        ],
    },
    "neurology": {
        "specialty_context": "神经科涉及脑卒中、帕金森病、阿尔茨海默病、癫痫、头痛和周围神经病变等。强调卒中的「FAST」快速识别和时间窗内急救（黄金 4.5 小时），以及慢性神经退行性疾病的长期管理。",
        "key_diseases": ["脑卒中", "帕金森病", "阿尔茨海默病", "癫痫", "偏头痛"],
        "avoid_topics": ["具体抗癫痫药物剂量", "脑血管手术细节"],
        "hook_examples": [
            "突然说不清话、一侧手脚没力——这不是「中邪」而是脑卒中",
            "记忆力下降就是老年痴呆？其实大多数不是",
            "头痛也分「好头痛」和「坏头痛」，如何区分？",
        ],
        "children_analogies": [
            "大脑就像一台超级计算机，神经就是它的电线",
            "癫痫发作就像大脑里的电路突然短路了",
        ],
    },
    "pediatrics": {
        "specialty_context": "儿科覆盖从新生儿到青少年的全年龄段健康问题，包括生长发育监测、常见传染病、过敏性疾病、儿童哮喘、营养与喂养指导。强调按龄科普、避免恐惧元素、用儿童友好的表达方式。",
        "key_diseases": ["手足口病", "儿童哮喘", "食物过敏", "腺样体肥大", "注意力缺陷多动障碍(ADHD)"],
        "avoid_topics": ["成人用药剂量", "恐惧性描述"],
        "hook_examples": [
            "宝宝反复发烧要不要马上去医院？记住这三个信号",
            "孩子总揉鼻子打喷嚏，可能不是感冒而是过敏",
            "一岁以内不能吃蜂蜜？是真的！",
        ],
        "children_analogies": [
            "白细胞就像身体里的小卫兵，专门打败入侵的坏细菌",
            "疫苗就像给小卫兵们看了一张坏人的照片，下次见到就认识了",
        ],
    },
}


def _resolve_specialty_config(specialty: str | None, specialty_config: dict | None) -> dict | None:
    if specialty_config:
        return specialty_config
    if specialty and specialty in _BUILTIN_SPECIALTY_CONFIGS:
        return _BUILTIN_SPECIALTY_CONFIGS[specialty]
    return None


SCRIPT_IMAGE_FORMATS = {
    "oral_script", "drama_script", "storyboard", "comic_strip",
    "card_series", "poster", "picture_book", "long_image",
}


# ════════════════════════════════════════════════════════════════
# Part 1 构建：写作能力增强
# ════════════════════════════════════════════════════════════════

_LANGUAGE_TRANSFORM_RULES = """## 一、语言转化规则

### 1.1 术语处理策略
- 只保留读者必须知道的术语，省略读者不需要知道的技术名词。
  ✓ "这种检测方法利用一种结合力极强的蛋白质来固定目标物"（读者能理解原理）
  ✗ "这种检测方法利用生物素-链霉亲和素系统"（读者记不住也不需要记这个名字）
- 确有必要保留的术语，首次出现时紧跟通俗解释。格式：专业术语（通俗解释）
- 后续出现同一术语可直接使用，不必重复解释。
- 每段正文中专业术语不超过2个，超出时拆分段落。

### 1.2 类比使用规则
- 全文比喻/类比总数 ≤ 2 个，仅在最难理解的概念处使用。大多数知识点直接用白话讲清楚。
- 比喻不得出现在开篇引入段和最后一段（结尾）。
- 优先用"比如""例如"引导的具体例子代替比喻——例子比比喻更精确。
- 使用比喻时补充一句限定语说明边界。
- 禁止连续两段各出现一个比喻。

### 1.3 数字呈现规则
- 大数字用对比方式呈现：✓ "大约每11个成年人中就有1人"  ✗ "463,000,000名"
- 风险数据用自然频率：✓ "每1000人中约3人"  ✗ "发生率0.3%"
- 所有数字必须来自「内容事实来源」区域，本规则仅规定呈现方式。"""

_STRUCTURE_TEMPLATES = """## 二、内容组织原则

- 从读者最关心的问题切入，不一定从"定义"开始。如果读者最想知道"怎么办"，可以先讲行动再讲原理。
- 每个小节解决一个具体问题，小节数量和顺序由主题本身决定，不套用固定模板。
- 用朴素的信息型小标题分隔（如"生物素如何干扰血液检测""哪些人需要特别注意"），不编号，不追求对仗。
- 最后落在具体的行动建议或就医信号上。不写升华段、不写感悟段。
- 参考组织思路（灵活运用，非强制顺序）：什么 → 为什么 → 怎么办 → 什么时候该就医"""

_PARAGRAPH_RHYTHM_RULES = """## 三、段落与节奏

⛔⛔⛔ 高权重禁止项（违反任何一条视为不合格，必须重写）⛔⛔⛔

1. 比喻总数 ≤ 2：全文最多2个比喻/类比，且必须用在最难理解的概念上。多数知识点直接用白话讲清楚。
2. 首尾段禁止比喻：开篇引入段和最后一段绝对不能出现比喻。
3. 禁止三项并列："一是/二是/三是""首先/其次/最后""A；或者B；又或者C"——改用两项或四项，或拆成独立短句。
4. 禁止"不是A而是B"收尾：如"不是为了增加焦虑，而是为了让我们更从容"——直接说B，删掉"不是A"。
5. 禁止虚假强调前缀："更值得注意的是""值得一提的是""需要指出的是"——直接陈述内容。
6. 禁止导游腔："这篇文章想和你聊聊""让我们一起来看看""接下来让我们"——删掉，直接进入内容。
7. 末段必须是行动建议或事实：禁止情感升华、禁止"健康密码""最佳搭档"等空洞比喻。
8. 安全声明仅1句：全文只允许在最末尾出现一句简短免责声明，正文中禁止插入"请咨询医生""仅供参考"。

⛔⛔⛔ 以上8条是硬性红线，输出前必须逐条自检 ⛔⛔⛔

---

## 抗AIGC检测规则（让文本更像人写的）

### 句式多样性（对抗Burstiness + 句法同质性检测）
- 禁止连续3句结构相同——如连续三句都是"A可能由B导致"式判断句、或都是无主语陈述句
- 段内必须混合不同句型：陈述句、短句判断、带破折号的补充、带数据的论证、反问
- 避免所有句子都在同一字数区间（如全落在25-30字）——长句（40+字，展开因果）和短句（≤15字，下判断）交替
- 每段内最长句与最短句的字数差 ≥ 15字

### 降低可预测性（对抗困惑度检测）
- 允许口语化表达：可以用"说白了""换句话说""这就有意思了""问题是"等口语词开头。
- 允许1-2处"硬切"：解释完一个概念后，不用过渡词直接进入下一个话题。读者能跟上。
- 禁止段首句式重复：连续3段不能用相同句式开头（如都是"研究发现...""事实上..."）。
- 偶尔打破语法完美：可以用"——"插入补充说明，可以用省略号表示停顿或留白。

### 人类噪声注入（对抗分类模型）
- 允许1-2处"不完整暗示"：如"这还涉及另一个机制，但先说结论""具体原理比较复杂，这里只说关键点"。
- 允许偶尔自问自答，但不成为固定节奏（全文最多2处）。
- 结尾可以留一个"未完全展开的点"，不必面面俱到。真人写作常常意犹未尽。
- 允许1处轻微的"立场流露"：如"我个人更倾向于...""临床上更常见的做法是..."（仅限有明确证据支持的观点）。

### 标点与格式波动
- 全文破折号"——"使用1-3次，用于插入补充或转折。
- 允许偶尔使用省略号"……"表示思考停顿或列举未尽（全文≤2次）。
- 括号补充说明不要每段都有，也不要完全没有——像真人写作一样随机。

---

- 段落长度要有变化：简单的信息用短段（2-3句），需要展开的解释用长段，不要所有段落一样长。
- 章节之间用内容本身的逻辑衔接，禁止以下播音腔过渡句：
  ✗ "说完了X，接下来……" / "了解了X之后……"
  ✗ "那么，面对这样的困境，我们究竟该怎么办呢？"
  ✗ "接下来让我们看看……" / "我们不禁要问……"
  段落之间直接推进内容，读者能自己跟上逻辑。
- 设问句偶尔用一两处即可，不要变成固定节奏。不要用"你可能会问""很多人好奇"等套话引导。
- 禁止震惊体（"竟然""99%的人不知道"）和恐吓性表述。
- 禁止绝对性承诺（"保证""一定"）。

## 四、反套路化写作（极重要——决定读者是否信任这篇文章）

### 4.1 禁止套话开头
以下开头方式全部禁止：
- "你有没有想过……" / "你是否曾经……" / "你知道吗"
- "在日常生活中……" / "在当今社会……" / "随着……的发展"
- "今天，我们来聊聊……" / "今天就带你了解……"
- "这不是危言耸听" / "这绝非夸张"
优先使用具体场景、数据或案例直接切入。

### 4.2 禁止三段排比
连续三项并列的节奏（"A；或者B；又或者C"）是 AI 写作最明显的特征。全文三项并列结构不超过2处。需要列举时用两项或四项，或拆成独立短句。

### 4.3 禁止套路式收尾
- 禁止"不是A而是B"句式（如"不是为了增加焦虑，而是为了让我们更从容"）——如需表达类似意思，直接说B
- 禁止宏大叙事和情感升华
- 禁止"今天我们聊了……"式总结
- 禁止在结尾呼吁读者分享文章
- 禁止以问句结尾
- 最后一段必须是具体行动建议或简短事实陈述

### 4.4 小标题要朴素
- 至少一半的小标题用朴素的信息型标题（如"生物素如何干扰血液检测"），不追求每个都"巧"
- 小标题禁止对仗、双关、设问。功能是导航，不是表演
- 禁止每段开头用"那么""其实""事实上""值得一提的是"等高频 AI 连接词

### 4.5 正文开篇必须有读者入口
- 正文第一段即"引入段"（2-4句），第一句必须是"读者入口"——场景、疑问、常见误解或反常识点
- 入口的作用：让读者先代入（"这事跟我有关"），然后再接收核心信息
- 禁止第一句就抛结论（读者还不知道在讨论什么就被砸一个判断句）
- 入口之后紧跟核心信息，不要铺垫太多。引入段让读者好奇，后续段落给答案
- 禁止在引入段中罗列后文的具体案例——一个转折就够了

### 4.6 词语黑名单（全文禁用）
以下词语在科普写作中严重暴露 AI 痕迹，全文禁止：
- 守护、并肩、携手、蓝图、赋能、助力
- 震撼、令人惊叹、超乎想象、令人叹为观止、触目惊心、让人深思
- 隐形杀手、不定时炸弹
- "拥抱"用于抽象概念（如"拥抱变化""拥抱健康"）
- "让我们""我们一起"开头的呼吁句
- "魔法""神奇"用于形容科学机制（如"催化剂像魔法师"）
- "各有各的道理""见仁见智"用于回避有明确科学共识的问题
- 全文"非常""极其""极为""十分"总数 ≤ 3次

### 4.7 安全性填充语禁令
以下套话信息量为零，全文禁止：
- "当然，每个人的身体状况不同，具体情况还需要咨询专业医生"
- "需要注意的是，以上信息仅供参考，不能替代专业医疗建议"
- "值得一提的是，科学研究仍在不断发展中"
- "总的来说，健康管理是一个复杂的话题"
免责声明仅在文末出现一次，不超过一句话。正文中禁止插入"具体请咨询医生""仅供参考"等套话。如果一句话删掉后文章信息量不减少，就删掉它。

### 4.8 医学与生命科学写作专项禁令
**医学通用：**
- 禁止"战争隐喻"：不用"卫士""巡逻""攻击""入侵者""叛变的士兵"等军事化类比描述免疫和疾病。改用直白的生物学描述（如"白细胞能识别并清除异常细胞"）
- 每个"研究发现""研究表明"必须跟具体来源（期刊名+年份 或 机构名）。不能给出来源的，改为"临床上常见的观察是……"或直接删除"研究发现"
- 涉及剂量、频率、比例的建议必须给出具体数字，禁止"适量""适当""少量"等模糊表述
- 禁止使用"超级食物"等神话化描述

**药学相关：**
- 禁止"是药三分毒""能不吃就不吃"等笼统表述。讨论药物安全性时必须给出获益-风险的具体数据对比
- 禁止将"天然"等同于"安全"（马兜铃酸、何首乌都是天然物但有明确毒性）
- 讨论治疗方案时以"是否有高质量临床证据"为核心评判标准，而非以"中/西""天然/合成"分类
- 禁止"西药快中药慢"等无依据的二分法

**生物学相关：**
- 描述进化时禁止目的论措辞（"为了适应环境""为了生存"），改用"在选择压力下""碰巧具有某特征的个体"
- 禁止"基因决定"的表述，改用"基因影响""基因与XX风险相关"。讨论基因与性状关系时必须说明效应量和环境调节作用

**中医与传统医学：**
- 禁止将中医概念与现代医学概念强行画等号（如"上火=炎症""经络=筋膜"）
- 禁止用"博大精深""老祖宗的智慧"替代证据讨论
- 禁止将古籍引文直接等同于科学论据
- 评价传统医学疗法时，以临床试验证据为核心标准，与评价其他疗法的标准保持一致

**皮肤科与护肤：**
- 描述护肤成分功效时，必须区分体外实验和人体临床试验证据
- 禁止"XX神器""全能选手"等营销化表述
- 禁止把多步骤护肤流程包装为"科学步骤"——皮肤科共识的基础护肤只有清洁、保湿、防晒三步

**口腔科：**
- 禁止将口腔疾病与全身疾病的"相关性"表述为"因果关系"
- 口腔护理建议必须区分"共识性推荐"和"证据尚不充分的经验做法"

**睡眠科学：**
- 睡眠时长建议必须说明个体差异和判断方法，禁止将"7-9小时"当作普适标准
- 助眠建议必须区分"短期偶尔失眠"和"慢性失眠"给出不同方案
- 对慢性失眠，必须提及CBT-I作为一线推荐，而非只列睡眠卫生清单

### 4.9 禁止虚假平衡
当科学共识明确时（疫苗安全性、气候变化、进化论等），禁止用"双方各有道理""尚存争议"来制造虚假平衡。必须明确说明科学共识是什么，然后可以补充少数意见的具体内容和其证据强度。

### 4.10 禁止强行三分结构
禁止所有问题都恰好给出3个原因/建议/步骤。如果核心问题只有1个，就只说1个。优先深度展开最重要的那一个，而非浅层罗列多个。

### 4.11 禁止共情前缀
科普文章中禁止使用"我理解你的感受""这确实让人焦虑""这种心情完全可以理解"等共情前缀。直接给信息。如果信息本身足够有用，读者的焦虑自然会缓解。

### 4.12 禁止编造数据
禁止生成未经核实的具体数据（百分比、样本量、精确数值）。如果记不清具体数字，用"大约""数量级上"等模糊但诚实的表述。给出的每一个具体数字，必须能追溯到原始文献或权威机构报告。

### 4.13 禁止刻意换词
同一概念在全文中使用统一名称，首次出现时可加注别名，之后保持一致。禁止为了"文采"而在不同段落中轮换同义词（如：生物素→维生素B7→该营养素→这一微量元素）。术语一致性优先于行文多样性。

### 4.14 禁止无权重罗列
禁止不加权重地罗列"首先、其次、再次、最后"。必须判断各因素的重要性差异，把最重要的放在第一位并展开解释，次要因素可以简略带过。读者需要的是优先级排序，不是平铺清单。

### 4.15 禁止伪辩证
当证据明确偏向一侧时，禁止用"一方面……另一方面……"制造虚假平衡感。如需提及相反方向的证据，必须同时说明其证据等级、效应量和实际意义，而非简单罗列让读者"综合考量"。

### 4.16 禁止虚假强调前缀
禁止使用"值得注意的是""需要指出的是""值得一提的是""更为重要的是"等虚假强调前缀。直接陈述内容。如果内容确实重要，通过把它放在段首来强调。

### 4.17 禁止导游腔
禁止使用"让我们一起来看看""接下来就让我们""让我带你了解""走进XX的世界"等导游腔引导句。删掉这些句子，直接开始说内容。

### 4.18 禁止段落复读
段落或小节末尾禁止使用"总而言之""综上所述""由此可见""因此可知"等总结句。段落写完最后一个信息点就停，或直接过渡到下一段。2000字以内的文章禁止用"总之""总而言之"开头的复述段。

### 4.19 数据呈现与引用规则
- 数据出现后禁止用"令人震惊""触目惊心""让人深思"等情绪词追加评论
- 用第二个数据（比率、对比基准、标准值）赋予语境，而非用感叹号
- 全文感叹号 ≤ 1个（引用原文除外）
- [N]引用角标只标在需要文献支撑的具体论断上（带数据、带结论的句子）
- 常识性陈述不标[N]——"化验有误差"不需要引用，"假阳性率达X%"才需要
- 如果一句话即使没有引用读者也会接受，那就不标

### 4.20 句式简洁规则
- 单个句子中的条件限定不超过2层。如果限定条件超过2个，拆成多个短句或用列表呈现
- 全文"然而/但是/不过"的出现频率不超过每500字1次
- 优先使用具体数值和分级标准，而非"某些情况下""一定程度上"等模糊限定

### 4.21 语域与风格
{style_rules}
- 全文语域必须统一——不能在同一篇文章里混用不同风格（如口语吐槽+学术引用）
- 直接给信息，不铺垫情绪、不渲染气氛、不戏剧化开场
- 说完了就停，不追加总结、不升华、不煽情
- 如果一句话删掉后文章信息量不减少，就删掉它

### 4.22 信息密度与递进（极重要——直接决定文章质量和AI检测）
每句话必须承载具体信息，且每句话必须比上一句推进新信息：
- "很多人都有过这种经历" → 删掉（常识铺垫，无信息量）
- "这个问题值得关注" → 删掉或替换为具体原因
- "显著降低风险" → 给出幅度（"降低约30%"）或至少给范围
- "多种因素" → 列出具体是哪几种
- 关键概念首次出现时必须界定（什么是什么、分哪几类）
- 比喻/类比 ≤ 1个/段，且不能替代正式术语——应在给出术语后用比喻辅助理解

信息递进规则（禁止多句同义复述）：
- 如果两句话说的是同一件事的不同表述，必须砍掉一句或合并
- 典型反例：①"异常可能是误差" ②"这种误差不少见" ③"医患容易忽视误差"——三句一意
- 检查方法：读完一句话后问"读者从这句话获得了什么前一句没有的新信息？"——答不上来就删

### 4.22b 去名词化（禁止公文腔）
- 禁止名词化组合："聚焦于""进行了探讨""存在的技术偏差""具有重要意义""呈现出...趋势"
- 改为动词主导的自然句式：
  ✗ "医患双方常聚焦于异常数值" → ✓ "医生和患者往往只盯着那个异常数字"
  ✗ "检测环节本身存在的技术偏差" → ✓ "检测过程本身可能出错"
- 句子要有明确的人做主语，避免无主语被动结构堆砌

### 4.23 初稿定位
本次输出是"草稿"，后续会经历自动改写流程。因此：
- 优先保证事实准确、结构清晰、引用完整——这些改写无法补救
- 句式可以朴素直白，不必刻意追求修辞多样性——改写阶段会处理
- 在需要具体数据/案例的地方，尽量给出具体信息而非抽象概括——抽象改写无法变具体
- 但仍然必须遵守上述所有禁止项（模板词、套话、导游腔等）——这些是硬性红线"""


def _build_knowledge_section(knowledge_chunks: list[dict]) -> str:
    """知识库内容注入：作为写作方法论参考，不是内容来源"""
    if not knowledge_chunks:
        return ""
    chunks_text = "\n".join(
        f"· {c.get('content', '')[:200]}" for c in knowledge_chunks[:3]
    )
    return f"""〔知识库方法论参考〕
{chunks_text}"""


def _format_example_type_header(e: dict, content_format: str) -> str:
    parts = [
        FORMAT_NAMES.get(content_format, content_format),
        SECTION_TITLES.get(content_format, {}).get(e.get("section_type", ""), e.get("section_type", "")),
        AUDIENCE_NAMES.get(e.get("target_audience", ""), e.get("target_audience", "") or "面向大众"),
        PLATFORM_NAMES.get(e.get("platform", ""), e.get("platform", "") or "通用"),
    ]
    if e.get("specialty"):
        parts.append(SPECIALTY_NAMES.get(e["specialty"], e["specialty"]))
    return "示例类型：" + " / ".join(p for p in parts if p)


def _build_single_example(e: dict, content_format: str) -> str:
    header = _format_example_type_header(e, content_format)
    analysis = (e.get("analysis_text") or "").strip()

    if content_format in ("comic_strip", "storyboard", "card_series", "picture_book"):
        cj = e.get("content_json")
        if cj:
            try:
                obj = json.loads(cj) if isinstance(cj, str) else cj
                body = json.dumps(obj, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, TypeError):
                body = e.get("content", e.get("content_text", ""))
        else:
            body = e.get("content", e.get("content_text", ""))
    else:
        body = e.get("content", e.get("content_text", ""))

    blocks = [f"{header}\n\n---\n\n{body}"]
    if analysis:
        blocks.append(f"【分析】\n{analysis}")
    return "\n\n".join(blocks)


def _build_example_section(examples: list[dict], section_type: str, content_format: str = "article") -> str:
    if not examples:
        return ""
    examples_text = "\n\n---\n\n".join(
        _build_single_example(e, e.get("content_format", content_format))
        for i, e in enumerate(examples[:2])
    )
    return f"""〔风格示例〕
参考以下示例的语言风格、结构方式和表达技巧：

{examples_text}"""


def _build_term_section(terms: list[dict], target_audience: str) -> str:
    if not terms:
        return ""
    term_key = "term"
    if target_audience in ("student", "professional"):
        term_lines = [
            f"· {t.get(term_key, '')}（{t.get('abbreviation', '')}）"
            for t in terms[:12]
        ]
        return f"""〔术语规范〕
{chr(10).join(term_lines)}"""
    if target_audience == "children":
        term_lines = [
            f"· {t.get(term_key, '')}：小朋友的说法是「{t.get('layman_explain', '')}」。"
            + (f" 可以比喻成：{t.get('analogy', '')}" if t.get("analogy") else "")
            for t in terms[:6]
        ]
        return f"""〔儿童友好术语〕
{chr(10).join(term_lines)}"""
    term_lines = [
        f"· {t.get(term_key, '')}：通俗说法为「{t.get('layman_explain', '')}」。"
        + (f"推荐类比：{t.get('analogy', '')}" if t.get("analogy") else "")
        for t in terms[:10]
    ]
    return f"""〔术语通俗化规则〕
{chr(10).join(term_lines)}"""


def _build_specialty_section(
    config: dict | None,
    content_format: str,
    target_audience: str,
) -> str:
    if not config:
        return ""

    specialty_bg = config.get("specialty_context", "")
    key_diseases = config.get("key_diseases", [])
    avoid_topics = config.get("avoid_topics", [])
    hook_examples = config.get("hook_examples", [])
    children_analogies = config.get("children_analogies", [])

    if target_audience == "children":
        children_section = ""
        if children_analogies:
            children_section = (
                "\n本学科推荐的儿童友好类比（可在内容中自然融入）：\n"
                + "\n".join(f"  · {a}" for a in children_analogies[:3])
            )
        return "\n".join(
            filter(
                None,
                [
                    "〔学科背景（儿童版）〕",
                    specialty_bg,
                    f"核心病种：{', '.join(key_diseases)}" if key_diseases else "",
                    children_section,
                ],
            )
        )

    hook_formats = ("oral_script", "drama_script", "audio_script", "comic_strip")
    hook_section = ""
    if content_format in hook_formats and hook_examples:
        hook_section = (
            "\n本学科常用的开场钩子/第一格场景参考：\n"
            + "\n".join(f"  · {h}" for h in hook_examples[:3])
        )

    avoid_section = ""
    if avoid_topics:
        avoid_section = "\n禁止话题（不生成任何相关内容）：\n" + "\n".join(f"  · {t}" for t in avoid_topics)

    return "\n".join(
        filter(
            None,
            [
                "〔学科背景〕",
                specialty_bg,
                f"核心病种：{', '.join(key_diseases)}" if key_diseases else "",
                hook_section,
                avoid_section,
            ],
        )
    )


_GUIDELINE_NAME_MAP: dict[tuple[str, str], str] = {
    ("article", "intro"): "article_intro",
    ("article", "body"): "article_body",
    ("article", "case"): "article_case",
    ("article", "qa"): "article_qa",
    ("article", "summary"): "article_summary",
    ("article", "topic"): "topic_plan",
    ("article", "outline"): "outline",
    ("debunk", "rumor_present"): "debunk_rumor_present",
    ("debunk", "verdict"): "debunk_verdict",
    ("debunk", "debunk_1"): "debunk_point",
    ("debunk", "debunk_2"): "debunk_point",
    ("debunk", "debunk_3"): "debunk_point",
    ("debunk", "correct_practice"): "debunk_correct_practice",
    ("debunk", "anti_fraud"): "debunk_anti_fraud",
    ("qa_article", "qa_intro"): "qa_intro",
    ("qa_article", "qa_1"): "qa_single",
    ("qa_article", "qa_2"): "qa_single",
    ("qa_article", "qa_3"): "qa_single",
    ("qa_article", "qa_4"): "qa_single",
    ("qa_article", "qa_5"): "qa_single",
    ("qa_article", "qa_summary"): "qa_summary",
    ("story", "hook"): "story_hook",
    ("story", "development"): "story_development",
    ("story", "turning_point"): "story_turning_point",
    ("story", "science_core"): "story_science_core",
    ("story", "resolution"): "story_resolution",
    ("story", "action_list"): "story_action_list",
    ("story", "closing_quote"): "story_closing_quote",
    ("research_read", "one_liner"): "research_one_liner",
    ("research_read", "study_card"): "research_study_card",
    ("research_read", "why_matters"): "research_why_matters",
    ("research_read", "methods"): "research_methods",
    ("research_read", "findings"): "research_findings",
    ("research_read", "implication"): "research_implication",
    ("research_read", "limitation"): "research_limitation",
    ("oral_script", "script_plan"): "oral_script_plan",
    ("oral_script", "golden_hook"): "oral_golden_hook",
    ("oral_script", "problem_setup"): "oral_problem_setup",
    ("oral_script", "core_knowledge"): "oral_core_knowledge",
    ("oral_script", "practical_tips"): "oral_practical_tips",
    ("oral_script", "closing_hook"): "oral_closing_hook",
    ("oral_script", "extras"): "oral_extras",
    ("drama_script", "drama_plan"): "drama_plan",
    ("drama_script", "cast_table"): "drama_cast_table",
    ("drama_script", "act_1"): "drama_act",
    ("drama_script", "act_2"): "drama_act",
    ("drama_script", "act_3"): "drama_act",
    ("drama_script", "act_4"): "drama_act",
    ("drama_script", "act_5"): "drama_act",
    ("drama_script", "finale"): "drama_finale",
    ("drama_script", "filming_notes"): "drama_filming_notes",
    ("storyboard", "anim_plan"): "storyboard_anim_plan",
    ("storyboard", "char_design"): "storyboard_char_design",
    ("storyboard", "reel_1"): "storyboard_reel",
    ("storyboard", "reel_2"): "storyboard_reel",
    ("storyboard", "reel_3"): "storyboard_reel",
    ("storyboard", "reel_4"): "storyboard_reel",
    ("storyboard", "reel_5"): "storyboard_reel",
    ("storyboard", "prod_notes"): "storyboard_prod_notes",
    ("audio_script", "opening"): "audio_opening",
    ("audio_script", "topic_intro"): "audio_topic_intro",
    ("audio_script", "deep_dive"): "audio_deep_dive",
    ("audio_script", "extension"): "audio_extension",
    ("audio_script", "closing"): "audio_closing",
    ("card_series", "series_plan"): "card_content",
    ("card_series", "cover_card"): "card_content",
    ("card_series", "card_1"): "card_content",
    ("card_series", "card_2"): "card_content",
    ("card_series", "card_3"): "card_content",
    ("card_series", "card_4"): "card_content",
    ("card_series", "card_5"): "card_content",
    ("card_series", "card_6"): "card_content",
    ("card_series", "card_7"): "card_content",
    ("card_series", "ending_card"): "card_content",
    ("picture_book", "book_plan"): "picture_book_planner",
    ("picture_book", "cover"): "picture_book_page",
    ("picture_book", "spread_1"): "picture_book_page",
    ("picture_book", "spread_2"): "picture_book_page",
    ("picture_book", "spread_3"): "picture_book_page",
    ("picture_book", "spread_4"): "picture_book_page",
    ("picture_book", "spread_5"): "picture_book_page",
    ("picture_book", "spread_6"): "picture_book_page",
    ("picture_book", "spread_7"): "picture_book_page",
    ("picture_book", "back_cover"): "picture_book_page",
    ("poster", "poster_brief"): "poster_section",
    ("poster", "headline"): "poster_section",
    ("poster", "body_visual"): "poster_section",
    ("poster", "cta_footer"): "poster_section",
    ("poster", "design_spec"): "poster_section",
    ("long_image", "image_plan"): "long_image_planner",
    ("long_image", "title_block"): "long_image_section",
    ("long_image", "intro_block"): "long_image_section",
    ("long_image", "core_1"): "long_image_section",
    ("long_image", "core_2"): "long_image_section",
    ("long_image", "core_3"): "long_image_section",
    ("long_image", "core_4"): "long_image_section",
    ("long_image", "tips_block"): "long_image_section",
    ("long_image", "warning_block"): "long_image_section",
    ("long_image", "summary_cta"): "long_image_footer",
    ("long_image", "footer_info"): "long_image_footer",
    ("quiz_article", "quiz_intro"): "quiz_intro",
    ("quiz_article", "q_1"): "quiz_question",
    ("quiz_article", "q_2"): "quiz_question",
    ("quiz_article", "q_3"): "quiz_question",
    ("quiz_article", "q_4"): "quiz_question",
    ("quiz_article", "q_5"): "quiz_question",
    ("quiz_article", "summary"): "quiz_summary",
    ("h5_outline", "page_1"): "h5_page",
    ("h5_outline", "page_2"): "h5_page",
    ("h5_outline", "page_3"): "h5_page",
    ("h5_outline", "page_cover"): "h5_section",
    ("h5_outline", "page_end"): "h5_section",
}


def _load_writing_guideline(content_format: str, section_type: str) -> str:
    if content_format == "comic_strip":
        name = "planner" if section_type == "planner" else "panel"
        guideline = load_comic_guideline(name)
    elif content_format == "patient_handbook":
        hb_map = {
            "handbook_plan": "cover", "cover": "cover",
            "disease_know": "disease_intro", "treatment": "treatment",
            "daily_care": "daily_care", "followup": "visit_tips",
            "emergency": "symptoms", "faq": "fallback", "back_cover": "cover",
        }
        name = hb_map.get(section_type, "fallback")
        guideline = load_handbook_guideline(name)
    else:
        name = _GUIDELINE_NAME_MAP.get((content_format, section_type))
        guideline = load_task_guideline(name) if name else None
    if not guideline:
        return ""
    return f"""〔写作规范模板〕
{guideline}"""


# ════════════════════════════════════════════════════════════════
# Part 2 构建：内容事实来源
# ════════════════════════════════════════════════════════════════

async def _build_literature_section(
    lit_chunks: list[dict],
    content_format: str,
    paper_meta: dict[int, dict] | None = None,
    binding_order: list[int] | None = None,
) -> str:
    """结构化文献注入：按 binding 表 priority 顺序编号，保证与导出/前端一致"""
    if not lit_chunks:
        return ""

    if paper_meta is None:
        paper_meta = {}

    if content_format in SCRIPT_IMAGE_FORMATS:
        chunks_text = "\n".join(
            f"· {c.get('content', '')[:150]}..." for c in lit_chunks[:3]
        )
        return f"""以下内容来自用户选定的参考文献，用于确保内容准确性：
{chunks_text}"""

    by_paper: dict[int, list[dict]] = {}
    orphans: list[dict] = []
    for c in lit_chunks:
        pid = c.get("paper_id")
        if pid and pid in paper_meta:
            by_paper.setdefault(pid, []).append(c)
        else:
            orphans.append(c)

    ordered_pids = binding_order or list(by_paper.keys())
    pid_to_idx: dict[int, int] = {}
    for i, pid in enumerate(ordered_pids, 1):
        if pid not in pid_to_idx:
            pid_to_idx[pid] = i

    sections: list[str] = []
    for pid in ordered_pids:
        if pid not in by_paper:
            continue
        chunks = by_paper.pop(pid)
        idx = pid_to_idx[pid]
        meta = paper_meta[pid]
        authors_str = ", ".join(meta["authors"][:3])
        if len(meta["authors"]) > 3:
            authors_str += " et al."
        source = meta["journal"] or "未知来源"
        year = meta["year"] or "未知年份"
        evidence = meta.get("evidence_level", "其他")

        content_parts = "\n".join(
            f"  {c.get('content', '')[:300]}" for c in chunks[:3]
        )

        block = f"""### 文献{idx}
- 编号：[{idx}]
- 标题：{meta['title']}
- 作者：{authors_str}
- 来源：{source}
- 发表时间：{year}
- 证据等级：{evidence}
- 核心内容：
{content_parts}"""
        sections.append(block)

    extra_idx = len(ordered_pids) + 1
    for pid, chunks in by_paper.items():
        meta = paper_meta.get(pid)
        if meta:
            content_parts = "\n".join(f"  {c.get('content', '')[:300]}" for c in chunks[:3])
            block = f"""### 文献{extra_idx}
- 编号：[{extra_idx}]
- 标题：{meta['title']}
- 核心内容：
{content_parts}"""
        else:
            content_parts = "\n".join(f"  {c.get('content', '')[:300]}" for c in chunks[:3])
            block = f"""### 文献{extra_idx}
- 编号：[{extra_idx}]
- 核心内容：
{content_parts}"""
        sections.append(block)
        extra_idx += 1

    for c in orphans:
        content = c.get("content", "")[:300]
        block = f"""### 文献{extra_idx}
- 编号：[{extra_idx}]
- 核心内容：
  {content}"""
        sections.append(block)
        extra_idx += 1

    return "\n\n".join(sections)


def _build_analysis_report_block(analysis_report: dict | None) -> str:
    """文献分析报告注入"""
    if not analysis_report:
        return ""
    parts = []
    if analysis_report.get("research_topic"):
        parts.append(f"核心研究主题：{analysis_report['research_topic']}")
    if analysis_report.get("key_findings"):
        findings = "\n".join(f"  - {f}" for f in analysis_report["key_findings"])
        parts.append(f"关键发现：\n{findings}")
    if analysis_report.get("methodology_summary"):
        parts.append(f"研究方法：{analysis_report['methodology_summary']}")
    if analysis_report.get("population"):
        parts.append(f"研究对象：{analysis_report['population']}")
    if analysis_report.get("clinical_significance"):
        parts.append(f"临床意义：{analysis_report['clinical_significance']}")
    if analysis_report.get("key_data_points"):
        data_lines = "\n".join(
            f"  - {d.get('label', '')}: {d.get('value', '')} (来源: {d.get('source', '')})"
            for d in analysis_report["key_data_points"]
        )
        parts.append(f"核心数据：\n{data_lines}")
    if analysis_report.get("writing_angles"):
        angles = "\n".join(f"  - {a}" for a in analysis_report["writing_angles"])
        parts.append(f"推荐写作角度：\n{angles}")
    if analysis_report.get("limitations"):
        lims = "\n".join(f"  - {l}" for l in analysis_report["limitations"])
        parts.append(f"研究局限性（写作时须客观提及）：\n{lims}")
    if not parts:
        return ""
    body = "\n".join(parts)
    return f"""### 文献分析报告（基于上述文献的结构化分析）

{body}

约束：分析报告中的数据和结论均源自上方文献，可直接引用。报告未覆盖的方面，用 [[待补充：需要关于XX的文献支持]] 占位。"""


# ════════════════════════════════════════════════════════════════
# Part 3 构建：写作任务
# ════════════════════════════════════════════════════════════════

_QA_SECTION_TYPES = {"qa", "qa_intro", "qa_1", "qa_2", "qa_3", "qa_4", "qa_5", "qa_summary"}
_SUMMARY_SECTION_TYPES = {"summary", "qa_summary", "cta"}
_STORY_SECTION_TYPES = {"hook", "development", "turning_point", "science_core",
                        "resolution", "action_list", "closing_quote"}
_DEBUNK_SECTION_TYPES = {"rumor_present", "verdict", "debunk_1", "debunk_2", "debunk_3",
                         "correct_practice", "anti_fraud"}

def _build_prior_sections_block(prior_sections_context: str, section_type: str = "",
                                content_format: str = "") -> str:
    if not prior_sections_context:
        return ""

    if content_format == "qa_article" and section_type in _QA_SECTION_TYPES:
        return f"""## 前序问答内容（严格保持问答链连贯性，严禁重复）
{prior_sections_context}

▌问答科普连贯性强制要求（逐条检查）

1. 问题角度不重复
   - 阅读前序已生成的所有问题，本题必须从完全不同的角度切入
   - 不能换个说法问同一个事——如果前序问了"能不能XX"，不能再问"XX行不行"

2. 回答内容不重复
   - 前序已经解释过的知识点、类比、数据，后续问答不得重复
   - 如果前序用了某个比喻，后续必须用不同的比喻

3. 层级递进
   - 问题链从入门→进阶→实操→特殊情况，逐步深入
   - 后续问答可以建立在前序的基础上，但不能重复内容

4. 阅读节奏
   - 可以在回答末尾自然引出下一个问题的方向，形成连贯的阅读体验"""

    if section_type in _QA_SECTION_TYPES:
        return f"""## 前序内容（Q&A 必须与正文互补，严禁重复）
{prior_sections_context}

Q&A 去重要求：正文已阐述的知识点不得再次解释；问题须是读者看完正文后仍有的新疑惑。"""

    if section_type in _SUMMARY_SECTION_TYPES:
        return f"""## 前序内容（小结必须与正文互补，严禁复述）
{prior_sections_context}

小结去重要求：
- 正文中已出现的知识点解释、类比、数据、行动建议，不得在小结中重复出现
- 小结应从更高视角提炼 1-2 个核心认知，而非逐条复述正文
- 行动要点须用全新的精炼语言，不能照搬正文原句"""

    if content_format == "story" and section_type in _STORY_SECTION_TYPES:
        return f"""## 前序故事内容（严格保持叙事连贯性）
{prior_sections_context}

▌叙事连贯性强制要求（逐条检查）

1. 人物一致性
   - 主角姓名、化名、年龄、职业、性别、家庭关系必须与前序内容完全一致，不得出现新名字或属性矛盾
   - 配角（家属、同事、医生）如已出场，后续出现时身份信息不能变化

2. 情节因果链
   - 本节内容必须自然承接前序最后的情节状态，不能跳过或遗忘已发生的事件
   - 如前序提到某个症状/事件，后续不能当它没发生过
   - 时间线要连贯：不能突然从白天跳到三个月后而不加交代

3. 情感弧线递进
   - 读者的情绪是被前序一步步建立的，本节必须延续并推进这条弧线
   - 不能出现情绪跳跃（如前序还在紧张，本节突然轻松，中间缺少过渡）

4. 医学信息一致
   - 前序提及的疾病/症状名称、诊断结论必须前后统一
   - 已经由医生说过的话不要换个人重复说

5. 过渡与衔接
   - 本节的第一句/第一段必须让读者感觉是前序自然延续，而非另起一篇文章
   - 可通过时间推移（"第二天"）、场景切换（"走出诊室"）、情绪延续（"心里还是放不下"）等方式过渡"""

    if content_format == "debunk" and section_type in _DEBUNK_SECTION_TYPES:
        return f"""## 前序辟谣内容（严格保持逻辑一致性，不得矛盾或重复）
{prior_sections_context}

▌辟谣文连贯性强制要求（逐条检查）

1. 谣言指代一致性
   - 全文针对的是同一条谣言，后续章节不能偏离或混入其他谣言
   - 谣言原文只在"谣言还原"中完整呈现一次，后续用简短指代（"前述说法""该谣言"）

2. 论据不重复（严格检查）
   - 阅读前序拆解内容，提取已使用的：漏洞类型、核心论点、类比、证据来源
   - 当前章节必须使用完全不同的漏洞类型和论证角度
   - 如果前序用了"偷换概念"，本条必须选择"剂量忽略""事实错误""恐惧利用"等其他类型
   - 前序已经使用过的类比（如"面粉≠面包""食盐中毒"），后续绝对不能重复使用

3. 结论一致性
   - "真相判定"中给出的判定结论（纯属谣言/夸大/张冠李戴/过时）贯穿全文
   - 后续拆解和正确做法必须与判定结论逻辑自洽，不能自相矛盾

4. 语气一致性
   - 全文保持"帮助读者理解"的友善语气，不出现嘲讽、说教
   - 前序如果用了某种风格（如轻松幽默/严肃权威），后续保持一致

5. 证据层级递进
   - 拆解点之间有层次感：从最明显的漏洞到较深层的问题
   - "正确做法"是在全部拆解完成后的行动指引，不提前泄露"""

    if content_format == "long_image" and section_type not in ("image_plan",):
        return f"""## 前序区块内容（保持长图的信息递进与视觉一致性）
{prior_sections_context}

▌竖版长图连贯性要求
1. 信息不重复：前序区块已讲的知识点/数据/建议，后续区块不重复
2. 配色一致：image_prompt 的色调描述与 image_plan 定义的 color_theme 一致
3. 逻辑递进：区块间有明确的信息递进关系（认知→理解→行动）
4. 每块独立：即使读者跳读，每个区块也能独立成立
5. 正文短句：控制每段不超过3行，正文用数字/动词开头"""

    if content_format == "picture_book" and section_type not in ("book_plan",):
        return f"""## 前序绘本内容（严格保持绘本故事与视觉连贯性）
{prior_sections_context}

▌科普绘本连贯性强制要求
1. 角色一致：主角和配角的名字、外貌、标志物、性格与 book_plan 和前序页完全一致
2. 叙事连贯：每个跨页只推进一个情节节点，且必须自然承接前一跨页的结尾
3. 画风统一：illustration_desc 的风格关键词（画风、配色、氛围）前后一致
4. 翻页悬念：前一跨页的 page_turn_hook 必须在本跨页得到回应/揭晓
5. 知识嵌入自然：知识点通过角色行动/对话带出，不突然切换为"科普模式"
6. 情绪递进：情绪基调要有变化弧线（好奇→困惑→发现→喜悦），不能平铺直叙
7. 文字节奏：page_text 风格保持一致——如果前序用了短句+感叹号的节奏，后续延续"""

    if content_format == "card_series" and section_type not in ("series_plan",):
        return f"""## 前序卡片内容（保持系列视觉与内容连贯性）
{prior_sections_context}

▌知识卡片系列连贯性要求
1. 视觉统一：配色、字体风格、图标风格与 series_plan 定义的保持一致
2. 编号连续：卡片编号必须与系列规划一致
3. 知识不重复：前序卡片已讲过的知识点，后续卡不重复
4. 信息密度一致：每张卡的信息量保持均衡，不出现前密后疏
5. illustration_desc 风格统一：所有卡片的配图描述保持相同的画风关键词"""

    if content_format == "oral_script" and section_type not in ("script_plan",):
        return f"""## 前序脚本内容（严格保持口播脚本的节奏与内容连贯性）
{prior_sections_context}

▌口播脚本连贯性强制要求
1. 人设一致：出镜人的身份、口吻风格、第一人称与 script_plan 完全一致
2. 信息不重复：前序段落已讲过的知识点/数据/建议，后续不重复
3. 节奏递进：开头→铺垫→科普→建议→收尾，信息密度与情绪有明确弧线
4. 口语统一：全段用"因为""所以""但是"，不用"由于""因此""然而"
5. 自然过渡：前段结尾与本段开头之间有自然衔接语，像在同一次录制中
6. 句子短：每句≤20字，让观众跟得上
7. 一个视频一个知识点：不贪多，不偏离 script_plan 的核心知识点"""

    if content_format == "drama_script" and section_type not in ("drama_plan", "cast_table"):
        return f"""## 前序剧本内容（严格保持情景剧的叙事连贯性与角色一致性）
{prior_sections_context}

▌情景剧本连贯性强制要求
1. 角色一致：角色姓名、身份、性格、外在表现与 cast_table 完全一致，不新增角色
2. 情节因果链：本场必须自然承接前一场的结尾状态，不跳过已发生的事件
3. 剧情弧线：日常建立→冲突触发→错误应对→专业介入→结局升华，每场只推进一个节拍
4. 台词风格一致：对白像"这个人真的会说的话"，不是念课文，保持口语化
5. 知识不重复：前序场景已传递的知识点，后续不重复
6. 医生角色不要"全知全能"：从倾听开始再给建议，不满口术语
7. 搞笑可以有，但不消解健康问题的严肃性"""

    if content_format == "storyboard" and section_type.startswith("reel_"):
        return f"""## 前序分镜内容（严格保持动画分镜的视觉与叙事连贯性）
{prior_sections_context}

▌动画分镜连贯性强制要求
1. 角色/元素一致：角色形象、拟人化方案与 char_design 完全一致，不新增不在设定中的视觉元素
2. 画面-旁白同步：旁白和画面必须同步对应，不能"说A画面还在B"
3. 景别节奏：景别要有变化（全景/中景/近景/特写交替），避免全程中景
4. 信息密度控制：每镜画面停留2-4秒，信息量不能太大
5. 旁白节奏：每句间留0.5-1秒气口，观众需要呼吸，核心段旁白速度放慢
6. 可视化比喻一致：机制解释段使用的可视化比喻前后统一
7. 知识不重复：前序幕已讲过的知识点后续不重复
8. 色调风格一致：画面色调和动画风格与 anim_plan 设定一致"""

    if content_format == "comic_strip" and section_type.startswith("panel_"):
        return f"""## 前序格内容（严格保持条漫的视觉与叙事连贯性）
{prior_sections_context}

▌条漫连贯性强制要求
1. 角色一致：角色的名字、外貌（服装/发型/标志物）、称呼必须与planner和前序格完全一致
2. 叙事承接：本格必须自然衔接前一格的情节，不跳跃、不矛盾
3. 画风统一：scene_desc 的风格描述（色调、画风）与前序格保持一致
4. 知识不重复：前序格已讲过的知识点，本格不重复，每格只讲一个新知识点
5. 对白风格统一：前序格如果是轻松口语风格，后续不突然变成学术腔"""

    _HB_CONTENT_TYPES = {"disease_know", "treatment", "daily_care", "followup", "emergency", "faq"}
    if content_format == "patient_handbook" and section_type in _HB_CONTENT_TYPES:
        return f"""## 前序手册内容（严格保持患者手册的信息一致性与实用导向）
{prior_sections_context}

▌患者手册连贯性强制要求
1. 疾病信息一致：前序部分提及的疾病名称、病因、严重程度描述后续不得矛盾
2. 称呼统一：全程用"你"称呼患者，不用"患者应当"
3. 语言直白：所有医学术语必须配通俗解释，或直接用大白话替代
4. 不提及具体药物名称或剂量：用药清单由患者/医生填写
5. 勾选框和表格：充分利用⬜勾选框和表格，手册是被"用"的
6. 结论一致：前序"可控"的信心基调贯穿全文，不自相矛盾"""

    _RESEARCH_READ_TYPES = {"one_liner", "study_card", "why_matters", "methods",
                             "findings", "implication", "limitation"}
    if content_format == "research_read" and section_type in _RESEARCH_READ_TYPES:
        return f"""## 前序内容（严格保持研究速读的信息一致性）
{prior_sections_context}

▌研究速读连贯性要求
1. 数据一致：前序提及的研究数据（样本量、随访时间、关键数字）后续引用时不能变化
2. 结论递进：一句话摘要→核心发现→对普通人的意义，信息逐步展开但不矛盾
3. 不提前泄露：背景和方法部分不透露结果，结果部分不讨论局限
4. 证据强度一致：对同一发现的因果/相关性判断前后统一"""

    if content_format == "article":
        return f"""## 前序章节内容（⚠️ 必读——当前章节必须基于以下内容进行写作）
{prior_sections_context}

▌⚠️ 章节衔接规则（逐条检查，任何一条不通过都必须修改）

1. 🔗 各章节职责边界
   - 正文：开篇引入话题 + 讲解知识、分析原理、给出证据
   - 小结：提炼行动要点，不重复正文讲过的知识

2. 🚫 严禁重复（前序已写过的内容不得出现）
   - 前序已使用的比喻、类比、具体数据、案例场景，当前章节不得出现
   - 前序已解释过的概念，当前章节可直接使用不必再次解释

3. 📖 全文一体感
   - 读者读完全部章节后应感到是同一篇文章，而非拼凑的几篇独立短文
   - 语气风格、术语使用、指代方式保持一致"""

    return f"""## 前序内容（保持一致性，不得矛盾或重复）
{prior_sections_context}"""


_CONTENT_FORMAT_TO_ARTICLE_TYPE: dict[str, tuple[str, str]] = {
    "article": ("疾病科普", "模板A"),
    "debunk": ("辟谣纠正", "模板B"),
    "qa_article": ("问答科普", "模板D"),
    "story": ("健康行为", "模板C"),
    "research_read": ("研究速读", "模板E"),
    "oral_script": ("口播脚本", "短视频口播"),
    "drama_script": ("情景剧本", "短视频情景剧"),
    "audio_script": ("其他", "自定义"),
    "comic_strip": ("条漫科普", "条漫模板"),
    "storyboard": ("动画分镜", "科普动画分镜"),
    "card_series": ("知识卡片", "卡片模板"),
    "picture_book": ("科普绘本", "绘本模板"),
    "poster": ("科普海报", "海报模板"),
    "long_image": ("竖版长图", "长图模板"),
    "quiz_article": ("其他", "自定义"),
    "h5_outline": ("其他", "自定义"),
    "patient_handbook": ("患者教育手册", "患者手册模板"),
}

_AUDIENCE_TO_KNOWLEDGE_LEVEL: dict[str, str] = {
    "public": "无医学背景",
    "patient": "有基础健康知识",
    "student": "有一定医学基础",
    "professional": "有一定医学基础",
    "children": "无医学背景",
}

_AUDIENCE_TO_TONE: dict[str, str] = {
    "public": "亲和平易",
    "patient": "亲和平易",
    "student": "专业严谨",
    "professional": "专业严谨",
    "children": "轻松活泼",
}


_TEMPLATE_SECTION_MAPPING: dict[str, dict[str, str]] = {
    "article": {
        "body": "正文（开篇引入 + 按主题自由组织小节）",
        "case": "穿插在正文中的案例/场景",
        "qa": "补充 Q&A，内容须与正文互补",
        "summary": "小结（行动建议 + 就医提示）",
    },
    "debunk": {
        "rumor_present": "标题 + 谣言还原（完整呈现谣言原文、传播场景、为何听起来有道理）",
        "verdict": "真相判定（一句话结论前置：纯属谣言/严重夸大/张冠李戴/过时信息）",
        "debunk_1": "逐条拆解·漏洞1（谣言说法 → 事实是 → 证据来源）",
        "debunk_2": "逐条拆解·漏洞2（谣言说法 → 事实是 → 证据来源）",
        "debunk_3": "逐条拆解·漏洞3（谣言说法 → 事实是 → 证据来源）",
        "correct_practice": "正确做法（可操作建议 + 就医信号 + 权威参考）",
        "anti_fraud": "防骗指南（3条通用谣言辨别方法）",
    },
}


_READING_LEVEL_LABELS = {
    "easy": "简单易懂（小学高年级可读）",
    "normal": "适中（普通成人可理解）",
    "advanced": "较深入（有一定医学常识的读者）",
}


def _build_article_meta_block(
    topic: str,
    content_format: str,
    section_type: str,
    target_audience: str,
    platform: str,
    target_word_count: int | None = None,
    tone: str | None = None,
    reading_level: str | None = None,
) -> str:
    """结构化文章元信息，对应参考架构 Part 3 的「文章基本信息」"""
    format_name = FORMAT_NAMES.get(content_format, content_format)
    section_name = SECTION_TITLES.get(content_format, {}).get(section_type, section_type)
    audience_name = AUDIENCE_NAMES.get(target_audience, target_audience)
    platform_name = PLATFORM_NAMES.get(platform, platform)

    article_type, template_name = _CONTENT_FORMAT_TO_ARTICLE_TYPE.get(
        content_format, ("其他", "自定义")
    )
    knowledge_level = _AUDIENCE_TO_KNOWLEDGE_LEVEL.get(target_audience, "无医学背景")
    resolved_tone = tone or _AUDIENCE_TO_TONE.get(target_audience, "亲和平易")

    _PLATFORM_DEFAULT_WC = {
        "wechat": 1200, "xiaohongshu": 800, "douyin": 300,
        "journal": 3000, "offline": 2000,
    }
    effective_wc = target_word_count or _PLATFORM_DEFAULT_WC.get(platform, 1500)
    word_count_str = f"全文严格控制在 {effective_wc} 字以内"

    template_hint = _TEMPLATE_SECTION_MAPPING.get(content_format, {}).get(section_type, "")
    mapping_line = f"\n- 当前章节对应模板位置：{template_hint}" if template_hint else ""

    return f"""## 文章基本信息
- 主题：{topic}
- 文章类型：{article_type}
- 对应模板：{template_name}
- 内容形式：{format_name}
- 当前章节：{section_name}{mapping_line}
- 目标读者：{audience_name}
- 读者知识水平：{knowledge_level}
- 目标字数：{word_count_str}
- 语气风格：{resolved_tone}
- 阅读难度：{_READING_LEVEL_LABELS.get(reading_level or "normal", reading_level or "适中")}
- 发布平台：{platform_name}"""


# ════════════════════════════════════════════════════════════════
# 主装配函数
# ════════════════════════════════════════════════════════════════

async def build_enhanced_prompt(
    base_prompt: str,
    topic: str,
    section_type: str,
    content_format: str,
    target_audience: str = "public",
    platform: str = "wechat",
    specialty: str | None = None,
    article_id: int | None = None,
    rag_context: list[dict] | None = None,
    examples: list[dict] | None = None,
    domain_terms: list[dict] | None = None,
    specialty_config: dict | None = None,
    prior_sections_context: str = "",
    user_id: int | None = None,
    analysis_report: dict | None = None,
    target_word_count: int | None = None,
    tone: str | None = None,
    reading_level: str | None = None,
) -> tuple[str, dict]:
    """
    四层 Prompt 架构 — User Message 装配（Part 1 + Part 2 + Part 3）。
    Layer 0-1 由 base.py 的 _build_system_prompt 负责。
    返回 (prompt, meta)
    """
    meta = {"ollama_unavailable": False}

    # ── 文献通道（Part 2 的内容来源）──
    if rag_context is None:
        lit_chunks, ollama_unavailable = await rag_retriever.retrieve_literature(
            query=f"{topic} {section_type}",
            article_id=article_id,
            section_type=section_type,
            top_k=5 if content_format not in SCRIPT_IMAGE_FORMATS else 3,
        )
        meta["ollama_unavailable"] = ollama_unavailable
    else:
        lit_chunks = rag_context

    # ── 获取 binding 顺序和文献元数据（用于 Part 2 结构化注入）──
    binding_order = await _fetch_binding_order(article_id)
    paper_ids = list({c.get("paper_id") for c in lit_chunks if c.get("paper_id")})
    all_ids = list(set(binding_order) | set(paper_ids))
    paper_meta = await _fetch_paper_meta(all_ids)

    # ── 知识通道（Part 1 的能力增强）──
    knowledge_chunks = await rag_retriever.retrieve_knowledge(
        query=f"{topic} {section_type}",
        specialty=specialty,
        top_k=3,
    )

    # ── Few-shot ──
    if examples is None:
        examples = await example_retriever.retrieve(
            content_format=content_format,
            section_type=section_type,
            target_audience=target_audience,
            platform=platform,
            specialty=specialty or None,
            top_k=2,
        )

    # ── 术语 ──
    if domain_terms is None:
        domain_terms = await term_injector.get_terms_for_audience(
            topic=topic,
            target_audience=target_audience,
            specialty=specialty,
            top_k=12 if target_audience in ("student", "professional") else 10,
        )

    uid = user_id if user_id is not None else 1
    personal_section = await _personal_corpus_section(uid)
    resolved_config = _resolve_specialty_config(specialty, specialty_config)

    # ════════════════════════════════════════════════════════════════
    # Part 1: 写作能力增强（教你怎么写）
    # 按章节裁剪以控制后期章节的 token 预算：
    #   完整注入：intro / body / case / debunk_* / rumor_present / verdict 等主体章节
    #   精简注入：qa / summary / anti_fraud / correct_practice —— 不需要结构模板和知识库方法论
    # ════════════════════════════════════════════════════════════════
    _LIGHT_SECTIONS = {"qa", "summary", "closing_quote", "action_list", "resolution",
                        "anti_fraud", "correct_practice", "qa_summary", "qa_intro",
                        "one_liner", "study_card", "limitation", "series_plan",
                        "cover_card", "ending_card", "poster_brief", "design_spec",
                        "cta_footer", "book_plan", "cover", "back_cover",
                        "image_plan", "footer_info", "summary_cta", "warning_block",
                        "script_plan", "closing_hook", "extras",
                        "drama_plan", "cast_table", "finale", "filming_notes",
                        "anim_plan", "char_design", "prod_notes",
                        "handbook_plan", "cover", "back_cover", "faq"}
    is_light = section_type in _LIGHT_SECTIONS

    from app.agents.prompts.audiences import resolve_writing_style
    _style = resolve_writing_style(platform, target_audience)
    _style_rules_text = (
        f"- 语域：{_style['register']}\n"
        f"- 术语密度：{_style['terminology']}\n"
        f"- 句式：{_style['sentence_style']}\n"
        f"- 情感色彩：{_style['emotion']}\n"
        f"- 禁止：{_style['forbidden']}"
    )
    rhythm_rules = _PARAGRAPH_RHYTHM_RULES.format(style_rules=_style_rules_text)

    if is_light:
        p1_parts = list(filter(None, [
            _LANGUAGE_TRANSFORM_RULES,
            rhythm_rules,
            personal_section,
            _load_writing_guideline(content_format, section_type),
        ]))
    else:
        p1_parts = list(filter(None, [
            _LANGUAGE_TRANSFORM_RULES,
            _STRUCTURE_TEMPLATES,
            _build_term_section(domain_terms, target_audience),
            _build_example_section(examples, section_type, content_format),
            rhythm_rules,
            _build_knowledge_section(knowledge_chunks),
            personal_section,
            _build_specialty_section(resolved_config, content_format, target_audience),
            _load_writing_guideline(content_format, section_type),
        ]))

    part1 = ""
    if p1_parts:
        part1 = f"""═══ 写作能力增强 ═══
【声明】以下内容用于提升写作质量，提供写作方法和范式参考。
本区域不是内容来源。具体约束：
- 本区域中出现的任何具体数字、实验结果、统计数据不得出现在正文中，
  除非在「内容事实来源」的文献中也能找到对应来源
- 如果本区域的术语用法与系统规则的证据语言规则冲突，以系统规则为准
- 如果本区域的内容与「内容事实来源」的文献有事实性矛盾，以文献为准
═══════════════════

{chr(10).join(p1_parts)}"""

    # ════════════════════════════════════════════════════════════════
    # Part 2: 内容事实来源（告诉你写什么）
    # ════════════════════════════════════════════════════════════════
    lit_section = await _build_literature_section(lit_chunks, content_format, paper_meta, binding_order)
    report_section = _build_analysis_report_block(analysis_report)
    p2_parts = list(filter(None, [lit_section, report_section]))

    _READER_FACING_P2 = {"article", "qa_article", "debunk", "story", "research_read",
                         "comic_strip", "card_series", "poster", "picture_book", "long_image",
                         "oral_script", "drama_script", "storyboard", "patient_handbook"}
    _is_reader_p2 = content_format in _READER_FACING_P2

    if p2_parts:
        if _is_reader_p2:
            _citation_mode = _style.get("citation_mode", "bracket_n") if _style else "bracket_n"
            if _citation_mode == "inline_name":
                p2_citation_rule = (
                    "引用方式：不使用[N]角标。引用文献时在正文中直接写出来源名称"
                    "（如'根据《中国血脂管理指南（2023）》''一项发表在《柳叶刀》的研究'）。\n"
                    "下方文献仅供你获取事实和数据，正文中不要出现[1][2]等角标。\n"
                    "如果以下文献不足以支撑写作任务的某些部分，直接用定性描述代替，不要留任何占位符标签。"
                )
            elif _citation_mode == "none":
                p2_citation_rule = (
                    "引用方式：不使用任何引用标注和文献名称。数据用口语化表述。\n"
                    "下方文献仅供你获取事实和数据，正文中不要出现[1][2]等角标，也不要提文献名。\n"
                    "如果以下文献不足以支撑写作任务的某些部分，直接用定性描述代替，不要留任何占位符标签。"
                )
            else:
                p2_citation_rule = (
                    "[N] 引用精准使用：只在关键论断（具体数据、反常识结论、治疗建议的循证依据）处标注，"
                    "每段角标不超过 2-3 个。常识、定义、逻辑推理不标。N 为下方文献序号。\n"
                    "如果以下文献不足以支撑写作任务的某些部分，直接用定性描述代替，不要留任何占位符标签。"
                )
        else:
            p2_citation_rule = (
                "文献编号仅供你内部参考以定位内容来源，正文中不要输出[文献1]等编号标注（由系统自动处理）。\n"
                "如果以下文献不足以支撑写作任务的某些部分，使用 [[待补充：需要关于XX的文献支持]] 占位，不得从其他来源补充。"
            )
        part2 = f"""═══ 内容事实来源 ═══
【声明】以下文献是本次写作任务的唯一事实性内容来源。
正文中基于文献的事实性陈述必须来自以下文献。
{p2_citation_rule}
═══════════════════

{chr(10).join(p2_parts)}"""
    else:
        if _is_reader_p2:
            part2 = """═══ 内容事实来源 ═══
当前无可用文献。请基于公认医学知识撰写，用自然语言表达来源可信度（如"医学指南建议""目前普遍认为"），不得自行编造数据或引用来源。
═══════════════════"""
        else:
            part2 = """═══ 内容事实来源 ═══
当前无可用文献。所有内容将标注为[共识]或[[待补充]]，不得自行编造数据或引用来源。
═══════════════════"""

    # ════════════════════════════════════════════════════════════════
    # Part 3: 写作任务（具体执行什么）
    # ════════════════════════════════════════════════════════════════
    meta_block = _build_article_meta_block(
        topic=topic,
        content_format=content_format,
        section_type=section_type,
        target_audience=target_audience,
        platform=platform,
        target_word_count=target_word_count,
        tone=tone,
        reading_level=reading_level,
    )
    prior_block = _build_prior_sections_block(prior_sections_context, section_type, content_format)

    p3_parts = list(filter(None, [meta_block, prior_block, base_prompt]))

    _READER_FACING_FORMATS = {
        "article", "qa_article", "debunk", "story", "research_read",
        "comic_strip", "card_series", "poster", "picture_book", "long_image",
        "oral_script", "drama_script", "storyboard", "patient_handbook",
    }
    is_reader_facing = content_format in _READER_FACING_FORMATS

    if is_reader_facing:
        _exec_citation_mode = _style.get("citation_mode", "bracket_n") if _style else "bracket_n"
        if _exec_citation_mode == "inline_name":
            citation_and_annotation = """2. 不使用[N]角标。引用文献时在正文中直接写出来源名称（如'根据《XX指南》''《柳叶刀》的一项研究'），让读者知道来源但不打断阅读
3. 🚨 禁止内部标签：不输出 [共识]、[推断]、[推断:基于XX]、[文献X]、[[待补充]]、[DATA:...]、[1]、[2] 等任何角标。文献不足时用定性描述代替"""
        elif _exec_citation_mode == "none":
            citation_and_annotation = """2. 不使用任何引用标注。数据用口语化表述，不提文献名称
3. 🚨 禁止内部标签：不输出 [共识]、[推断]、[推断:基于XX]、[文献X]、[[待补充]]、[DATA:...]、[1]、[2] 等任何角标或文献名。文献不足时用定性描述代替"""
        else:
            citation_and_annotation = """2. [N] 精准标注：只标在关键数据和核心结论上（读者会问"凭什么？"的地方），每段≤3个角标。常识、定义、逻辑推理不标。公认知识用自然语言归属（"研究显示""指南建议"），不加编号
3. 🚨 禁止内部标签：不输出 [共识]、[推断]、[推断:基于XX]、[文献X]、[[待补充]]、[DATA:...]。文献不足时用定性描述代替"""
    else:
        citation_and_annotation = """2. 文献引用编号由系统自动处理，正文不要添加[1][2]等编号；可自然标注来源归属（"研究显示""指南建议"）
3. 公认医学知识句末标注[共识]，推断性内容标注[推断:基于XX]，文献不足时用 [[待补充：需要XX类型的文献支持]] 占位"""

    part3 = f"""═══ 写作任务 ═══

{chr(10).join(p3_parts)}

## 执行指令
仅基于上方「内容事实来源」中的文献生成当前章节。

1. 严格遵守字数限制（见上方「写作要求」），宁可精炼不可超字
{citation_and_annotation}
4. 不附参考文献列表（由系统自动处理）
5. 禁止输出元数据（"主题：…""形式：…""平台：…"）和空占位标题（"# 案例""# Q&A"）

## ⛔ 输出前强制自检（全部通过才可输出）
逐条检查，任何一条不通过必须修改后再输出：

【硬性红线检查——这些问题后续改写无法修复】
□ 事实准确：每个具体数字/结论都能追溯到「内容事实来源」或标注为公认知识
□ 引用精准不过密：[N]只标在关键数据和核心结论上，每段≤3个角标。常识/定义/逻辑推理不标
□ 无编造数据：搜索全文中的百分比、数字、年份——每个都有来源

【信息递进与结构检查——AI文本最典型的问题】
□ 章节边界清晰：正文包含开篇引入 + 知识讲解；小结只提炼行动要点，不重复正文知识
□ 信息递进：逐句检查——每句话是否提供了前一句没有的新信息？如有同义复述，合并或删除
□ 句式多样：段内没有连续3句结构相同（如都是"A由B导致"）。长短句交替，字数差≥15字
□ 无名词化公文腔："聚焦于""进行了探讨""存在的偏差""具有意义"——改为动词主导的自然句
□ 引用位置正确：[N]只在具体论断（带数据/结论）上标注，常识性陈述不标

【语域与信息密度检查】
□ 语域一致：全文风格统一，不能混用不同语域（如口语吐槽+学术引用并存）
□ 无空洞铺垫：删掉所有"常识铺垫"句（"很多人都有过这种经历""这个问题值得关注"）
□ 概念有界定：关键概念首次出现时有明确定义或分类，不能只给比喻不给术语
□ 信息密度：搜索"显著""广泛""重要""关键""多种"——能换成具体数字/名称的必须换

【模板与套路检查】
□ 无三项并列：搜索"一是""二是""三是""首先""其次""最后"，改为两项或拆成独立句
□ 无"不是A而是B"：搜索"不是为了""并非""而是为了"，直接说B
□ 无虚假强调：搜索"更值得注意""值得一提""需要指出"，删除前缀
□ 无导游腔：搜索"这篇文章""让我们""带你了解""一起来看"，删除
□ 末段是行动/事实：最后一段是具体建议或事实陈述，不是总结升华
□ 安全声明 ≤ 1句：搜索"请咨询""仅供参考""专业评估"，仅保留文末一句

⚠ 事实性陈述的依据只能来自「内容事实来源」区域，「写作能力增强」区域仅供参考写法。"""

    # ── 合并 ──
    final_parts = list(filter(None, [part1, part2, part3]))
    return "\n\n\n".join(final_parts), meta

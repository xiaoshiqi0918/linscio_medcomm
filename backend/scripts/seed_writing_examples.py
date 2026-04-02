"""P0 Few-shot 示例种子数据 - article / oral_script / comic_strip / patient_handbook

符合规范 13.1-13.4 的模板格式：示例类型、【高质量示例】、【分析】
条漫使用 content_json（scene_desc 英文）
"""
import asyncio
import json
from app.core.database import AsyncSessionLocal
from app.models.example import WritingExample

# 条漫 JSON 示例（13.3 规范）
COMIC_PANEL_JSON = {
    "panel_index": 3,
    "scene_desc": "A middle-aged woman holding a blood glucose meter with a confused expression, sitting at a kitchen table with breakfast foods visible. A thought bubble shows question marks. Clean flat illustration style, warm kitchen lighting, Chinese home setting.",
    "dialogue": "这个数字高了？我明明没吃甜的啊……",
    "narration": "王阿姨看着血糖仪，满脸疑惑",
    "caption": "血糖升高不只因为吃甜食",
    "visual_notes": "王阿姨的表情要体现困惑而非恐慌，早餐要看起来「健康」（粥/鸡蛋）以强调误区",
}

# 完整模板示例（含 analysis_text）
TEMPLATE_EXAMPLES = [
    # 13.1 图文文章 - 完整模板
    {
        "content_format": "article",
        "section_type": "intro",
        "target_audience": "public",
        "platform": "wechat",
        "specialty": "endocrine",
        "content_text": """## 血糖到底是什么？

很多人听到"血糖"就发愁，好像这两个字天生就跟"麻烦"挂钩。但其实血糖是个再正常不过的东西——它就是你血液里的糖分，是大脑和肌肉最喜欢的"燃料"。

问题不在于有血糖，而在于血糖**太多或太少**都会出问题。就像汽车油箱，太满会溢出来，太空了跑不动。

你的身体有一套精密的调控系统，其中最重要的"调节阀"叫做**胰岛素**——它是胰腺分泌的一种激素，负责帮细胞"开门"，让糖分进入细胞变成能量。

当这套系统出了问题，血糖就会失控。这就是糖尿病最核心的故事。""",
        "content_json": None,
        "analysis_text": """✓ 开头用类比（燃料/汽车油箱）
✓ 先解释正常，再说异常
✓ 专业词（胰岛素）有通俗解释
✓ 无绝对化表述
✓ 无具体数据（避免编造）
✓ 句子平均17字，符合大众受众标准""",
    },
    # 13.2 口播脚本 - 完整模板（时间戳+停顿）
    {
        "content_format": "oral_script",
        "section_type": "body_1",
        "target_audience": "public",
        "platform": "douyin",
        "specialty": "endocrine",
        "content_text": """[00:15-00:45] 医生（口播）：
血糖高了，很多人第一反应是不能吃甜的。
但你知道吗——白米饭的升糖速度，有时候比糖还快！/
这不是让你不吃饭。
而是让你学会——怎么搭配着吃。
记住这三个字：先吃菜。/
每顿饭先吃蔬菜，再吃蛋白质，最后吃主食。
这个顺序，能让你的血糖平稳很多。
划重点——先吃菜。""",
        "content_json": None,
        "analysis_text": """✓ 完全口语化，无书面语
✓ 每句≤15字
✓ 有停顿标记（/）
✓ 有反问（"你知道吗"）
✓ 有重复强调（"先吃菜"出现两次）
✓ 无具体数据编造
✓ 内容按字数换算约90字/30秒，节奏合理""",
    },
    # 13.3 条漫 - JSON 格式
    {
        "content_format": "comic_strip",
        "section_type": "panel_1",
        "target_audience": "public",
        "platform": "wechat",
        "specialty": None,
        "content_text": None,
        "content_json": json.dumps(COMIC_PANEL_JSON, ensure_ascii=False),
        "analysis_text": None,
    },
    # 13.4 患者手册 - 日常注意事项
    {
        "content_format": "patient_handbook",
        "section_type": "daily_care",
        "target_audience": "patient",
        "platform": "offline",
        "specialty": "endocrine",
        "content_text": """**饮食管理**

控制糖尿病，饮食是关键，但不是"什么都不能吃"。

**可以吃，但要注意量：**
• 主食：每餐主食量控制在半碗到一碗（生米约50-75g），优先选粗粮
• 水果：可以吃，但选低糖水果（苹果、樱桃、草莓等），每天不超过200g
• 肉类：优先选鱼、鸡肉等白肉，红肉适量

**吃的顺序很重要：**
先吃蔬菜→再吃蛋白质（肉/蛋/豆腐）→最后吃主食
这个顺序能让血糖上升更平稳。

**关于甜食：**
偶尔少量吃并不会造成大问题，但要在医生确认血糖控制稳定后再尝试。
不要因为"今天吃了甜食"就非常自责，把握整体趋势比单次更重要。""",
        "content_json": None,
        "analysis_text": """✓ 告诉患者"可以吃什么"，不只是禁止
✓ 具体可操作（半碗/200g 是通俗单位）
✓ 进食顺序是有研究支撑的建议
✓ 情感支持（不要自责）
✓ 未给出具体用药建议""",
    },
]

# 补充示例（简化版，保持原有结构）
LEGACY_EXAMPLES = [
    ("article", "body", "public", "wechat", "endocrine", "血糖控制的核心是「五驾马车」：饮食、运动、药物、监测、教育。饮食上建议少食多餐，选择低GI食物；运动建议每周150分钟中等强度有氧。"),
    ("article", "summary", "public", "wechat", None, "科学控糖不是少吃就行，而是要吃对、动够、测准、遵医嘱。如有疑问请咨询专业医生。"),
    ("article", "intro", "patient", "wechat", "cardiology", "高血压被称为「沉默的杀手」，多数患者早期无明显症状。定期测量血压是发现和控制高血压的第一步。"),
    ("oral_script", "hook", "public", "douyin", None, "你知道吗？每天多喝一杯奶茶，一年能胖十几斤！今天用60秒告诉你，糖分背后的健康真相。"),
    ("oral_script", "summary", "public", "douyin", None, "下次想喝甜的，试试无糖茶或者水果。点赞收藏，转发给爱喝奶茶的朋友！"),
    ("patient_handbook", "disease_intro", "patient", "offline", "endocrine", "2型糖尿病是胰岛素抵抗或分泌不足导致的代谢性疾病。典型症状为多饮、多尿、多食、体重下降。"),
]

# 条漫 panel_2 的 JSON
COMIC_PANEL_2_JSON = {
    "panel_index": 2,
    "scene_desc": "A close-up of a dinner plate with vegetables, protein and rice arranged in sections. Chopsticks picking vegetables first. Clean illustration style, appetizing food presentation.",
    "dialogue": "这个我会！",
    "narration": "一日三餐怎么吃？少油少盐，主食适量，蔬菜占一半。",
    "caption": "进食顺序有讲究",
    "visual_notes": "餐盘分区清晰，突出蔬菜优先",
}


async def seed():
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        updated = 0
        inserted = 0

        # 1. 模板示例：upsert（存在则更新）
        for e in TEMPLATE_EXAMPLES:
            q = (
                select(WritingExample)
                .where(WritingExample.content_format == e["content_format"])
                .where(WritingExample.section_type == e["section_type"])
                .where(WritingExample.platform == e["platform"])
                .where(WritingExample.target_audience == e["target_audience"])
            )
            if e.get("specialty"):
                q = q.where(WritingExample.specialty == e["specialty"])
            else:
                q = q.where(WritingExample.specialty.is_(None))
            r = await session.execute(q.limit(1))
            existing = r.scalar_one_or_none()
            if existing:
                existing.content_text = e.get("content_text") or existing.content_text
                existing.content_json = e.get("content_json") or existing.content_json
                existing.analysis_text = e.get("analysis_text") or existing.analysis_text
                updated += 1
            else:
                session.add(
                    WritingExample(
                        content_format=e["content_format"],
                        section_type=e["section_type"],
                        target_audience=e["target_audience"],
                        platform=e["platform"],
                        specialty=e.get("specialty"),
                        content_text=e.get("content_text"),
                        content_json=e.get("content_json"),
                        analysis_text=e.get("analysis_text"),
                        is_active=1,
                    )
                )
                inserted += 1

        # 2. 条漫 panel_2 特殊处理：补充 JSON
        q = (
            select(WritingExample)
            .where(WritingExample.content_format == "comic_strip")
            .where(WritingExample.section_type == "panel_2")
            .where(WritingExample.platform == "wechat")
        )
        r = await session.execute(q.limit(1))
        p2 = r.scalar_one_or_none()
        if p2:
            p2.content_json = json.dumps(COMIC_PANEL_2_JSON, ensure_ascii=False)
            p2.content_text = None  # 条漫以 JSON 为准
            updated += 1
        else:
            session.add(
                WritingExample(
                    content_format="comic_strip",
                    section_type="panel_2",
                    target_audience="public",
                    platform="wechat",
                    specialty=None,
                    content_text=None,
                    content_json=json.dumps(COMIC_PANEL_2_JSON, ensure_ascii=False),
                    analysis_text=None,
                    is_active=1,
                )
            )
            inserted += 1

        # 3. 其他补充示例（仅当不存在时插入）
        for item in LEGACY_EXAMPLES:
            if len(item) == 6:
                cf, st, ta, pl, sp, txt = item
                cj = None
            else:
                continue
            if cf == "comic_strip" and st == "panel_2":
                continue  # 已处理
            q = (
                select(WritingExample)
                .where(WritingExample.content_format == cf)
                .where(WritingExample.section_type == st)
                .where(WritingExample.platform == pl)
                .where(WritingExample.target_audience == ta)
            )
            if sp:
                q = q.where(WritingExample.specialty == sp)
            else:
                q = q.where(WritingExample.specialty.is_(None))
            r = await session.execute(q.limit(1))
            if r.scalar_one_or_none():
                continue
            session.add(
                WritingExample(
                    content_format=cf,
                    section_type=st,
                    target_audience=ta,
                    platform=pl,
                    specialty=sp,
                    content_text=txt or "",
                    content_json=None,
                    is_active=1,
                )
            )
            inserted += 1

        await session.commit()
        print(f"Writing examples: {inserted} inserted, {updated} updated.")

if __name__ == "__main__":
    asyncio.run(seed())

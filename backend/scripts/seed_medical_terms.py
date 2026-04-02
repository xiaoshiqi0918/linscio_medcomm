"""医学术语种子数据 - public/patient 通俗解释 + student/professional 缩写"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.term import MedicalTerm

# (term, abbreviation, layman_explain, analogy, specialty, audience_level)
TERMS = [
    # public/patient 通俗解释 + 比喻
    ("糖尿病", None, "一种血糖长期偏高的慢性病，身体无法有效利用或储存糖分", "就像水龙头关不紧，糖分不断流入血液", "endocrine", "public"),
    ("高血压", None, "血管内压力持续偏高的状态", "好比水管里水压过大，长期会损伤管道", "cardiology", "public"),
    ("糖化血红蛋白", "HbA1c", "反映过去2-3个月平均血糖水平的指标", "像一张「血糖成绩单」，比单次测血糖更靠谱", "endocrine", "patient"),
    ("冠心病", None, "心脏供血血管狭窄或堵塞导致的心肌缺血", "冠状动脉像心脏的「油管」，堵了心脏就缺氧", "cardiology", "public"),
    ("胰岛素", None, "帮助细胞吸收血糖的激素，糖尿病患者常分泌不足或作用减弱", "像一把钥匙，帮血糖打开细胞的门", "endocrine", "public"),
    ("血脂", None, "血液中的脂肪类物质，包括胆固醇和甘油三酯", "过多的血脂就像水管里的油垢，会堵塞血管", None, "public"),
    # student/professional 标准术语 + 缩写
    ("糖化血红蛋白", "HbA1c", None, None, "endocrine", "student"),
    ("低密度脂蛋白胆固醇", "LDL-C", None, None, "cardiology", "professional"),
    ("高密度脂蛋白胆固醇", "HDL-C", None, None, "cardiology", "professional"),
    ("空腹血糖", "FPG", None, None, "endocrine", "professional"),
    ("餐后2小时血糖", "2hPG", None, None, "endocrine", "professional"),
]


async def seed():
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        for term, abbr, layman, analogy, sp, level in TERMS:
            r = await session.execute(
                select(MedicalTerm).where(
                    MedicalTerm.term == term,
                    MedicalTerm.audience_level == level,
                ).limit(1)
            )
            if r.scalars().first():
                continue
            t = MedicalTerm(
                term=term,
                abbreviation=abbr,
                layman_explain=layman,
                analogy=analogy,
                specialty=sp,
                audience_level=level,
            )
            session.add(t)
        await session.commit()
    print(f"Medical terms seeded: {len(TERMS)} rows.")


if __name__ == "__main__":
    asyncio.run(seed())

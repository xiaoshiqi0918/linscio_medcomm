"""种子模板数据 - 20+ 个覆盖各形式"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.template import ContentTemplate

# (name, content_format, platform, specialty, structure_str)
TEMPLATES = [
    ("疾病科普标准模板", "article", "wechat", "endocrine", "intro,body,case,qa,summary"),
    ("健康饮食科普", "article", "wechat", "", "intro,body,summary"),
    ("研究速读精简版", "article", "journal", "", "intro,body,summary"),
    ("科普故事七章式", "story", "wechat", "", "hook,development,turning_point,science_core,resolution,action_list,closing_quote"),
    ("儿童健康小故事", "story", "wechat", "pediatric", "hook,development,turning_point,science_core,resolution"),
    ("辟谣文七段式", "debunk", "wechat", "", "rumor_present,verdict,debunk_1,debunk_2,debunk_3,correct_practice,anti_fraud"),
    ("问答科普五问五答", "qa_article", "wechat", "", "qa_intro,qa_1,qa_2,qa_3,qa_4,qa_5,qa_summary"),
    ("研究速读七段式", "research_read", "wechat", "", "one_liner,study_card,why_matters,methods,findings,implication,limitation"),
    ("抖音口播脚本", "oral_script", "douyin", "", "script_plan,golden_hook,problem_setup,core_knowledge,practical_tips,closing_hook,extras"),
    ("情景剧本五幕式", "drama_script", "douyin", "", "drama_plan,cast_table,act_1,act_2,act_3,act_4,act_5,finale,filming_notes"),
    ("动画分镜五幕式", "storyboard", "bilibili", "", "anim_plan,char_design,reel_1,reel_2,reel_3,reel_4,reel_5,prod_notes"),
    ("播客科普脚本", "audio_script", "wechat", "", "opening,topic_intro,deep_dive,extension,closing"),
    ("条漫12格七幕科普", "comic_strip", "wechat", "", "planner,panel_1,panel_2,panel_3,panel_4,panel_5,panel_6,panel_7,panel_8,panel_9,panel_10,panel_11,panel_12"),
    ("知识卡片系列9张", "card_series", "xiaohongshu", "", "series_plan,cover_card,card_1,card_2,card_3,card_4,card_5,card_6,card_7,ending_card"),
    ("科普海报标准", "poster", "xiaohongshu", "", "poster_brief,headline,body_visual,cta_footer,design_spec"),
    ("儿童绘本16页", "picture_book", "wechat", "", "book_plan,cover,spread_1,spread_2,spread_3,spread_4,spread_5,spread_6,spread_7,back_cover"),
    ("竖版长图通用", "long_image", "wechat", "", "image_plan,title_block,intro_block,core_1,core_2,core_3,core_4,tips_block,warning_block,summary_cta,footer_info"),
    ("患者教育手册九部式", "patient_handbook", "offline", "", "handbook_plan,cover,disease_know,treatment,daily_care,followup,emergency,faq,back_cover"),
    ("糖尿病自测5题", "quiz_article", "wechat", "", "quiz_intro,q_1,q_2,q_3,q_4,q_5,summary"),
    ("H5互动5页大纲", "h5_outline", "wechat", "", "page_cover,page_1,page_2,page_3,page_end"),
    ("通用叙事模板", "article", "universal", "", "intro,body,summary"),
    ("小红书种草文", "article", "xiaohongshu", "", "intro,body,summary"),
]


async def seed():
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        for name, content_format, platform, specialty, structure_str in TEMPLATES:
            r = await session.execute(
                select(ContentTemplate).where(
                    ContentTemplate.name == name,
                    ContentTemplate.content_format == content_format,
                    ContentTemplate.platform == platform,
                )
            )
            if r.scalars().first():
                continue
            structure = [{"section_type": s.strip(), "title": s.strip()} for s in structure_str.split(",")]
            t = ContentTemplate(
                name=name,
                content_format=content_format,
                platform=platform,
                specialty=specialty or None,
                structure=structure,
                is_system=True,
                is_active=True,
            )
            session.add(t)
        await session.commit()
    print("Templates seeded.")


if __name__ == "__main__":
    asyncio.run(seed())

"""种子模板数据 - 20+ 个覆盖各形式"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.template import ContentTemplate

# (name, content_format, platform, specialty, structure_str)
TEMPLATES = [
    ("疾病科普标准模板", "article", "wechat", "endocrine", "intro,body,case,qa,summary"),
    ("健康饮食科普", "article", "wechat", "", "intro,body,summary"),
    ("研究速读精简版", "article", "journal", "", "intro,body,summary"),
    ("科普故事五幕式", "story", "wechat", "", "opening,development,climax,resolution,lesson"),
    ("儿童健康小故事", "story", "wechat", "pediatric", "opening,development,resolution,lesson"),
    ("五大误区辟谣模板", "debunk", "wechat", "", "myth_intro,myth_1,myth_2,myth_3,action_guide"),
    ("患者十问十答", "qa_article", "wechat", "", "qa_intro,qa_1,qa_2,qa_3,qa_summary"),
    ("研究速读四段式", "research_read", "journal", "", "background,finding,implication,caution"),
    ("抖音60秒口播模板", "oral_script", "douyin", "", "hook,body_1,body_2,summary,cta"),
    ("情景剧三幕式", "drama_script", "douyin", "", "scene_setup,scene_1,scene_2,ending"),
    ("动画分镜6帧", "storyboard", "bilibili", "", "planner,frame_1,frame_2,frame_3,frame_4,frame_5,frame_6"),
    ("播客科普脚本", "audio_script", "wechat", "", "opening,topic_intro,deep_dive,extension,closing"),
    ("条漫6格疾病科普", "comic_strip", "wechat", "", "planner,panel_1,panel_2,panel_3,panel_4,panel_5,panel_6"),
    ("知识卡片系列5张", "card_series", "xiaohongshu", "", "card_1,card_2,card_3,card_4,card_5"),
    ("科普海报标准", "poster", "xiaohongshu", "", "headline,core_message,data_points,cta,visual_desc"),
    ("儿童绘本5页", "picture_book", "wechat", "", "planner,page_1,page_2,page_3,page_4,page_5"),
    ("竖版长图通用", "long_image", "wechat", "", "cover,section_1,section_2,section_3,footer"),
    ("患者教育手册通用", "patient_handbook", "offline", "", "cover_copy,disease_intro,symptoms,treatment,daily_care,visit_tips"),
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

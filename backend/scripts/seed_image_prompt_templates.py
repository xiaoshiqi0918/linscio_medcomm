"""图像提示词模板种子 - 按形式/风格提供 prompt 增强"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.image_prompt_template import ImagePromptTemplate

# (name, content_format, style, prompt_template, description)
TEMPLATES = [
    (
        "医学插画通用",
        "article",
        "medical_illustration",
        "医学插画风格，清晰准确，专业严谨。{scene}",
        "适用于科普文章配图，强调准确性与可读性",
    ),
    (
        "科普漫画",
        "comic_strip",
        "comic",
        "科普漫画风格，易懂有趣，线条清晰。{scene}",
        "适用于条漫、漫画类内容",
    ),
    (
        "绘本风格",
        "picture_book",
        "picture_book",
        "温馨绘本风格，适合儿童，色彩柔和。{scene}",
        "适用于儿童健康绘本",
    ),
    (
        "扁平化设计",
        "poster",
        "flat_design",
        "扁平化设计风格，简洁现代，配色清爽。{scene}",
        "适用于海报、知识卡片",
    ),
    (
        "条漫分镜",
        "comic_strip",
        "comic",
        "条漫分镜风格，画面连贯，分格清晰。{scene}",
        "六格条漫专用",
    ),
    (
        "知识卡片",
        "card_series",
        "flat_design",
        "知识卡片风格，信息突出，排版规整。{scene}",
        "小红书/知识卡片系列",
    ),
    (
        "长图竖版",
        "long_image",
        "flat_design",
        "竖版长图风格，信息流式，易读易分享。{scene}",
        "竖版长图通用",
    ),
    (
        "口播配图",
        "oral_script",
        "flat_design",
        "短视频配图风格，视觉冲击强，易吸引注意。{scene}",
        "抖音口播配图",
    ),
    (
        "医学插画-内分泌",
        "article",
        "medical_illustration",
        "医学插画风格，内分泌领域，解剖与机制示意清晰。{scene}",
        "内分泌专科科普",
    ),
    (
        "医学插画-儿科",
        "article",
        "medical_illustration",
        "医学插画风格，儿科友好，温和易懂。{scene}",
        "儿科科普专用",
    ),
]


async def seed():
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        for name, content_format, style, prompt_template, description in TEMPLATES:
            r = await session.execute(
                select(ImagePromptTemplate).where(
                    ImagePromptTemplate.name == name,
                    ImagePromptTemplate.content_format == content_format,
                    ImagePromptTemplate.style == style,
                )
            )
            if r.scalars().first():
                continue
            t = ImagePromptTemplate(
                name=name,
                content_format=content_format,
                style=style,
                prompt_template=prompt_template,
                description=description or None,
                is_system=True,
                is_active=True,
            )
            session.add(t)
        await session.commit()
    print("Image prompt templates seeded.")


if __name__ == "__main__":
    asyncio.run(seed())

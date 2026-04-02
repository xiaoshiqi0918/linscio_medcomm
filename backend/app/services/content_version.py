"""内容版本管理 - save_node + enforce_version_limit"""
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import ArticleContent

VERSION_LIMIT = 30


async def enforce_version_limit(db: AsyncSession, section_id: int, platform: str) -> int:
    """
    单章节 × 单平台最多保留 VERSION_LIMIT 个版本
    删除超出部分（按 id 升序，保留最新的）
    返回删除数量
    """
    platform = platform or "wechat"
    from sqlalchemy import or_
    platform_filter = (ArticleContent.platform == platform) | ((ArticleContent.platform.is_(None)) & (platform == "wechat"))
    subq = (
        select(ArticleContent.id)
        .where(
            ArticleContent.section_id == section_id,
            platform_filter,
        )
        .order_by(ArticleContent.id.desc())
        .limit(VERSION_LIMIT)
    )
    to_keep = await db.execute(subq)
    keep_ids = [r[0] for r in to_keep.all()]

    if not keep_ids:
        return 0

    result = await db.execute(
        delete(ArticleContent).where(
            ArticleContent.section_id == section_id,
            platform_filter,
            ArticleContent.id.notin_(keep_ids),
        )
    )
    return result.rowcount or 0


async def save_node(
    db: AsyncSession,
    article_id: int,
    section_id: int,
    content_json: dict,
    version_type: str = "user_edited",
    platform: str | None = None,
    verify_report: dict | None = None,
) -> ArticleContent:
    """
    保存节点内容，创建新版本并执行版本上限清理
    """
    from app.models.article import Article
    from sqlalchemy import select

    platform = platform or "wechat"
    if not platform:
        ar = await db.execute(select(Article).where(Article.id == article_id))
        art = ar.scalar_one_or_none()
        if art and art.platform:
            platform = art.platform

    # 将当前 (section, platform) 的 is_current 置为 False；platform=None 视为同 platform
    from sqlalchemy import or_
    existing = await db.execute(
        select(ArticleContent).where(
            ArticleContent.section_id == section_id,
            or_(
                ArticleContent.platform == platform,
                (ArticleContent.platform.is_(None)) & (platform == "wechat"),
            ),
            ArticleContent.is_current == True,
        )
    )
    prev_verify = None
    for c in existing.scalars().all():
        if c.verify_report is not None:
            prev_verify = c.verify_report
        c.is_current = False

    if verify_report is None and prev_verify is not None:
        verify_report = prev_verify

    # 计算新版本号（含 platform=None 视为 wechat）
    pf = (ArticleContent.platform == platform) | ((ArticleContent.platform.is_(None)) & (platform == "wechat"))
    max_ver = await db.execute(
        select(func.max(ArticleContent.version)).where(
            ArticleContent.section_id == section_id,
            pf,
        )
    )
    next_version = (max_ver.scalar() or 0) + 1

    import json
    new_content = ArticleContent(
        article_id=article_id,
        section_id=section_id,
        content_json=json.dumps(content_json) if isinstance(content_json, dict) else str(content_json),
        version=next_version,
        version_type=version_type,
        platform=platform,
        is_current=True,
        verify_report=verify_report,
    )
    db.add(new_content)
    await db.flush()

    await enforce_version_limit(db, section_id, platform)
    return new_content

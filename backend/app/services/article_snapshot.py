"""文章快照：创建 / 列举 / 恢复"""
import json
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, ArticleSection, ArticleContent
from app.models.article_snapshot import ArticleSnapshot
from app.services.content_version import save_node

SNAPSHOT_LIMIT_PER_ARTICLE = 50


async def _current_section_doc(
    db: AsyncSession, section_id: int, platform: str
) -> dict:
    from sqlalchemy import or_
    pf = (ArticleContent.platform == platform) | (
        (ArticleContent.platform.is_(None)) & (platform == "wechat")
    )
    r = await db.execute(
        select(ArticleContent)
        .where(
            ArticleContent.section_id == section_id,
            ArticleContent.is_current == True,
            pf,
        )
        .limit(1)
    )
    row = r.scalar_one_or_none()
    if not row or not row.content_json:
        return {"type": "doc", "content": []}
    try:
        return json.loads(row.content_json)
    except Exception:
        return {"type": "doc", "content": []}


async def create_snapshot(
    db: AsyncSession,
    *,
    user_id: int,
    article_id: int,
    label: str = "",
    note: str = "",
) -> ArticleSnapshot:
    ar = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    article = ar.scalar_one_or_none()
    if not article:
        raise ValueError("article_not_found")
    platform = article.platform or "wechat"
    sec_r = await db.execute(
        select(ArticleSection)
        .where(ArticleSection.article_id == article_id)
        .order_by(ArticleSection.order_num, ArticleSection.id)
    )
    sections = sec_r.scalars().all()
    payload_sections = []
    for sec in sections:
        doc = await _current_section_doc(db, sec.id, platform)
        payload_sections.append(
            {
                "section_id": sec.id,
                "section_type": sec.section_type,
                "title": sec.title,
                "order_num": sec.order_num,
                "content_json": doc,
            }
        )
    payload = {
        "v": 1,
        "platform": platform,
        "article": {
            "id": article.id,
            "title": article.title,
            "topic": article.topic,
            "content_format": article.content_format,
        },
        "sections": payload_sections,
    }
    cnt = await db.execute(
        select(func.count()).select_from(ArticleSnapshot).where(ArticleSnapshot.article_id == article_id)
    )
    n = cnt.scalar() or 0
    if n >= SNAPSHOT_LIMIT_PER_ARTICLE:
        oldest = await db.execute(
            select(ArticleSnapshot.id)
            .where(ArticleSnapshot.article_id == article_id)
            .order_by(ArticleSnapshot.id.asc())
            .limit(n - SNAPSHOT_LIMIT_PER_ARTICLE + 1)
        )
        for (oid,) in oldest.all():
            await db.execute(delete(ArticleSnapshot).where(ArticleSnapshot.id == oid))

    snap = ArticleSnapshot(
        user_id=user_id,
        article_id=article_id,
        label=(label or "").strip()[:200],
        note=(note or "").strip(),
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(snap)
    await db.flush()
    return snap


async def restore_snapshot(db: AsyncSession, snapshot_id: int, user_id: int) -> None:
    r = await db.execute(
        select(ArticleSnapshot).where(
            ArticleSnapshot.id == snapshot_id,
            ArticleSnapshot.user_id == user_id,
        )
    )
    snap = r.scalar_one_or_none()
    if not snap:
        raise ValueError("snapshot_not_found")
    payload = json.loads(snap.payload_json)
    platform = payload.get("platform") or "wechat"
    article_id = snap.article_id
    for sec in payload.get("sections") or []:
        sid = sec.get("section_id")
        doc = sec.get("content_json")
        if sid is None or not isinstance(doc, dict):
            continue
        await save_node(
            db,
            article_id=article_id,
            section_id=int(sid),
            content_json=doc,
            version_type="snapshot_restore",
            platform=platform,
        )

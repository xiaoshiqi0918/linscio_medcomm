"""文章本地快照 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.article import Article
from app.models.article_snapshot import ArticleSnapshot
from app.services.article_snapshot import create_snapshot, restore_snapshot

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CreateSnapshotBody(BaseModel):
    label: str = ""
    note: str = ""


@router.get("/articles/{article_id}/snapshots")
async def list_snapshots(
    article_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ar = await db.execute(select(Article).where(Article.id == article_id, Article.deleted_at.is_(None)))
    if not ar.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="文章不存在")
    r = await db.execute(
        select(ArticleSnapshot)
        .where(
            ArticleSnapshot.article_id == article_id,
            ArticleSnapshot.user_id == user.id,
        )
        .order_by(ArticleSnapshot.id.desc())
    )
    items = r.scalars().all()
    return {
        "items": [
            {
                "id": s.id,
                "label": s.label,
                "note": s.note,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in items
        ]
    }


@router.post("/articles/{article_id}/snapshots")
async def post_snapshot(
    article_id: int,
    body: CreateSnapshotBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        snap = await create_snapshot(
            db,
            user_id=user.id,
            article_id=article_id,
            label=body.label,
            note=body.note,
        )
        await db.commit()
        await db.refresh(snap)
    except ValueError as e:
        if str(e) == "article_not_found":
            raise HTTPException(status_code=404, detail="文章不存在")
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": snap.id, "label": snap.label, "created_at": snap.created_at.isoformat() if snap.created_at else None}


@router.post("/articles/{article_id}/snapshots/{snapshot_id}/restore")
async def post_restore_snapshot(
    article_id: int,
    snapshot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chk = await db.execute(
        select(ArticleSnapshot).where(
            ArticleSnapshot.id == snapshot_id,
            ArticleSnapshot.article_id == article_id,
            ArticleSnapshot.user_id == user.id,
        )
    )
    if not chk.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="快照不存在或文章不匹配")
    try:
        await restore_snapshot(db, snapshot_id, user.id)
        await db.commit()
    except ValueError:
        raise HTTPException(status_code=404, detail="快照不存在")
    return {"ok": True}


@router.delete("/articles/{article_id}/snapshots/{snapshot_id}")
async def delete_snapshot(
    article_id: int,
    snapshot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        delete(ArticleSnapshot).where(
            ArticleSnapshot.id == snapshot_id,
            ArticleSnapshot.article_id == article_id,
            ArticleSnapshot.user_id == user.id,
        )
    )
    await db.commit()
    if not r.rowcount:
        raise HTTPException(status_code=404, detail="快照不存在")
    return {"ok": True}

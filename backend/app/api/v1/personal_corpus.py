"""个人语料 API（手动维护 + capture 收录，注入生成提示词）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.personal_corpus import PersonalCorpusEntry

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CorpusCreateBody(BaseModel):
    kind: str = Field(..., description="avoid | prefer | note")
    anchor: str = ""
    content: str = ""
    source: str = "manual"


class CorpusPatchBody(BaseModel):
    anchor: str | None = None
    content: str | None = None
    enabled: bool | None = None
    kind: str | None = None


class CaptureBody(BaseModel):
    """从使用过程收录：例如改稿后「把这种说法记下来」"""
    kind: str = "prefer"
    anchor: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="", max_length=4000)


def _norm_kind(k: str) -> str:
    k = (k or "note").lower()
    if k not in ("avoid", "prefer", "note"):
        raise HTTPException(status_code=400, detail="kind 须为 avoid | prefer | note")
    return k


@router.get("")
async def list_corpus(
    enabled_only: bool = Query(False, description="仅返回启用的条目"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(PersonalCorpusEntry).where(PersonalCorpusEntry.user_id == user.id)
    if enabled_only:
        q = q.where(PersonalCorpusEntry.enabled == True)
    q = q.order_by(PersonalCorpusEntry.id.desc())
    r = await db.execute(q)
    rows = r.scalars().all()
    return {
        "items": [
            {
                "id": e.id,
                "kind": e.kind,
                "anchor": e.anchor,
                "content": e.content,
                "source": e.source,
                "enabled": e.enabled,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ]
    }


@router.post("")
async def create_corpus(
    body: CorpusCreateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kind = _norm_kind(body.kind)
    src = (body.source or "manual").lower()
    if src not in ("manual", "capture"):
        src = "manual"
    e = PersonalCorpusEntry(
        user_id=user.id,
        kind=kind,
        anchor=(body.anchor or "")[:500],
        content=(body.content or "")[:4000],
        source=src,
        enabled=True,
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return {"id": e.id}


@router.post("/capture")
async def capture_corpus(
    body: CaptureBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kind = _norm_kind(body.kind)
    e = PersonalCorpusEntry(
        user_id=user.id,
        kind=kind,
        anchor=body.anchor.strip()[:500],
        content=(body.content or "").strip()[:4000],
        source="capture",
        enabled=True,
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return {"id": e.id, "ok": True}


@router.patch("/{entry_id}")
async def patch_corpus(
    entry_id: int,
    body: CorpusPatchBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(PersonalCorpusEntry).where(
            PersonalCorpusEntry.id == entry_id,
            PersonalCorpusEntry.user_id == user.id,
        )
    )
    e = r.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="条目不存在")
    if body.kind is not None:
        e.kind = _norm_kind(body.kind)
    if body.anchor is not None:
        e.anchor = body.anchor[:500]
    if body.content is not None:
        e.content = body.content[:4000]
    if body.enabled is not None:
        e.enabled = body.enabled
    await db.commit()
    return {"ok": True}


@router.delete("/{entry_id}")
async def delete_corpus(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(PersonalCorpusEntry).where(
            PersonalCorpusEntry.id == entry_id,
            PersonalCorpusEntry.user_id == user.id,
        )
    )
    e = r.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="条目不存在")
    await db.delete(e)
    await db.commit()
    return {"ok": True}

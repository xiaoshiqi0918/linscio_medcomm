"""医学术语库 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal
from app.models.term import MedicalTerm

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CreateTermRequest(BaseModel):
    term: str
    abbreviation: str | None = None
    layman_explain: str | None = None
    analogy: str | None = None
    specialty: str | None = None
    audience_level: str = "public"


@router.get("")
async def list_terms(
    audience_level: str | None = Query(None),
    specialty: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """术语列表，支持按受众/专科过滤"""
    q = select(MedicalTerm)
    if audience_level:
        q = q.where(MedicalTerm.audience_level == audience_level)
    if specialty:
        q = q.where(MedicalTerm.specialty == specialty)
    q = q.order_by(MedicalTerm.term)
    result = await db.execute(q)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": t.id,
                "term": t.term,
                "abbreviation": t.abbreviation,
                "audience_level": t.audience_level,
                "specialty": t.specialty,
            }
            for t in items
        ]
    }


@router.post("")
async def create_term(req: CreateTermRequest, db: AsyncSession = Depends(get_db)):
    """新增术语"""
    t = MedicalTerm(
        term=req.term,
        abbreviation=req.abbreviation,
        layman_explain=req.layman_explain,
        analogy=req.analogy,
        specialty=req.specialty,
        audience_level=req.audience_level,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"id": t.id, "term": t.term, "audience_level": t.audience_level}


@router.get("/{term_id}")
async def get_term(term_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个术语详情"""
    result = await db.execute(select(MedicalTerm).where(MedicalTerm.id == term_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="术语不存在")
    return {
        "id": t.id,
        "term": t.term,
        "abbreviation": t.abbreviation,
        "layman_explain": t.layman_explain,
        "analogy": t.analogy,
        "specialty": t.specialty,
        "audience_level": t.audience_level,
    }


@router.delete("/{term_id}")
async def delete_term(term_id: int, db: AsyncSession = Depends(get_db)):
    """删除术语"""
    result = await db.execute(select(MedicalTerm).where(MedicalTerm.id == term_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="术语不存在")
    await db.delete(t)
    await db.commit()
    return {"ok": True}

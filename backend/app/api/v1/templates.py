"""模板库 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal
from app.models.template import ContentTemplate

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CreateTemplateRequest(BaseModel):
    name: str = ""
    content_format: str = "article"
    platform: str | None = None
    specialty: str | None = None
    structure: dict | None = None
    description: str | None = None


@router.get("")
async def list_templates(
    content_format: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """模板列表，支持按形式过滤"""
    q = select(ContentTemplate).where(ContentTemplate.is_active == True)
    if content_format:
        q = q.where(ContentTemplate.content_format == content_format)
    q = q.order_by(ContentTemplate.content_format, ContentTemplate.name)
    result = await db.execute(q)
    items = result.scalars().all()
    return {"items": [{"id": t.id, "name": t.name, "content_format": t.content_format, "platform": t.platform, "specialty": t.specialty} for t in items]}


@router.post("")
async def create_template(req: CreateTemplateRequest, db: AsyncSession = Depends(get_db)):
    """新建模板"""
    t = ContentTemplate(
        name=req.name or "未命名",
        content_format=req.content_format,
        platform=req.platform,
        specialty=req.specialty,
        structure=req.structure,
        description=req.description,
        is_system=False,
        is_active=True,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"id": t.id, "name": t.name, "content_format": t.content_format}

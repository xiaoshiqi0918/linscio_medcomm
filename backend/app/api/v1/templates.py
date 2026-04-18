"""模板库 API — 完整 CRUD"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal
from app.models.template import ContentTemplate

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def _template_to_dict(t: ContentTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "content_format": t.content_format,
        "platform": t.platform,
        "specialty": t.specialty,
        "structure": t.structure,
        "description": t.description,
        "target_word_count": t.target_word_count,
        "target_audience": t.target_audience,
        "reading_level": t.reading_level,
        "skip_sections": t.skip_sections,
        "is_system": t.is_system,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "section_count": len(t.structure) if isinstance(t.structure, list) else 0,
    }


class CreateTemplateRequest(BaseModel):
    name: str = ""
    content_format: str = "article"
    platform: str | None = None
    specialty: str | None = None
    structure: list | None = None
    description: str | None = None
    target_word_count: int | None = None
    target_audience: str | None = None
    reading_level: str | None = None
    skip_sections: list[str] | None = None


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    content_format: str | None = None
    platform: str | None = None
    specialty: str | None = None
    structure: list | None = None
    description: str | None = None
    target_word_count: int | None = None
    target_audience: str | None = None
    reading_level: str | None = None
    skip_sections: list[str] | None = None


@router.get("")
async def list_templates(
    content_format: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """模板列表，支持按形式过滤"""
    q = select(ContentTemplate).where(ContentTemplate.is_active == True)
    if content_format:
        q = q.where(ContentTemplate.content_format == content_format)
    q = q.order_by(ContentTemplate.is_system.desc(), ContentTemplate.content_format, ContentTemplate.name)
    result = await db.execute(q)
    items = result.scalars().all()
    return {"items": [_template_to_dict(t) for t in items]}


@router.get("/{template_id}")
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个模板详情"""
    result = await db.execute(
        select(ContentTemplate).where(ContentTemplate.id == template_id, ContentTemplate.is_active == True)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_to_dict(t)


@router.post("")
async def create_template(req: CreateTemplateRequest, db: AsyncSession = Depends(get_db)):
    """新建模板"""
    t = ContentTemplate(
        name=req.name or "未命名模板",
        content_format=req.content_format,
        platform=req.platform,
        specialty=req.specialty,
        structure=req.structure,
        description=req.description,
        target_word_count=req.target_word_count,
        target_audience=req.target_audience,
        reading_level=req.reading_level,
        skip_sections=req.skip_sections,
        is_system=False,
        is_active=True,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return _template_to_dict(t)


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    req: UpdateTemplateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新模板（系统模板不可编辑）"""
    result = await db.execute(
        select(ContentTemplate).where(ContentTemplate.id == template_id, ContentTemplate.is_active == True)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if t.is_system:
        raise HTTPException(status_code=403, detail="系统模板不可编辑，请先复制")

    if req.name is not None:
        t.name = req.name
    if req.content_format is not None:
        t.content_format = req.content_format
    if req.platform is not None:
        t.platform = req.platform
    if req.specialty is not None:
        t.specialty = req.specialty
    if req.structure is not None:
        t.structure = req.structure
    if req.description is not None:
        t.description = req.description
    if req.target_word_count is not None:
        t.target_word_count = req.target_word_count
    if req.target_audience is not None:
        t.target_audience = req.target_audience
    if req.reading_level is not None:
        t.reading_level = req.reading_level
    if req.skip_sections is not None:
        t.skip_sections = req.skip_sections

    await db.commit()
    await db.refresh(t)
    return _template_to_dict(t)


@router.delete("/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """删除模板（软删除，系统模板不可删除）"""
    result = await db.execute(
        select(ContentTemplate).where(ContentTemplate.id == template_id, ContentTemplate.is_active == True)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if t.is_system:
        raise HTTPException(status_code=403, detail="系统模板不可删除")
    t.is_active = False
    await db.commit()
    return {"ok": True}


@router.post("/{template_id}/duplicate")
async def duplicate_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """复制模板为非系统副本"""
    result = await db.execute(
        select(ContentTemplate).where(ContentTemplate.id == template_id, ContentTemplate.is_active == True)
    )
    src = result.scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="Template not found")

    dup = ContentTemplate(
        name=f"{src.name}（副本）",
        content_format=src.content_format,
        platform=src.platform,
        specialty=src.specialty,
        structure=src.structure,
        description=src.description,
        target_word_count=src.target_word_count,
        target_audience=src.target_audience,
        reading_level=src.reading_level,
        skip_sections=src.skip_sections,
        is_system=False,
        is_active=True,
    )
    db.add(dup)
    await db.commit()
    await db.refresh(dup)
    return _template_to_dict(dup)

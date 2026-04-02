"""Few-shot 示例库 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal
from app.models.example import WritingExample

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CreateExampleRequest(BaseModel):
    content_format: str
    section_type: str
    target_audience: str = "public"
    platform: str = "wechat"
    specialty: str | None = None
    content_text: str = ""
    content_json: str | None = None
    analysis_text: str | None = None
    source_doc: str | None = None
    medical_reviewed: bool = False


class UpdateExampleRequest(BaseModel):
    source_doc: str | None = None
    medical_reviewed: bool | None = None


@router.get("")
async def list_examples(
    content_format: str | None = Query(None),
    section_type: str | None = Query(None),
    platform: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """示例列表，支持按形式/章节/平台过滤"""
    q = select(WritingExample).where(WritingExample.is_active == 1)
    if content_format:
        q = q.where(WritingExample.content_format == content_format)
    if section_type:
        q = q.where(WritingExample.section_type == section_type)
    if platform:
        q = q.where(WritingExample.platform == platform)
    q = q.order_by(WritingExample.content_format, WritingExample.section_type, WritingExample.created_at.desc())
    result = await db.execute(q)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": e.id,
                "content_format": e.content_format,
                "section_type": e.section_type,
                "target_audience": e.target_audience,
                "platform": e.platform,
                "specialty": e.specialty,
                "content_text_preview": (e.content_text or "")[:100] + "..." if (e.content_text and len(e.content_text) > 100) else (e.content_text or ""),
                "medical_reviewed": bool(getattr(e, "medical_reviewed", 0)),
            }
            for e in items
        ]
    }


@router.post("")
async def create_example(req: CreateExampleRequest, db: AsyncSession = Depends(get_db)):
    """新增示例"""
    ex = WritingExample(
        content_format=req.content_format,
        section_type=req.section_type,
        target_audience=req.target_audience,
        platform=req.platform,
        specialty=req.specialty,
        content_text=req.content_text,
        content_json=req.content_json,
        analysis_text=req.analysis_text,
        source_doc=req.source_doc,
        medical_reviewed=1 if req.medical_reviewed else 0,
        is_active=1,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    return {"id": ex.id, "content_format": ex.content_format, "section_type": ex.section_type}


@router.patch("/{example_id}")
async def update_example(example_id: int, req: UpdateExampleRequest, db: AsyncSession = Depends(get_db)):
    """更新示例（来源、审核标记）"""
    result = await db.execute(select(WritingExample).where(WritingExample.id == example_id))
    ex = result.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail="示例不存在")
    if req.source_doc is not None:
        ex.source_doc = req.source_doc
    if req.medical_reviewed is not None:
        ex.medical_reviewed = 1 if req.medical_reviewed else 0
    await db.commit()
    return {"ok": True}


@router.get("/{example_id}")
async def get_example(example_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个示例详情"""
    result = await db.execute(select(WritingExample).where(WritingExample.id == example_id))
    ex = result.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail="示例不存在")
    return {
        "id": ex.id,
        "content_format": ex.content_format,
        "section_type": ex.section_type,
        "target_audience": ex.target_audience,
        "platform": ex.platform,
        "specialty": ex.specialty,
        "content_text": ex.content_text,
        "content_json": ex.content_json,
        "analysis_text": getattr(ex, "analysis_text", None),
        "source_doc": getattr(ex, "source_doc", None),
        "medical_reviewed": bool(getattr(ex, "medical_reviewed", 0)),
    }


@router.delete("/{example_id}")
async def delete_example(example_id: int, db: AsyncSession = Depends(get_db)):
    """软删除示例（置 is_active=0）"""
    result = await db.execute(select(WritingExample).where(WritingExample.id == example_id))
    ex = result.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail="示例不存在")
    ex.is_active = 0
    await db.commit()
    return {"ok": True}

"""发布管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import AsyncSessionLocal, get_domain_lock
from app.models.publish import PublishRecord
from app.models.article import Article

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CreatePublishRecordRequest(BaseModel):
    article_id: int
    platform: str
    publish_url: str = ""
    read_count: int | None = None


@router.get("/records")
async def list_records(article_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """发布记录列表"""
    q = select(PublishRecord)
    if article_id:
        q = q.where(PublishRecord.article_id == article_id)
    q = q.order_by(PublishRecord.created_at.desc())
    result = await db.execute(q)
    items = result.scalars().all()
    return {"items": [{"id": r.id, "article_id": r.article_id, "platform": r.platform, "publish_url": r.publish_url, "read_count": r.read_count} for r in items]}


@router.post("/records")
async def create_record(req: CreatePublishRecordRequest, db: AsyncSession = Depends(get_db)):
    """创建发布记录"""
    lock = get_domain_lock("articles")
    async with lock:
        rec = PublishRecord(article_id=req.article_id, platform=req.platform, publish_url=req.publish_url, read_count=req.read_count)
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
    return {"id": rec.id}


@router.patch("/records/{record_id}")
async def update_record(record_id: int, read_count: int | None = None, publish_url: str | None = None, db: AsyncSession = Depends(get_db)):
    """更新发布记录（手动录入阅读量）"""
    lock = get_domain_lock("articles")
    async with lock:
        result = await db.execute(select(PublishRecord).where(PublishRecord.id == record_id))
        rec = result.scalar_one_or_none()
        if not rec:
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        if read_count is not None:
            rec.read_count = read_count
        if publish_url is not None:
            rec.publish_url = publish_url
        await db.commit()
    return {"ok": True}

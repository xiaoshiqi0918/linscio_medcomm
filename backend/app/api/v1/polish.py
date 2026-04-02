"""润色适配 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.polish import PolishSession, PolishChange

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class CreateSessionRequest(BaseModel):
    section_id: int
    polish_type: str = "language"  # language | platform | script | visual | handbook


class RunPolishRequest(BaseModel):
    session_id: int


@router.post("/run")
async def polish_run(req: RunPolishRequest, db=Depends(get_db)):
    """执行润色：按 polish_type 调用对应 Agent（language/platform/script/visual/handbook）"""
    from app.services.polish import run_polish

    result = await run_polish(req.session_id, db)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "changes_count": result["changes_count"],
        "word_count": result.get("word_count"),
        "changes_summary": result.get("changes_summary"),
        "platform_tips": result.get("platform_tips", []),
    }


@router.post("/sessions")
async def create_polish_session(req: CreateSessionRequest, db=Depends(get_db)):
    """创建润色会话"""
    session = PolishSession(section_id=req.section_id, polish_type=req.polish_type, status="active")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "section_id": session.section_id, "polish_type": session.polish_type, "status": session.status}


@router.get("/sessions/{session_id}/changes")
async def list_session_changes(session_id: int, db=Depends(get_db)):
    """获取润色会话下的所有修改建议"""
    result = await db.execute(
        select(PolishChange).where(PolishChange.session_id == session_id).order_by(PolishChange.id)
    )
    changes = result.scalars().all()
    return {
        "changes": [
            {
                "id": c.id,
                "original_text": c.original_text,
                "suggested_text": c.suggested_text,
                "status": c.status,
            }
            for c in changes
        ]
    }


@router.get("/sessions/active/{section_id}")
async def get_active_session(section_id: int, db=Depends(get_db)):
    """获取章节当前 active 的润色会话"""
    result = await db.execute(
        select(PolishSession).where(
            PolishSession.section_id == section_id,
            PolishSession.status == "active",
        ).order_by(PolishSession.id.desc()).limit(1)
    )
    s = result.scalar_one_or_none()
    if not s:
        return {"session": None}
    return {"session": {"id": s.id, "section_id": s.section_id, "polish_type": s.polish_type, "status": s.status}}


@router.post("/changes/{change_id}/accept")
async def accept_change(change_id: int, db=Depends(get_db)):
    """采纳润色建议"""
    result = await db.execute(select(PolishChange).where(PolishChange.id == change_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, detail="Change not found")
    c.status = "accepted"
    await db.commit()
    return {"ok": True}


@router.post("/changes/{change_id}/reject")
async def reject_change(change_id: int, db=Depends(get_db)):
    """拒绝润色建议"""
    result = await db.execute(select(PolishChange).where(PolishChange.id == change_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, detail="Change not found")
    c.status = "rejected"
    await db.commit()
    return {"ok": True}

"""任务 API - 取消等通用操作"""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务（目前支持 imagegen 任务）"""
    from app.api.v1.imagegen import _tasks

    if task_id not in _tasks:
        raise HTTPException(404, detail="Task not found")
    _tasks[task_id]["_cancelled"] = True
    if _tasks[task_id]["status"] == "pending":
        _tasks[task_id]["status"] = "cancelled"
    return {"ok": True}

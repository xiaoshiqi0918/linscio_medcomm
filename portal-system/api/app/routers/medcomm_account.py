"""MedComm v3 账号迁移申请"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.medcomm_models import MedcommAccountMigrationRequest
from app.schemas.medcomm import MedcommMigrationRequestBody
from app.services.medcomm_auth_service import decode_session_token, get_user_by_id

router = APIRouter(prefix="/medcomm/account", tags=["medcomm-account"])
security = HTTPBearer(auto_error=False)


@router.post("/migration-request")
async def migration_request(
    body: MedcommMigrationRequestBody,
    db: AsyncSession = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security),
):
    """提交账号迁移申请（客服处理）"""
    if not cred or not cred.credentials:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = decode_session_token(cred.credentials.strip())
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的登录凭证")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    row = MedcommAccountMigrationRequest(
        from_user_id=user.id,
        to_credential=body.to_credential.strip()[:255],
        reason=(body.reason or "")[:2000],
        status="pending",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "success": True,
        "request_id": row.id,
        "message": "申请已提交，客服将在 1-3 个工作日内处理",
    }

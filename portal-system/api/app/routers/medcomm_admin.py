"""
MedComm 管理接口：账号迁移审批等
需管理员登录（admin_token）
"""
import re
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.medcomm_models import (
    MedcommUser,
    MedcommUserLicense,
    MedcommUserSpecialty,
    MedcommAccountMigrationRequest,
    MedcommSecurityLimit,
)
from app.services.medcomm_auth_service import hash_password
from app.routers.admin import get_current_admin
from app.models import AdminUser

router = APIRouter(prefix="/admin/medcomm", tags=["medcomm-admin"])


def _infer_credential_type(credential: str) -> str:
    """根据格式推断 credential 类型"""
    s = (credential or "").strip()
    if "@" in s:
        return "email"
    if re.match(r"^1[3-9]\d{9}$", re.sub(r"\D", "", s)):
        return "phone"
    return "username"


def _normalize_credential(credential: str, cred_type: str) -> str:
    s = (credential or "").strip()
    if cred_type == "email":
        return s.lower()
    if cred_type == "phone":
        return re.sub(r"\D", "", s) or s
    return s.lower()


@router.get("/migration-requests")
async def list_migration_requests(
    status: str | None = Query(None, description="pending | approved | rejected"),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """列出 MedComm 账号迁移申请"""
    q = select(
        MedcommAccountMigrationRequest,
        MedcommUser.email.label("from_email"),
        MedcommUser.phone.label("from_phone"),
        MedcommUser.username.label("from_username"),
    ).join(MedcommUser, MedcommAccountMigrationRequest.from_user_id == MedcommUser.id)
    if status:
        q = q.where(MedcommAccountMigrationRequest.status == status)
    q = q.order_by(MedcommAccountMigrationRequest.created_at.desc())
    r = await db.execute(q)
    rows = r.all()
    return [
        {
            "id": mr.id,
            "from_user_id": mr.from_user_id,
            "from_credential": fe or fp or fu or str(mr.from_user_id),
            "to_credential": mr.to_credential,
            "reason": mr.reason,
            "status": mr.status,
            "handled_by": mr.handled_by,
            "handled_at": mr.handled_at.isoformat() if mr.handled_at else None,
            "created_at": mr.created_at.isoformat() if mr.created_at else None,
        }
        for mr, fe, fp, fu in rows
    ]


@router.post("/migration-requests/{request_id}/approve")
async def approve_migration(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """审批通过：创建/查找目标账号，迁移 user_licenses 和 user_specialties"""
    r = await db.execute(
        select(MedcommAccountMigrationRequest, MedcommUser).join(
            MedcommUser, MedcommAccountMigrationRequest.from_user_id == MedcommUser.id
        ).where(
            MedcommAccountMigrationRequest.id == request_id,
            MedcommAccountMigrationRequest.status == "pending",
        )
    )
    row = r.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="申请不存在或已处理")
    req, from_user = row
    to_cred = (req.to_credential or "").strip()
    if not to_cred:
        raise HTTPException(status_code=400, detail="目标凭证为空")

    cred_type = _infer_credential_type(to_cred)
    cred_normalized = _normalize_credential(to_cred, cred_type)
    now = datetime.now(timezone.utc)

    # 查找或创建目标用户
    cond = (
        MedcommUser.email == cred_normalized if cred_type == "email"
        else MedcommUser.phone == cred_normalized if cred_type == "phone"
        else MedcommUser.username == cred_normalized
    )
    r2 = await db.execute(select(MedcommUser).where(cond))
    to_user = r2.scalar_one_or_none()
    if not to_user:
        to_user = MedcommUser(
            username=cred_normalized if cred_type == "username" else None,
            email=cred_normalized if cred_type == "email" else None,
            phone=cred_normalized if cred_type == "phone" else None,
            password_hash=hash_password(secrets.token_urlsafe(16)),
        )
        db.add(to_user)
        await db.flush()

    if to_user.id == from_user.id:
        raise HTTPException(status_code=400, detail="目标账号与源账号相同")

    # 迁移 user_licenses（覆盖目标用户的 license，因为通常目标尚无 license）
    await db.execute(
        update(MedcommUserLicense).where(
            MedcommUserLicense.user_id == from_user.id
        ).values(user_id=to_user.id, updated_at=now)
    )
    # 迁移 user_specialties
    await db.execute(
        update(MedcommUserSpecialty).where(
            MedcommUserSpecialty.user_id == from_user.id
        ).values(user_id=to_user.id)
    )
    # 更新申请状态
    req.status = "approved"
    req.handled_by = admin.id
    req.handled_at = now
    await db.commit()
    return {
        "success": True,
        "message": "迁移已完成",
        "to_user_id": to_user.id,
        "to_credential": to_cred,
    }


@router.post("/security-limits/unlock")
async def unlock_security_limit(
    limit_type: str,
    identifier: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """解锁安全限制（如 activate_user 永久锁）"""
    r = await db.execute(
        select(MedcommSecurityLimit).where(
            MedcommSecurityLimit.limit_type == limit_type,
            MedcommSecurityLimit.identifier == identifier,
        )
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    row.fail_count = 0
    row.locked_until = None
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "message": "已解锁"}


@router.post("/migration-requests/{request_id}/reject")
async def reject_migration(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """审批拒绝"""
    r = await db.execute(
        select(MedcommAccountMigrationRequest).where(
            MedcommAccountMigrationRequest.id == request_id,
            MedcommAccountMigrationRequest.status == "pending",
        )
    )
    req = r.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在或已处理")
    now = datetime.now(timezone.utc)
    req.status = "rejected"
    req.handled_by = admin.id
    req.handled_at = now
    await db.commit()
    return {"success": True, "message": "已拒绝"}

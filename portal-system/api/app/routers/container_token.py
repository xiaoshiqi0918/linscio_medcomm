# 全栈方案 §3.1：POST /api/v1/auth/container-token 与限流
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PortalUser, ContainerToken, ContainerMachineBinding
from app.schemas.container_token import ContainerTokenRequest, ContainerTokenResponse
from app.services.auth_service import verify_password
from app.services.account_service import compute_account_status

router = APIRouter(prefix="/auth", tags=["auth"])

# 套餐 -> 模块列表（与系统端 is_module_enabled 一致，使用 analyzer 而非 data_analyzer）
PLAN_MODULES = {
    "personal": ["schola", "medcomm", "qcc"],
    "team": ["schola", "medcomm", "qcc", "literature", "analyzer"],
    "enterprise": ["schola", "medcomm", "qcc", "literature", "analyzer", "image_studio"],
    "beta": ["schola", "medcomm", "qcc", "literature", "analyzer", "image_studio"],  # 内测与旗舰一致
}

# 限流：每 IP 每分钟 20 次；每账号每小时 60 次（内存计数）
_ip_timestamps: dict[str, list[float]] = defaultdict(list)
_user_timestamps: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_IP_PER_MIN = 20
RATE_LIMIT_USER_PER_HOUR = 60
CLEANUP_AFTER = 3700  # 秒，略大于 1 小时


def _check_rate_limit_ip(ip: str) -> None:
    now = time.time()
    lst = _ip_timestamps[ip]
    lst[:] = [t for t in lst if now - t < 60]
    if len(lst) >= RATE_LIMIT_IP_PER_MIN:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "message": "请求过于频繁，请稍后重试"},
        )
    lst.append(now)


def _check_rate_limit_user(username_lower: str) -> None:
    now = time.time()
    lst = _user_timestamps[username_lower]
    lst[:] = [t for t in lst if now - t < 3600]
    if len(lst) >= RATE_LIMIT_USER_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "message": "该账号请求过于频繁，请稍后重试"},
        )
    lst.append(now)


@router.post("/container-token", response_model=ContainerTokenResponse)
async def issue_container_token(
    body: ContainerTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # 限流
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit_ip(client_ip)
    _check_rate_limit_user(body.username.strip().lower())

    # 1. 查找用户（用户名不区分大小写，视为邮箱）
    uname = body.username.strip()
    result = await db.execute(
        select(PortalUser).where(PortalUser.username.ilike(uname))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_credentials",
                "message": "用户名或密码错误，请检查配置",
            },
        )

    # 2. 已注销
    if getattr(user, "account_status", None) == "cancelled":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "account_suspended",
                "message": "您的账号已注销，如有疑问请联系 support@linscio.com.cn；续费请前往 api.linscio.com.cn",
            },
        )

    # 3. 验证密码
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_credentials",
                "message": "用户名或密码错误，请检查配置",
            },
        )

    # 4. 实时计算账号状态
    status = compute_account_status(user)
    if status == "suspended":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "account_suspended",
                "message": "您的维护服务已到期，请前往 api.linscio.com.cn 续费后继续使用",
            },
        )
    # 内测账号（plan == "beta"）业务上视为已购买，不返回 not_purchased，直接发 token
    if status == "registered" and getattr(user, "plan", None) != "beta":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "not_purchased",
                "message": "账号未购买套餐，请前往 www.linscio.com.cn 购买",
            },
        )

    # 5. 机器绑定数检查（0 = 不限）
    machine_limit = getattr(user, "machine_limit", 1) or 0
    if machine_limit > 0:
        count_result = await db.execute(
            select(ContainerMachineBinding).where(ContainerMachineBinding.user_id == user.id)
        )
        bindings = count_result.scalars().all()
        bound_count = len(bindings)
        machine_ids = {b.machine_id for b in bindings}
        is_new_machine = body.machine_id.strip() not in machine_ids
        if is_new_machine and bound_count >= machine_limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "machine_limit_exceeded",
                    "message": "绑定机器数已达套餐上限，请在用户中心解绑旧机器",
                },
            )

    # 6. 吊销同 user + machine 的旧令牌
    await db.execute(
        update(ContainerToken)
        .where(
            ContainerToken.user_id == user.id,
            ContainerToken.machine_id == body.machine_id.strip(),
        )
        .values(is_revoked=True)
    )
    await db.flush()

    # 7. 生成新令牌
    token_value = "ls_tok_" + secrets.token_hex(16)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)
    issued_at = now

    ct = ContainerToken(
        user_id=user.id,
        token=token_value,
        machine_id=body.machine_id.strip(),
        expires_at=expires_at,
        issued_at=issued_at,
        is_revoked=False,
    )
    db.add(ct)
    await db.flush()

    # 8. upsert container_machine_bindings
    plan = getattr(user, "plan", None) or "personal"
    modules = PLAN_MODULES.get(plan, PLAN_MODULES["personal"])
    if not modules:
        modules = ["schola", "medcomm", "qcc"]

    existing = await db.execute(
        select(ContainerMachineBinding).where(
            ContainerMachineBinding.user_id == user.id,
            ContainerMachineBinding.machine_id == body.machine_id.strip(),
        )
    )
    binding = existing.scalar_one_or_none()
    if binding:
        binding.last_seen = now
    else:
        binding = ContainerMachineBinding(
            user_id=user.id,
            machine_id=body.machine_id.strip(),
            first_seen=now,
            last_seen=now,
        )
        db.add(binding)
    await db.flush()

    # 9. 构造响应
    response = ContainerTokenResponse(
        token=token_value,
        plan=plan,
        modules=modules,
        expires_at=expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        issued_at=issued_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        username=user.username,
    )
    if status == "grace":
        maintenance_until = getattr(user, "maintenance_until", None)
        date_str = maintenance_until.strftime("%Y-%m-%d") if maintenance_until else ""
        response.warning = (
            "您的维护服务已于 {} 到期，当前处于宽限期。请尽快前往 api.linscio.com.cn 续费，以免服务中断。".format(date_str)
        )
    return response

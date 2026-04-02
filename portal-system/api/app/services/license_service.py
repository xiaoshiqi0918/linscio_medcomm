import binascii
import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LicenseKey, PortalUser, Plan, BillingPeriod, ModuleDefinition
from app.constants import CONTROLLED_MODULES_SEED

# 旧格式字符集（排除易混淆 O/0/I/1）
LICENSE_CHARS = string.ascii_uppercase + string.digits
for c in "O0I1":
    LICENSE_CHARS = LICENSE_CHARS.replace(c, "")

# 新格式 LS- 字符集（排除 O/0/I/1/L）
CHARSET_V2 = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LS_PATTERN = re.compile(
    r"^LS-([BPTED])([MQYI])-([A-Z2-9]{4})-([A-Z2-9]{6})-([A-Z2-9]{2})$",
    re.IGNORECASE,
)


def generate_license_code() -> str:
    parts = []
    for _ in range(5):
        parts.append("".join(secrets.choice(LICENSE_CHARS) for _ in range(4)))
    return "LINSCIO-" + "-".join(parts)


def generate_license_code_v2(plan_char: str, period_char: str) -> str:
    plan_char = plan_char.upper()
    period_char = period_char.upper()
    ts = int(datetime.now(timezone.utc).timestamp())
    ts_hash = "".join(CHARSET_V2[(ts >> (i * 5)) & 0x1F] for i in range(4))
    random_part = "".join(secrets.choice(CHARSET_V2) for _ in range(6))
    body = f"{plan_char}{period_char}-{ts_hash}-{random_part}"
    crc = binascii.crc32(body.encode()) & 0xFFFF
    checksum = CHARSET_V2[crc % len(CHARSET_V2)] + CHARSET_V2[(crc >> 5) % len(CHARSET_V2)]
    return f"LS-{body}-{checksum}"


def validate_license_format(code: str) -> tuple[bool, str | None]:
    code = code.strip().upper()
    if code.startswith("LS-"):
        m = LS_PATTERN.match(code)
        if not m:
            return False, "授权码格式错误，请检查输入"
        plan_char, period_char, ts_hash, random_part, checksum = m.groups()
        body = f"{plan_char}{period_char}-{ts_hash}-{random_part}"
        crc = binascii.crc32(body.encode()) & 0xFFFF
        expected = CHARSET_V2[crc % len(CHARSET_V2)] + CHARSET_V2[(crc >> 5) % len(CHARSET_V2)]
        if checksum.upper() != expected:
            return False, "授权码格式错误，请检查输入"
        return True, None
    if code.startswith("LINSCIO-") and len(code) == 29:
        return True, None
    return False, "授权码格式错误，请检查输入"


def parse_license_code(code: str) -> tuple[str | None, str | None]:
    code = code.strip().upper()
    if not code.startswith("LS-"):
        return None, None
    m = LS_PATTERN.match(code)
    if not m:
        return None, None
    return m.group(1).upper(), m.group(2).upper()


async def mask_to_module_codes(db: AsyncSession, module_mask: int | None) -> list[str]:
    """将 module_mask 解码为模块 code 列表，供主产品 is_module_enabled 使用。"""
    if module_mask is None or module_mask == 0:
        return []
    result = await db.execute(
        select(ModuleDefinition).where(
            ModuleDefinition.is_controlled == True,
            ModuleDefinition.bit_position >= 0,
        ).order_by(ModuleDefinition.bit_position)
    )
    modules = result.scalars().all()
    codes = []
    for mod in modules:
        if (module_mask >> mod.bit_position) & 1:
            codes.append(mod.code)
    return codes


async def get_module_mask(db: AsyncSession, plan_code: str) -> int:
    result = await db.execute(
        select(ModuleDefinition).where(
            ModuleDefinition.is_controlled == True,
            ModuleDefinition.bit_position >= 0,
        ).order_by(ModuleDefinition.bit_position)
    )
    modules = result.scalars().all()
    mask = 0
    for mod in modules:
        enabled = False
        if plan_code == "basic":
            enabled = getattr(mod, "basic_enabled", False)
        elif plan_code == "professional" or plan_code == "pro":
            enabled = getattr(mod, "pro_enabled", False) or getattr(mod, "team_enabled", False)
        elif plan_code == "team":
            enabled = getattr(mod, "team_enabled", False)
        elif plan_code == "enterprise":
            enabled = getattr(mod, "enterprise_enabled", True)
        elif plan_code == "beta":
            enabled = getattr(mod, "beta_enabled", True)
        else:
            enabled = getattr(mod, "pro_enabled", False) or getattr(mod, "team_enabled", False)
        if enabled:
            mask |= 1 << mod.bit_position
    return mask


async def ensure_controlled_modules(db: AsyncSession) -> int:
    """确保 6 个受控模块存在于 module_definitions；已存在则跳过。返回本次新增数量。不提交事务。"""
    added = 0
    for code, name, bit_position, basic_enabled, pro_enabled, team_enabled, enterprise_enabled, beta_enabled in CONTROLLED_MODULES_SEED:
        r = await db.execute(select(ModuleDefinition).where(ModuleDefinition.code == code))
        if r.scalar_one_or_none():
            continue
        db.add(ModuleDefinition(
            code=code,
            name=name,
            bit_position=bit_position,
            is_controlled=True,
            basic_enabled=basic_enabled,
            pro_enabled=pro_enabled,
            team_enabled=team_enabled,
            enterprise_enabled=enterprise_enabled,
            beta_enabled=beta_enabled,
            sort_order=bit_position,
        ))
        added += 1
    return added


async def create_license_batch(
    db: AsyncSession,
    count: int,
    months_valid: int,
    plan_type: str,
    created_by: str,
    notes: str | None = None,
) -> list[LicenseKey]:
    expires_at = datetime.now(timezone.utc) + timedelta(days=months_valid * 30)
    keys = []
    for _ in range(count):
        code = generate_license_code()
        key = LicenseKey(
            code=code,
            plan_type=plan_type,
            created_by=created_by,
            expires_at=expires_at,
            notes=notes,
        )
        db.add(key)
        keys.append(key)
    await db.flush()
    return keys


async def create_license_batch_v2(
    db: AsyncSession,
    count: int,
    plan_code: str,
    period_code: str,
    created_by: str,
    notes: str | None = None,
) -> list[LicenseKey]:
    plan_res = await db.execute(select(Plan).where(Plan.code == plan_code))
    plan = plan_res.scalar_one_or_none()
    period_res = await db.execute(select(BillingPeriod).where(BillingPeriod.code == period_code))
    period = period_res.scalar_one_or_none()
    if not plan or not period:
        raise ValueError("套餐或周期不存在")
    months = period.months
    expires_at = datetime.now(timezone.utc) + timedelta(days=months * 30)
    module_mask = await get_module_mask(db, plan_code)
    keys = []
    for _ in range(count):
        code = generate_license_code_v2(plan.plan_char, period.period_char)
        key = LicenseKey(
            code=code,
            plan_type=plan_code,
            plan_id=plan.id,
            period_id=period.id,
            module_mask=module_mask,
            machine_limit=plan.machine_limit,
            concurrent_limit=plan.concurrent_limit,
            pull_limit_monthly=plan.pull_limit_monthly,
            created_by=created_by,
            expires_at=expires_at,
            notes=notes,
        )
        db.add(key)
        keys.append(key)
    await db.flush()
    return keys


async def activate_license(db: AsyncSession, code: str, user_id: str) -> LicenseKey | None:
    code = code.strip().upper()
    ok, _err = validate_license_format(code)
    if not ok:
        return None
    result = await db.execute(
        select(LicenseKey).where(
            LicenseKey.code == code,
            LicenseKey.is_used == False,
            LicenseKey.is_revoked == False,
            LicenseKey.expires_at > datetime.now(timezone.utc),
        )
    )
    license_key = result.scalar_one_or_none()
    if not license_key:
        return None
    license_key.is_used = True
    license_key.assigned_to = user_id
    license_key.activated_at = datetime.now(timezone.utc)
    await db.flush()
    return license_key


async def lookup_license_activate_status(db: AsyncSession, code: str) -> tuple[LicenseKey | None, str | None]:
    result = await db.execute(select(LicenseKey).where(LicenseKey.code == code.strip().upper()))
    key = result.scalar_one_or_none()
    if not key:
        return None, "授权码无效"
    if key.is_revoked:
        return None, "该授权码已失效，请联系管理员"
    if key.is_used:
        return None, "该授权码已被激活，如有疑问请联系客服"
    if key.expires_at <= datetime.now(timezone.utc):
        return None, "该授权码已过期，请重新购买"
    return key, None


async def validate_license_plan_period(db: AsyncSession, code: str) -> str | None:
    """② 解析套餐码与周期码：LS- 码须能解析且套餐/周期在库中存在，否则返回「授权码无效」。"""
    code = code.strip().upper()
    if not code.startswith("LS-"):
        return None
    plan_char, period_char = parse_license_code(code)
    if not plan_char or not period_char:
        return "授权码无效"
    p = await db.execute(select(Plan).where(Plan.plan_char == plan_char))
    if not p.scalar_one_or_none():
        return "授权码无效"
    bp = await db.execute(select(BillingPeriod).where(BillingPeriod.period_char == period_char))
    if not bp.scalar_one_or_none():
        return "授权码无效"
    return None

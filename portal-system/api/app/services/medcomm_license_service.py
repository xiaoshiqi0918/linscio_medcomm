"""
LinScio MedComm v3 授权码服务
- 格式：LINSCIO-XXXX-XXXX-XXXX
- 类型：basic（基础版）/ specialty（学科包）
- 试用码：is_trial=1
"""
import re
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.medcomm_models import (
    MedcommLicenseCode,
    MedcommUserLicense,
    MedcommUserSpecialty,
    MedcommUser,
)

# 授权码格式：LINSCIO-XXXX-XXXX-XXXX 或 LINSCIO-XXXX-XXXX-XXXX-XXXX
LICENSE_PATTERN_3 = re.compile(
    r"^LINSCIO-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})$",
    re.IGNORECASE,
)
LICENSE_PATTERN_4 = re.compile(
    r"^LINSCIO-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})$",
    re.IGNORECASE,
)


def normalize_license_code(code: str) -> str:
    """规范化授权码：去空格、转大写、自动加横杠（支持 3 段或 4 段）"""
    s = re.sub(r"[\s\-]", "", (code or "").upper())
    if not s:
        return ""
    # 提取 LINSCIO 后的数字字母部分
    if s.startswith("LINSCIO") and len(s) >= 19:
        rest = s[7:]
        if len(rest) == 12:
            return f"LINSCIO-{rest[0:4]}-{rest[4:8]}-{rest[8:12]}"
        if len(rest) == 16:
            return f"LINSCIO-{rest[0:4]}-{rest[4:8]}-{rest[8:12]}-{rest[12:16]}"
    if len(s) == 12:
        return f"LINSCIO-{s[0:4]}-{s[4:8]}-{s[8:12]}"
    if len(s) == 16:
        return f"LINSCIO-{s[0:4]}-{s[4:8]}-{s[8:12]}-{s[12:16]}"
    if "-" in (code or ""):
        return re.sub(r"\s", "", (code or "").upper())
    return s


def validate_license_format(code: str) -> tuple[bool, str | None]:
    """
    校验授权码格式
    返回 (是否有效, 错误信息)
    """
    s = normalize_license_code(code)
    if not s or len(s) < 10:
        return False, "授权码格式不正确"
    if not (LICENSE_PATTERN_3.match(s) or LICENSE_PATTERN_4.match(s)):
        return False, "授权码格式不正确"
    return True, None


async def lookup_license_code(
    db: AsyncSession, code: str
) -> MedcommLicenseCode | None:
    """查询授权码（支持 3 段与 4 段格式，优先精确匹配）"""
    s = normalize_license_code(code)
    r = await db.execute(select(MedcommLicenseCode).where(MedcommLicenseCode.code == s))
    row = r.scalar_one_or_none()
    if row:
        return row
    # 4 段格式可能对应 DB 中的 3 段码（最后一段为校验等）
    if s.count("-") == 4:
        short = "-".join(s.split("-")[:4])
        r2 = await db.execute(select(MedcommLicenseCode).where(MedcommLicenseCode.code == short))
        return r2.scalar_one_or_none()
    return None


def compute_new_expires_at(
    current_expires: datetime | None,
    duration_months: int,
    now: datetime,
) -> datetime:
    """叠加逻辑：new = MAX(now, current) + duration_months"""
    base = now
    if current_expires and current_expires > now:
        base = current_expires
    # 简单月数加法（不考虑月末）
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=duration_months * 30)


# 学科 ID -> 名称 映射（可后续从配置/表加载）
SPECIALTY_NAMES = {
    "endocrine": "内分泌科",
    "cardiology": "心内科",
    "neurology": "神经内科",
}

#!/usr/bin/env python3
"""
预置 MedComm v3 测试授权码
格式：LINSCIO-XXXX-XXXX-XXXX
执行：cd api && python scripts/seed_medcomm_license.py
或：docker compose exec linscio-api python scripts/seed_medcomm_license.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.medcomm_models import MedcommLicenseCode


def gen_code() -> str:
    import random
    import string
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 排除 O0I1L
    parts = ["".join(random.choices(chars, k=4)) for _ in range(3)]
    return f"LINSCIO-{parts[0]}-{parts[1]}-{parts[2]}"


async def main():
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(MedcommLicenseCode).limit(1))
        if r.scalar_one_or_none():
            print("已存在 MedComm 授权码，跳过")
            return
        for _ in range(3):
            code = gen_code()
            lc = MedcommLicenseCode(
                code=code,
                license_type="basic",
                duration_months=12,
                is_trial=0,
            )
            db.add(lc)
            print(f"已创建: {code}")
        await db.commit()
        print("完成")


if __name__ == "__main__":
    asyncio.run(main())

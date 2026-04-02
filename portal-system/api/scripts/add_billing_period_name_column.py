"""
为 billing_periods 表增加 name 列（可选显示名，供管理后台配置）。
与 api/scripts/migrate_billing_period_name.sql 等效；Docker 部署推荐使用 SQL 迁移：
  docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_billing_period_name.sql
本地跑 API 且无 psql 时可用本脚本：
  cd api && python scripts/add_billing_period_name_column.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(text(
            "ALTER TABLE billing_periods ADD COLUMN IF NOT EXISTS name VARCHAR(60)"
        ))
        await db.commit()
    print("billing_periods.name 列已就绪（已存在则跳过）")


if __name__ == "__main__":
    asyncio.run(main())

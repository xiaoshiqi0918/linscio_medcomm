"""
分级授权预置数据：套餐、付费周期、受控模块。用法：
  cd api && python scripts/seed_plans_periods_modules.py
需已设置 .env 中 DATABASE_URL，且数据库已建表（含 plans、billing_periods、module_definitions）。
与《LinScio_AI_分级授权与镜像管控方案_v5》第九章预置数据一致。
"""
import asyncio
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Plan, BillingPeriod, ModuleDefinition
from app.constants import CONTROLLED_MODULES_SEED


async def main():
    async with AsyncSessionLocal() as db:
        # 套餐
        plans_data = [
            ("basic", "基础版", "B", 1, 1, 20, Decimal("49.9")),
            ("professional", "专业版", "P", 1, 1, 30, Decimal("149.9")),
            ("team", "团队版", "T", 10, 10, None, Decimal("999.9")),
            ("enterprise", "旗舰版", "E", 0, 0, None, Decimal("9999.9")),
            ("beta", "内测版", "D", 0, 0, None, Decimal("0")),
        ]
        for code, name, plan_char, ml, cl, plm, price in plans_data:
            r = await db.execute(select(Plan).where(Plan.code == code))
            if r.scalar_one_or_none():
                continue
            db.add(Plan(
                code=code, name=name, plan_char=plan_char,
                machine_limit=ml, concurrent_limit=cl, pull_limit_monthly=plm,
                price_monthly=price,
            ))
        await db.flush()

        # 付费周期
        periods_data = [
            ("monthly", "月付", "M", 1, Decimal("1.00")),
            ("quarterly", "季付", "Q", 3, Decimal("0.90")),
            ("yearly", "年付", "Y", 12, Decimal("0.80")),
            ("internal", "内测", "I", 1, Decimal("0.00")),
        ]
        for code, period_name, period_char, months, rate in periods_data:
            r = await db.execute(select(BillingPeriod).where(BillingPeriod.code == code))
            if r.scalar_one_or_none():
                continue
            db.add(BillingPeriod(code=code, name=period_name, period_char=period_char, months=months, discount_rate=rate))
        await db.flush()

        # 受控模块：前 6 个与 app.constants 一致；后 9 个为非受控展示用
        for code, name, bit_position, basic_enabled, pro_enabled, team_enabled, enterprise_enabled, beta_enabled in CONTROLLED_MODULES_SEED:
            r = await db.execute(select(ModuleDefinition).where(ModuleDefinition.code == code))
            if r.scalar_one_or_none():
                continue
            db.add(ModuleDefinition(
                code=code, name=name, bit_position=bit_position,
                is_controlled=True, basic_enabled=basic_enabled,
                pro_enabled=pro_enabled, team_enabled=team_enabled,
                enterprise_enabled=enterprise_enabled, beta_enabled=beta_enabled,
                sort_order=bit_position,
            ))
        other_modules = [
            ("creation_lib", "创作库", -1, False, False, False, False, False, False),
            ("project_mat", "立项材料", -2, False, False, False, False, False, False),
            ("knowledge_base", "知识库", -3, False, False, False, False, False, False),
            ("analysis_rpt", "分析报告", -4, False, False, False, False, False, False),
            ("polish", "润色修订", -5, False, False, False, False, False, False),
            ("submission", "投稿发表", -6, False, False, False, False, False, False),
            ("settings", "设置", -7, False, False, False, False, False, False),
            ("agent_config", "智能体配置", -8, False, False, False, False, False, False),
            ("personalize", "个性化", -9, False, False, False, False, False, False),
        ]
        for code, name, bit_position, controlled, basic_enabled, pro_enabled, team_enabled, enterprise_enabled, beta_enabled in other_modules:
            r = await db.execute(select(ModuleDefinition).where(ModuleDefinition.code == code))
            if r.scalar_one_or_none():
                continue
            db.add(ModuleDefinition(
                code=code, name=name, bit_position=bit_position,
                is_controlled=controlled, basic_enabled=basic_enabled,
                pro_enabled=pro_enabled, team_enabled=team_enabled,
                enterprise_enabled=enterprise_enabled, beta_enabled=beta_enabled,
                sort_order=bit_position,
            ))
        await db.commit()
    print("plans / billing_periods / module_definitions 预置数据已写入（已存在则跳过）")


if __name__ == "__main__":
    asyncio.run(main())

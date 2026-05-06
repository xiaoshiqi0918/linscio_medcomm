"""
推广奖励 — 被推广人首次成功下载客户端 → 推广人获得 1000 推广积分

覆盖场景：
  T1  无推广人      → 不发放
  T2  有推广人但无授权码 → 不发放
  T3  有推广人 + 授权码（首次）→ 发放 1000，写 ReferralLog(license_download)
  T4  幂等：同一对（推广人↔被推广人）二次下载 → 不重复发放
  T5  promo_credits 累加（不覆盖原有余额），promo_credits_expire_at 被刷新
  T6  奖励额度可由 settings.referral_license_download_reward 配置
  T7  推广人不存在（数据异常） → 不抛异常，返回 False

运行：
  cd backend && pytest tests/test_referral_license_download.py -v
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio


# 用 desktop 模式跑测试：app.core.database 加载时不会塞 PG 连接池参数
os.environ.setdefault("DEPLOYMENT_MODE", "desktop")


# ────────────────────────────────────────────
# Fixtures：每个测试一份独立的 in-memory SQLite + 表结构
# ────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session():
    """每个测试一份独立的 in-memory SQLite + 全部表结构。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models import Base
    from app.models.user import User  # noqa: F401  确保模型注册
    from app.models.billing import LicenseCode, DownloadLog  # noqa: F401
    from app.models.referral import ReferralLog  # noqa: F401

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


async def _make_user(session, *, display_name: str, referred_by: int | None = None,
                    promo_credits: Decimal = Decimal("0"),
                    promo_expire: datetime | None = None) -> "User":  # type: ignore[name-defined]
    from app.models.user import User
    u = User(
        display_name=display_name,
        referred_by=referred_by,
        promo_credits=promo_credits,
        promo_credits_expire_at=promo_expire,
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def _add_license(session, owner_id: int) -> "LicenseCode":  # type: ignore[name-defined]
    from app.models.billing import LicenseCode
    lc = LicenseCode(
        code=f"LINSCIO-TEST-{owner_id:04d}-AAAA",
        owner_id=owner_id,
        credit_type="credits",
        credits_cost=Decimal("600"),
        source="redeem",
    )
    session.add(lc)
    await session.commit()
    await session.refresh(lc)
    return lc


# ────────────────────────────────────────────
# 测试用例
# ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t1_no_referrer_not_granted(db_session):
    """T1：被推广人没有推广人 → 不发放"""
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    user = await _make_user(db_session, display_name="独立用户")
    await _add_license(db_session, user.id)

    granted = await grant_referral_license_download_reward(user.id, db_session)
    assert granted is False


@pytest.mark.asyncio
async def test_t2_referrer_but_no_license_not_granted(db_session):
    """T2：有推广人但名下没有授权码 → 不发放"""
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    referrer = await _make_user(db_session, display_name="推广人 A")
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)

    granted = await grant_referral_license_download_reward(referred.id, db_session)
    assert granted is False
    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits or 0)) == Decimal("0")


@pytest.mark.asyncio
async def test_t3_first_grant_succeeds(db_session):
    """T3：有推广人 + 授权码 → 首次发放成功，写 ReferralLog(license_download)"""
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.referral import ReferralLog
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    referrer = await _make_user(db_session, display_name="推广人 A")
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)
    await _add_license(db_session, referred.id)

    expected = Decimal(str(settings.referral_license_download_reward))

    granted = await grant_referral_license_download_reward(
        referred.id, db_session, source_id=12345
    )
    await db_session.commit()
    assert granted is True

    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits)) == expected
    assert referrer.promo_credits_expire_at is not None
    # SQLite 回读为 naive datetime；统一去掉时区再比较
    expire_naive = referrer.promo_credits_expire_at.replace(tzinfo=None) \
        if referrer.promo_credits_expire_at.tzinfo else referrer.promo_credits_expire_at
    assert expire_naive > datetime.utcnow() + timedelta(days=30)

    rows = (await db_session.execute(
        select(ReferralLog).where(ReferralLog.referrer_id == referrer.id)
    )).scalars().all()
    assert len(rows) == 1
    log = rows[0]
    assert log.trigger_type == "license_download"
    assert Decimal(str(log.reward_credits)) == expected
    assert log.referred_id == referred.id
    assert log.related_recharge_id == 12345


@pytest.mark.asyncio
async def test_t4_idempotent_second_call_skipped(db_session):
    """T4：同一对（推广人↔被推广人）二次下载 → 不重复发放，余额不变"""
    from sqlalchemy import select, func
    from app.core.config import settings
    from app.models.referral import ReferralLog
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    referrer = await _make_user(db_session, display_name="推广人 A")
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)
    await _add_license(db_session, referred.id)

    expected = Decimal(str(settings.referral_license_download_reward))

    g1 = await grant_referral_license_download_reward(referred.id, db_session)
    await db_session.commit()
    assert g1 is True

    g2 = await grant_referral_license_download_reward(referred.id, db_session)
    await db_session.commit()
    assert g2 is False

    g3 = await grant_referral_license_download_reward(referred.id, db_session)
    await db_session.commit()
    assert g3 is False

    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits)) == expected

    cnt = await db_session.scalar(
        select(func.count(ReferralLog.id)).where(
            ReferralLog.referrer_id == referrer.id,
            ReferralLog.referred_id == referred.id,
            ReferralLog.trigger_type == "license_download",
        )
    )
    assert cnt == 1


@pytest.mark.asyncio
async def test_t5_accumulates_existing_promo_balance(db_session):
    """T5：推广人原有 promo_credits 余额被累加，而不是覆盖"""
    from app.core.config import settings
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    initial = Decimal("250.5")
    # 用 naive datetime 写入（与 SQLite 存储格式一致）
    referrer = await _make_user(
        db_session, display_name="推广人 A", promo_credits=initial,
        promo_expire=datetime.utcnow() + timedelta(days=10),
    )
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)
    await _add_license(db_session, referred.id)

    granted = await grant_referral_license_download_reward(referred.id, db_session)
    await db_session.commit()
    assert granted is True

    await db_session.refresh(referrer)
    expected = initial + Decimal(str(settings.referral_license_download_reward))
    assert Decimal(str(referrer.promo_credits)) == expected
    expire_naive = referrer.promo_credits_expire_at.replace(tzinfo=None) \
        if referrer.promo_credits_expire_at.tzinfo else referrer.promo_credits_expire_at
    assert expire_naive > datetime.utcnow() + timedelta(days=30)


@pytest.mark.asyncio
async def test_t6_reward_amount_configurable(db_session, monkeypatch):
    """T6：奖励额度可由 settings.referral_license_download_reward 配置"""
    from app.core.config import settings
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    monkeypatch.setattr(settings, "referral_license_download_reward", 7777, raising=True)

    referrer = await _make_user(db_session, display_name="推广人 A")
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)
    await _add_license(db_session, referred.id)

    granted = await grant_referral_license_download_reward(referred.id, db_session)
    await db_session.commit()
    assert granted is True

    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits)) == Decimal("7777")


@pytest.mark.asyncio
async def test_t7_referrer_missing_returns_false(db_session):
    """T7：referred_by 指向不存在的用户 → 安全返回 False，不抛异常"""
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    referred = await _make_user(db_session, display_name="孤儿 B", referred_by=999999)
    await _add_license(db_session, referred.id)

    granted = await grant_referral_license_download_reward(referred.id, db_session)
    assert granted is False


@pytest.mark.asyncio
async def test_t8_zero_reward_disables_grant(db_session, monkeypatch):
    """T8：当奖励额度被显式调整为 0/负数 → 不发放，不写日志"""
    from sqlalchemy import select, func
    from app.core.config import settings
    from app.models.referral import ReferralLog
    from app.services.credit.referral_rewards import grant_referral_license_download_reward

    monkeypatch.setattr(settings, "referral_license_download_reward", 0, raising=True)

    referrer = await _make_user(db_session, display_name="推广人 A")
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)
    await _add_license(db_session, referred.id)

    granted = await grant_referral_license_download_reward(referred.id, db_session)
    await db_session.commit()
    assert granted is False

    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits or 0)) == Decimal("0")
    cnt = await db_session.scalar(select(func.count(ReferralLog.id)))
    assert cnt == 0


# ════════════════════════════════════════════════════════════════
# T9：端到端集成测试 — 调用 download_software 路由函数验证完整链路
# ════════════════════════════════════════════════════════════════


class _FakeRequest:
    """伪造 FastAPI Request：只暴露 client.host 和 headers。"""
    def __init__(self):
        self.client = type("C", (), {"host": "127.0.0.1"})()
        self.headers = {"user-agent": "pytest/1.0"}


@pytest.mark.asyncio
async def test_t9_e2e_download_software_triggers_reward(db_session, monkeypatch):
    """
    端到端：
    A 邀请 B → B 兑换授权码 → B 调 POST /download/software
    应触发 grant_referral_license_download_reward，A 余额 +1000。
    第二次下载不应再加。
    """
    from sqlalchemy import select, func
    from app.core.config import settings
    from app.models.referral import ReferralLog
    from app.api.v1.download import download_software, SoftwareDownloadRequest
    import app.api.v1.download as dl_module
    import app.services.cos as cos_module

    # 构造数据
    referrer = await _make_user(db_session, display_name="推广人 A")
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)
    await _add_license(db_session, referred.id)

    # Mock COS：返回一个最简 manifest + 假的预签名 URL
    fake_manifest = {
        "products": [{
            "id": "medcomm",
            "latest_version": "1.2.3",
            "platforms": ["mac-arm64", "win-x64"],
            "download_files": {},
        }],
    }
    monkeypatch.setattr(cos_module, "read_manifest", lambda: fake_manifest, raising=True)
    monkeypatch.setattr(
        cos_module, "generate_presigned_download_url",
        lambda key, expires=7200: f"https://fake-cos.local/{key}?sig=test",
        raising=True,
    )
    # download.py 内部 from app.services.cos import ...，所以也要 patch 模块本地引用
    if hasattr(dl_module, "read_manifest"):
        monkeypatch.setattr(dl_module, "read_manifest", lambda: fake_manifest, raising=False)
    if hasattr(dl_module, "generate_presigned_download_url"):
        monkeypatch.setattr(
            dl_module, "generate_presigned_download_url",
            lambda key, expires=7200: f"https://fake-cos.local/{key}?sig=test",
            raising=False,
        )
    monkeypatch.setattr(settings, "cos_secret_id", "fake-secret", raising=False)

    expected = Decimal(str(settings.referral_license_download_reward))

    # —— 第一次下载 → 应触发奖励 ——
    resp1 = await download_software(
        SoftwareDownloadRequest(product_id="medcomm", platform="mac-arm64"),
        _FakeRequest(),  # type: ignore[arg-type]
        user=referred,
        db=db_session,
    )
    assert resp1["filename"].endswith("mac-arm64.dmg")
    assert resp1["version"] == "1.2.3"
    assert resp1["download_url"].startswith("https://fake-cos.local/")

    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits)) == expected

    # —— 第二次下载 → 不应再加 ——
    resp2 = await download_software(
        SoftwareDownloadRequest(product_id="medcomm", platform="win-x64"),
        _FakeRequest(),  # type: ignore[arg-type]
        user=referred,
        db=db_session,
    )
    assert resp2["filename"].endswith("win-x64.exe")

    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits)) == expected  # 未增加

    # ReferralLog(license_download) 仅 1 条
    cnt = await db_session.scalar(
        select(func.count(ReferralLog.id)).where(
            ReferralLog.referrer_id == referrer.id,
            ReferralLog.referred_id == referred.id,
            ReferralLog.trigger_type == "license_download",
        )
    )
    assert cnt == 1


@pytest.mark.asyncio
async def test_t10_e2e_no_license_blocks_download_and_no_reward(db_session, monkeypatch):
    """端到端：无授权码 → 接口返回 403，奖励不触发"""
    from fastapi import HTTPException
    from sqlalchemy import select, func
    from app.models.referral import ReferralLog
    from app.api.v1.download import download_software, SoftwareDownloadRequest

    referrer = await _make_user(db_session, display_name="推广人 A")
    referred = await _make_user(db_session, display_name="被推广人 B", referred_by=referrer.id)
    # 不发授权码

    with pytest.raises(HTTPException) as exc:
        await download_software(
            SoftwareDownloadRequest(product_id="medcomm", platform="mac-arm64"),
            _FakeRequest(),  # type: ignore[arg-type]
            user=referred,
            db=db_session,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "no_valid_license"

    await db_session.refresh(referrer)
    assert Decimal(str(referrer.promo_credits or 0)) == Decimal("0")
    cnt = await db_session.scalar(select(func.count(ReferralLog.id)))
    assert cnt == 0

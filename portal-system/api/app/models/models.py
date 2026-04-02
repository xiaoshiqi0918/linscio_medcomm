from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, Text, DateTime, Date, ForeignKey, BigInteger, Integer, Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid():
    return str(uuid4())


class PortalUser(Base):
    __tablename__ = "portal_users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 全栈方案 §5.1：套餐与账号状态（container-token 体系）
    plan: Mapped[str | None] = mapped_column(String(32), nullable=True)  # personal / team / enterprise / NULL
    license_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    maintenance_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account_status: Mapped[str] = mapped_column(String(32), nullable=False, default="registered")
    machine_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 0 = 不限

    license: Mapped[list["LicenseKey"]] = relationship(back_populates="assigned_user", foreign_keys="LicenseKey.assigned_to")
    registry_credential: Mapped["RegistryCredential | None"] = relationship(back_populates="user", uselist=False)


class ModuleDefinition(Base):
    __tablename__ = "module_definitions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bit_position: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    is_controlled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    basic_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pro_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    team_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enterprise_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # 旗舰版
    beta_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # 内测版
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    plan_char: Mapped[str] = mapped_column(String(1), unique=True, nullable=False)
    machine_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    concurrent_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pull_limit_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BillingPeriod(Base):
    __tablename__ = "billing_periods"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    period_char: Mapped[str] = mapped_column(String(1), unique=True, nullable=False)
    months: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=1, nullable=False)


class LicenseKey(Base):
    __tablename__ = "license_keys"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(String(30), default="standard", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 作废后不可激活
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    plan_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("plans.id"), nullable=True)
    period_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("billing_periods.id"), nullable=True)
    module_mask: Mapped[int | None] = mapped_column(Integer, nullable=True)
    machine_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    concurrent_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pull_limit_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replace_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)  # 当前更换周期起始日（365 天一轮）
    replace_count_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 本周期已解绑次数

    plan: Mapped["Plan | None"] = relationship(foreign_keys=[plan_id])
    period: Mapped["BillingPeriod | None"] = relationship(foreign_keys=[period_id])
    assigned_user: Mapped["PortalUser | None"] = relationship(back_populates="license", foreign_keys=[assigned_to])


class RegistryCredential(Base):
    __tablename__ = "registry_credentials"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), unique=True, nullable=False)
    license_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("license_keys.id"), nullable=True)
    registry_username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    registry_password_enc: Mapped[str] = mapped_column(String(500), nullable=False)
    allowed_image_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)), nullable=True)
    pull_count_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pull_count_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["PortalUser"] = relationship(back_populates="registry_credential")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), default="operator", nullable=False)  # super / operator
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operator: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_addr: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MachineBinding(Base):
    __tablename__ = "machine_bindings"
    __table_args__ = (UniqueConstraint("license_id", "machine_id", name="uq_machine_bindings_license_machine"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    license_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("license_keys.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(100), nullable=False)
    machine_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    replace_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class InstanceHeartbeat(Base):
    __tablename__ = "instance_heartbeats"
    __table_args__ = (UniqueConstraint("license_id", "instance_id", name="uq_instance_heartbeats_license_instance"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    license_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("license_keys.id"), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(100), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(100), nullable=False)
    last_beat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PullRecord(Base):
    __tablename__ = "pull_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=True)
    license_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("license_keys.id"), nullable=True)
    image_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    machine_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_update: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# 全栈方案 §5.1：container-token 体系
class ContainerToken(Base):
    __tablename__ = "container_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    machine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)  # initial_license / maintenance_renewal
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_fen: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trade_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ContainerMachineBinding(Base):
    """账号+机器绑定（container-token 用），与旧 machine_bindings(license_id) 并存"""
    __tablename__ = "container_machine_bindings"
    __table_args__ = (UniqueConstraint("user_id", "machine_id", name="uq_container_machine_bindings_user_machine"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=False, index=True)
    machine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# 生成次数管控（7.x：每台机器每 90 天周期按内容类型计数）
class GenerationQuota(Base):
    __tablename__ = "generation_quotas"
    __table_args__ = (
        UniqueConstraint(
            "license_id", "machine_id", "content_type", "cycle_start",
            name="uq_generation_quotas_license_machine_type_cycle",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    license_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("license_keys.id"), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(100), nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)  # schola / medcomm / qcc
    cycle_start: Mapped[date] = mapped_column(Date, nullable=False)
    cycle_end: Mapped[date] = mapped_column(Date, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_limit: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = 不限
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class GenerationRecord(Base):
    __tablename__ = "generation_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    license_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("license_keys.id"), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=True)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cycle_start: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ReleaseVersion(Base):
    """安装包版本（COS 路径 + 当前可下载标记），用于下载中心与后台版本管理"""
    __tablename__ = "release_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DownloadLog(Base):
    """安装包下载记录，用于审计与管理端展示"""
    __tablename__ = "download_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    license_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("license_keys.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ClientHeartbeat(Base):
    """桌面客户端心跳记录，用于客户端概览与设备列表"""
    __tablename__ = "client_heartbeats"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("portal_users.id"), nullable=False, index=True)
    machine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    os_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deployment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AppVersion(Base):
    """桌面客户端发布版本，供 latest-version / tauri-update 返回。规范 9.4"""
    __tablename__ = "app_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_url_windows: Mapped[str | None] = mapped_column(String(500), nullable=True)
    download_url_macos: Mapped[str | None] = mapped_column(String(500), nullable=True)
    download_url_linux: Mapped[str | None] = mapped_column(String(500), nullable=True)
    min_supported_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rollback_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    force_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pub_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    announcement: Mapped[str | None] = mapped_column(Text, nullable=True)  # 心跳下发的公告
    tauri_platforms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {"darwin-aarch64":{"url":"","signature":""}, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

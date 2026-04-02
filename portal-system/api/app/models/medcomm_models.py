"""
LinScio MedComm v3 授权体系数据模型
参考：LinScio_MedComm_授权体系方案_v3.md
与现有 portal 体系并存，表名使用 medcomm_ 前缀
"""
from datetime import datetime
from sqlalchemy import (
    String, Text, DateTime, Integer, ForeignKey, UniqueConstraint, PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MedcommUser(Base):
    """MedComm 用户（支持邮箱/手机号/用户名三渠道）"""
    __tablename__ = "medcomm_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Integer, default=1, nullable=False)  # 0=封禁
    email_verified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    phone_verified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MedcommLicenseCode(Base):
    """MedComm 授权码表"""
    __tablename__ = "medcomm_license_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    license_type: Mapped[str] = mapped_column(String(20), nullable=False)  # basic | specialty
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_trial: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 1=试用码
    specialty_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_activated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("medcomm_users.id"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipient_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_admin: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommUserLicense(Base):
    """MedComm 用户授权表（1:1 user）"""
    __tablename__ = "medcomm_user_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("medcomm_users.id"), unique=True, nullable=False, index=True
    )
    is_trial: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    device_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    token_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rebind_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    reported_specialties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MedcommUserSpecialty(Base):
    """MedComm 用户学科包（永久有效）"""
    __tablename__ = "medcomm_user_specialties"
    __table_args__ = (UniqueConstraint("user_id", "specialty_id", name="uq_medcomm_user_specialties_user_spec"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("medcomm_users.id"), nullable=False, index=True)
    specialty_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    license_code_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("medcomm_license_codes.id"), nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommDeviceChangeCode(Base):
    """MedComm 换机码（服务端生成，5 分钟有效）"""
    __tablename__ = "medcomm_device_change_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("medcomm_users.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    new_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    new_device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommDeviceRebindLog(Base):
    """MedComm 设备换绑日志"""
    __tablename__ = "medcomm_device_rebind_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("medcomm_users.id"), nullable=False, index=True)
    old_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    new_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    old_device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rebind_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # self_service | admin
    operator_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommDownloadLog(Base):
    """MedComm 下载日志（含完成回调）"""
    __tablename__ = "medcomm_download_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("medcomm_users.id"), nullable=True, index=True)
    download_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # software | specialty | document
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(30), nullable=True)
    signed_url_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    needs_review: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 1=同资源同账号当日>5次
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommSecurityLimit(Base):
    """MedComm 安全限制（速率 + 账号锁定）"""
    __tablename__ = "medcomm_security_limits"
    __table_args__ = (PrimaryKeyConstraint("limit_type", "identifier"),)

    limit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fail_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommSpecialtyVersionPolicy(Base):
    """MedComm 学科包强制版本策略"""
    __tablename__ = "medcomm_specialty_version_policy"

    specialty_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    force_min_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    force_max_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    policy_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommPendingRegistration(Base):
    """MedComm 待验证注册（验证码流程）"""
    __tablename__ = "medcomm_pending_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    credential_type: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommPasswordReset(Base):
    """MedComm 忘记密码重置（验证码流程）"""
    __tablename__ = "medcomm_password_resets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommSecurityEvent(Base):
    """MedComm 安全事件日志"""
    __tablename__ = "medcomm_security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("medcomm_users.id"), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MedcommAccountMigrationRequest(Base):
    """MedComm 账号迁移申请"""
    __tablename__ = "medcomm_account_migration_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("medcomm_users.id"), nullable=False, index=True)
    to_credential: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    handled_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

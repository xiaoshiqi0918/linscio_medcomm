"""LinScio MedComm v3 API Schemas"""
import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


def _validate_password_complexity(v: str) -> str:
    """密码须至少 8 位且包含字母和数字"""
    if len(v) < 8:
        raise ValueError("密码至少 8 位")
    if not re.search(r"[a-zA-Z]", v):
        raise ValueError("密码须包含字母")
    if not re.search(r"\d", v):
        raise ValueError("密码须包含数字")
    return v


# ------ Auth ------
class MedcommRegisterRequest(BaseModel):
    credential: str
    password: str = Field(..., min_length=8)
    credential_type: str = "email"  # email | phone | username

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class MedcommVerifyRequest(BaseModel):
    credential: str
    code: str


class MedcommLoginRequest(BaseModel):
    credential: str
    password: str


class MedcommLoginResponse(BaseModel):
    session_token: str
    expires_in: int


class MedcommChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class MedcommForgotPasswordRequest(BaseModel):
    credential: str


class MedcommResetPasswordRequest(BaseModel):
    credential: str
    code: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


# ------ License Activate ------
class MedcommValidateRequest(BaseModel):
    code: str


class MedcommValidateResponse(BaseModel):
    valid: bool
    error: str | None = None
    license_type: str | None = None
    is_trial: bool = False
    duration_months: int | None = None
    current_expires_at: str | None = None
    current_days_remaining: int | None = None
    new_expires_at: str | None = None
    specialty_ids: list[str] | None = None
    specialty_names: list[str] | None = None


class MedcommActivateRequest(BaseModel):
    code: str
    device_fingerprint: str
    device_name: str


class MedcommActivateResponse(BaseModel):
    success: bool
    error: str | None = None
    message: str | None = None
    license_type: str | None = None
    is_trial: bool = False
    new_expires_at: str | None = None
    days_added: int | None = None
    token_unchanged: bool = False
    rebind_count_reset: bool = False
    deep_link: str | None = None
    specialty_ids: list[str] | None = None
    specialty_names: list[str] | None = None


# ------ License Status ------
class MedcommLicenseStatusBase(BaseModel):
    valid: bool
    is_trial: bool
    expires_at: str | None
    days_remaining: int | None
    device_name: str | None
    token_created_at: str | None = None  # 设备绑定时间
    rebind_remaining: int


class MedcommSpecialtyStatus(BaseModel):
    id: str
    name: str
    remote_version: str | None
    local_version: str | None
    purchased_at: str | None


class MedcommVersionPolicy(BaseModel):
    specialty_id: str
    force_min_version: str | None
    force_max_version: str | None
    policy_message: str | None


class MedcommLicenseStatusResponse(BaseModel):
    base: MedcommLicenseStatusBase
    specialties: list[MedcommSpecialtyStatus] = []
    version_policies: list[MedcommVersionPolicy] = []


# ------ Device Change Code ------
class MedcommChangeCodeRequestRequest(BaseModel):
    credential: str
    password: str
    new_fingerprint: str
    new_device_name: str


class MedcommChangeCodeRequestResponse(BaseModel):
    success: bool
    code: str | None = None
    expires_in: int | None = None
    error: str | None = None
    message: str | None = None


class MedcommChangeCodeVerifyRequest(BaseModel):
    code: str


class MedcommChangeCodeVerifyResponse(BaseModel):
    success: bool
    new_device_name: str | None = None
    rebind_remaining: int | None = None
    deep_link: str | None = None
    error: str | None = None
    locked_until: str | None = None


# ------ Update check ------
class MedcommUpdateCheckRequest(BaseModel):
    platform: str = "mac-arm64"
    software_version: str = "1.0.0"
    specialties: dict[str, str] = Field(default_factory=dict)


class MedcommSoftwareUpdateInfo(BaseModel):
    version: str | None = None
    release_notes: str | None = None
    download_url: str | None = None
    size_mb: float | None = None


class MedcommSpecialtyUpdateItem(BaseModel):
    id: str
    latest_version: str | None = None
    has_update: bool = False
    size_mb: float | None = None
    full_size_mb: float | None = None
    changelog: list[str] = []
    force_update: bool = False
    force_message: str | None = None


class MedcommUpdateCheckResponse(BaseModel):
    base_valid: bool
    has_software_update: bool = False
    software: MedcommSoftwareUpdateInfo | None = None
    specialty_updates: list[MedcommSpecialtyUpdateItem] = []


# ------ Download ------
class MedcommSoftwareDownloadRequest(BaseModel):
    platform: str = "mac-arm64"


class MedcommSoftwareDownloadResponse(BaseModel):
    success: bool
    download_url: str | None = None
    filename: str | None = None
    size_mb: float | None = None
    download_log_id: int | None = None
    error: str | None = None


class MedcommDownloadCompleteRequest(BaseModel):
    download_log_id: int


class MedcommSpecialtyDownloadRequest(BaseModel):
    specialty_id: str
    version: str
    from_version: str | None = None
    resume_offset: int = 0


class MedcommSpecialtyDownloadResponse(BaseModel):
    success: bool
    package_type: str = "full"  # patch | full
    download_url: str | None = None
    filename: str | None = None
    size_mb: float | None = None
    md5: str | None = None
    download_log_id: int | None = None
    expires_in: int = 7200
    error: str | None = None


# ------ Account migration ------
class MedcommMigrationRequestBody(BaseModel):
    to_credential: str
    reason: str | None = None

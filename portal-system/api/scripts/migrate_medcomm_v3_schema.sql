-- LinScio MedComm v3 授权体系 - 数据库迁移
-- 适用于已有 linscio_portal 数据库，新增 MedComm 表
-- 执行：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_medcomm_v3_schema.sql

-- 幂等：表已存在则跳过（需手动检查）

CREATE TABLE IF NOT EXISTS medcomm_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active INTEGER DEFAULT 1 NOT NULL,
    email_verified INTEGER DEFAULT 0 NOT NULL,
    phone_verified INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_medcomm_users_email ON medcomm_users(email);
CREATE INDEX IF NOT EXISTS ix_medcomm_users_phone ON medcomm_users(phone);

CREATE TABLE IF NOT EXISTS medcomm_license_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) UNIQUE NOT NULL,
    license_type VARCHAR(20) NOT NULL,
    duration_months INTEGER,
    is_trial INTEGER DEFAULT 0 NOT NULL,
    specialty_ids JSONB,
    is_activated INTEGER DEFAULT 0 NOT NULL,
    activated_by INTEGER REFERENCES medcomm_users(id),
    activated_at TIMESTAMPTZ,
    recipient_note TEXT,
    created_by_admin INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_medcomm_license_codes_code ON medcomm_license_codes(code);

CREATE TABLE IF NOT EXISTS medcomm_user_licenses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES medcomm_users(id),
    is_trial INTEGER DEFAULT 0 NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    device_fingerprint VARCHAR(128),
    device_name VARCHAR(255),
    access_token VARCHAR(128) UNIQUE,
    token_created_at TIMESTAMPTZ,
    rebind_count INTEGER DEFAULT 0 NOT NULL,
    last_seen_at TIMESTAMPTZ,
    last_seen_ip VARCHAR(45),
    reported_specialties JSONB,
    reported_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_medcomm_user_licenses_user_id ON medcomm_user_licenses(user_id);
CREATE INDEX IF NOT EXISTS ix_medcomm_user_licenses_access_token ON medcomm_user_licenses(access_token);

CREATE TABLE IF NOT EXISTS medcomm_user_specialties (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES medcomm_users(id),
    specialty_id VARCHAR(50) NOT NULL,
    license_code_id INTEGER REFERENCES medcomm_license_codes(id),
    purchased_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, specialty_id)
);
CREATE INDEX IF NOT EXISTS ix_medcomm_user_specialties_user_id ON medcomm_user_specialties(user_id);
CREATE INDEX IF NOT EXISTS ix_medcomm_user_specialties_specialty_id ON medcomm_user_specialties(specialty_id);

CREATE TABLE IF NOT EXISTS medcomm_device_change_codes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES medcomm_users(id),
    code VARCHAR(6) NOT NULL,
    new_fingerprint VARCHAR(128) NOT NULL,
    new_device_name VARCHAR(255),
    expires_at TIMESTAMPTZ NOT NULL,
    is_used INTEGER DEFAULT 0 NOT NULL,
    fail_count INTEGER DEFAULT 0 NOT NULL,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_medcomm_device_change_codes_user_id ON medcomm_device_change_codes(user_id);

CREATE TABLE IF NOT EXISTS medcomm_device_rebind_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES medcomm_users(id),
    old_fingerprint VARCHAR(128),
    new_fingerprint VARCHAR(128),
    old_device_name VARCHAR(255),
    new_device_name VARCHAR(255),
    rebind_type VARCHAR(20),
    operator_ip VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS medcomm_download_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES medcomm_users(id),
    download_type VARCHAR(20),
    resource_id VARCHAR(100),
    platform VARCHAR(30),
    signed_url_hash VARCHAR(64),
    client_ip VARCHAR(45),
    user_agent TEXT,
    completed INTEGER DEFAULT 0 NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS medcomm_security_limits (
    limit_type VARCHAR(50) NOT NULL,
    identifier VARCHAR(255) NOT NULL,
    fail_count INTEGER DEFAULT 0 NOT NULL,
    locked_until TIMESTAMPTZ,
    last_fail_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (limit_type, identifier)
);

CREATE TABLE IF NOT EXISTS medcomm_specialty_version_policy (
    specialty_id VARCHAR(50) PRIMARY KEY,
    force_min_version VARCHAR(20),
    force_max_version VARCHAR(20),
    policy_message TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS medcomm_account_migration_requests (
    id SERIAL PRIMARY KEY,
    from_user_id INTEGER NOT NULL REFERENCES medcomm_users(id),
    to_credential VARCHAR(255) NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    handled_by INTEGER,
    handled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

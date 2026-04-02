-- MedComm 认证扩展：username、pending_registration、password_reset
-- 执行：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < api/scripts/migrate_medcomm_auth_extensions.sql

-- username 列（注册/登录支持用户名）
ALTER TABLE medcomm_users ADD COLUMN IF NOT EXISTS username VARCHAR(64) UNIQUE;
CREATE UNIQUE INDEX IF NOT EXISTS ix_medcomm_users_username ON medcomm_users(username) WHERE username IS NOT NULL;

-- 待验证注册（验证码流程）
CREATE TABLE IF NOT EXISTS medcomm_pending_registrations (
    id SERIAL PRIMARY KEY,
    credential VARCHAR(255) NOT NULL,
    credential_type VARCHAR(20) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_medcomm_pending_reg_credential ON medcomm_pending_registrations(credential);

-- 忘记密码重置（验证码流程）
CREATE TABLE IF NOT EXISTS medcomm_password_resets (
    id SERIAL PRIMARY KEY,
    credential VARCHAR(255) NOT NULL,
    code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_medcomm_password_resets_credential ON medcomm_password_resets(credential);

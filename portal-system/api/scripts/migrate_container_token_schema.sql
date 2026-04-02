-- 全栈部署方案 §5.1：portal_users 扩展 + container_tokens / orders / container_machine_bindings
-- 执行：psql -U linscio_user -d linscio_portal -f migrate_container_token_schema.sql
-- 或：docker compose exec -T linscio-db psql -U linscio_user -d linscio_portal < scripts/migrate_container_token_schema.sql

-- 1. portal_users 新增字段（已存在则跳过）
ALTER TABLE portal_users ADD COLUMN IF NOT EXISTS plan VARCHAR(32) DEFAULT NULL;
ALTER TABLE portal_users ADD COLUMN IF NOT EXISTS license_paid_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE portal_users ADD COLUMN IF NOT EXISTS maintenance_until TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE portal_users ADD COLUMN IF NOT EXISTS account_status VARCHAR(32) NOT NULL DEFAULT 'registered';
ALTER TABLE portal_users ADD COLUMN IF NOT EXISTS machine_limit INTEGER NOT NULL DEFAULT 1;

-- 2. container_tokens
CREATE TABLE IF NOT EXISTS container_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES portal_users(id),
    token       VARCHAR(64) UNIQUE NOT NULL,
    machine_id  VARCHAR(64) NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    issued_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_revoked  BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_container_tokens_user ON container_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_container_tokens_token ON container_tokens (token);
CREATE INDEX IF NOT EXISTS idx_container_tokens_user_machine ON container_tokens (user_id, machine_id);

-- 3. orders
CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES portal_users(id),
    order_type      VARCHAR(32) NOT NULL,
    plan            VARCHAR(32) NOT NULL,
    amount_fen      INTEGER NOT NULL,
    payment_method  VARCHAR(32),
    trade_no        VARCHAR(128),
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    paid_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders (user_id);

-- 4. container_machine_bindings
CREATE TABLE IF NOT EXISTS container_machine_bindings (
    id          SERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES portal_users(id),
    machine_id  VARCHAR(64) NOT NULL,
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, machine_id)
);
CREATE INDEX IF NOT EXISTS idx_container_machine_bindings_user ON container_machine_bindings (user_id);

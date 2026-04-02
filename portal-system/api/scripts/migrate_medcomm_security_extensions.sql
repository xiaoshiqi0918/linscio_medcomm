-- MedComm 安全扩展：medcomm_security_events 表、medcomm_download_logs.needs_review 列
-- 执行前请备份数据库

-- 1. 安全事件日志表
CREATE TABLE IF NOT EXISTS medcomm_security_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id INTEGER REFERENCES medcomm_users(id),
    reason VARCHAR(255),
    client_ip VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_medcomm_security_events_event_type ON medcomm_security_events(event_type);
CREATE INDEX IF NOT EXISTS ix_medcomm_security_events_user_id ON medcomm_security_events(user_id);

-- 2. 下载日志异常标记列
ALTER TABLE medcomm_download_logs ADD COLUMN IF NOT EXISTS needs_review INTEGER NOT NULL DEFAULT 0;

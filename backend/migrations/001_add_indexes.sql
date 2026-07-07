-- =============================================================================
-- Migration: 添加数据库索引以优化仪表盘查询性能
--
-- 问题：messages、conversations 表没有索引，导致每次聚合查询都全表扫描
-- 影响的主要查询：
--   1. Message JOIN Conversation on conversation_id (无索引)
--   2. WHERE user_id = ? (无索引)
--   3. GROUP BY / ORDER BY created_at (无索引)
--   4. WHERE status = 'active' (无索引)
-- =============================================================================

-- ── messages 表 ─────────────────────────────────────────────

-- 外键索引：Message JOIN Conversation 时最频繁
CREATE INDEX idx_messages_conversation_id ON messages (conversation_id);

-- 时间索引：趋势查询 GROUP BY / ORDER BY / WHERE 使用
CREATE INDEX idx_messages_created_at ON messages (created_at);

-- 联合索引：按用户统计消息时，避免回表
-- 覆盖 today count + 角色统计 + token 统计
CREATE INDEX idx_messages_conv_user_lookup ON messages (conversation_id, created_at, role, token_count);

-- ── conversations 表 ────────────────────────────────────────

-- 用户索引：几乎所有会话查询都按 user_id 过滤
CREATE INDEX idx_conversations_user_id ON conversations (user_id);

-- 状态索引：按 status 过滤 active/archived
CREATE INDEX idx_conversations_status ON conversations (status);

-- 联合索引：排序 updated_at 查询用户活跃会话
CREATE INDEX idx_conversations_user_status_updated ON conversations (user_id, status, updated_at);

-- ── system_logs 表 ──────────────────────────────────────────

-- 已经有 user_id 索引，添加时间索引用于排序
CREATE INDEX idx_system_logs_created_at ON system_logs (created_at);

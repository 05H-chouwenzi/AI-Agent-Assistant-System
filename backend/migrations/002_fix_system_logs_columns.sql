-- 修复 system_logs 表缺少的列
ALTER TABLE system_logs
    ADD COLUMN action         VARCHAR(80)  DEFAULT NULL COMMENT '操作分类' AFTER module,
    ADD COLUMN user_id        INT          DEFAULT NULL COMMENT '操作用户 ID' AFTER message,
    ADD COLUMN ip_address     VARCHAR(45)  DEFAULT NULL COMMENT '客户端 IP' AFTER user_id,
    ADD COLUMN resource_type  VARCHAR(50)  DEFAULT NULL COMMENT '资源类型' AFTER ip_address,
    ADD COLUMN resource_id    VARCHAR(50)  DEFAULT NULL COMMENT '资源 ID' AFTER resource_type,
    ADD COLUMN execution_time_ms INT      DEFAULT NULL COMMENT '执行耗时(毫秒)' AFTER resource_id;

-- 添加外键和索引
ALTER TABLE system_logs ADD INDEX idx_system_logs_action (action);
ALTER TABLE system_logs ADD INDEX idx_system_logs_user_id (user_id);

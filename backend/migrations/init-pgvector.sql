-- pgvector 初始化 SQL（docker-entrypoint-initdb.d 自动执行）
-- 启用向量扩展，供 KnowledgeVector 表使用
CREATE EXTENSION IF NOT EXISTS vector;

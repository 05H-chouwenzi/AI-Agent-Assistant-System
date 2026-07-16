"""
全局配置 —— 单一配置源，所有配置都从 .env 读取，避免硬编码密钥和散落的配置项。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ========== 加载 .env ==========
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ========== 阿里云 DashScope（大模型调用 + 嵌入）==========
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# ========== 聊天 LLM（可独立配置为 DeepSeek 等）==========
# 优先级：LLM_API_KEY > DASHSCOPE_API_KEY
LLM_API_KEY = os.getenv("LLM_API_KEY", DASHSCOPE_API_KEY)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", DASHSCOPE_BASE_URL)
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.6-27b")

# ========== JWT 密钥 ==========
_jwt_secret = os.getenv("JWT_SECRET")
if not _jwt_secret:
    raise ValueError(
        "JWT_SECRET 未设置！请在 backend/.env 中配置 JWT_SECRET=你的密钥"
    )
JWT_SECRET = _jwt_secret

# ========== 数据库连接 ==========
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL 未设置！请在 backend/.env 中配置 DATABASE_URL=数据库连接字符串"
    )

# ========== 向量存储配置 ==========
VECTOR_STORE_PROVIDER = os.getenv("VECTOR_STORE_PROVIDER", "faiss")
PGVECTOR_DATABASE_URL = os.getenv("PGVECTOR_DATABASE_URL", "")

# ========== CORS 配置 ==========
# 生产环境设置为你的公网 IP 或域名，如 http://106.53.59.88
# 多个来源用逗号分隔，如 http://a.com,http://b.com
_default_cors = "http://localhost:5173,http://localhost:4173,http://localhost"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_cors).split(",") if o.strip()]

"""
全局配置 —— 单一配置源
所有配置都从 .env 读取，避免硬编码密钥和散落的配置项。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ========== 加载 .env ==========
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ========== 阿里云 DashScope（大模型调用） ==========
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "glm-5.1"

# ========== JWT 密钥 ==========
# 生产环境必须在 .env 中设置 JWT_SECRET，无回退值！
# 生成密钥：openssl rand -hex 32
_jwt_secret = os.getenv("JWT_SECRET")
if not _jwt_secret:
    raise ValueError(
        "JWT_SECRET 未设置！请在 backend/.env 中配置 JWT_SECRET=你的密钥"
    )
JWT_SECRET = _jwt_secret

# ========== 数据库连接 ==========
# 生产环境必须在 .env 中设置 DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL 未设置！请在 backend/.env 中配置 DATABASE_URL=数据库连接字符串"
    )

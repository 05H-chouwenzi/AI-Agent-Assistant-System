"""配置模块 - 统一环境变量和配置"""
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


# Export variables directly
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.6-27b")

# Vision is kept on a separate model so attachment support does not replace the
# project's existing text/chat model.
VISION_LLM_API_KEY = os.getenv("VISION_LLM_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
VISION_LLM_BASE_URL = os.getenv("VISION_LLM_BASE_URL", os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
VISION_LLM_MODEL = os.getenv("VISION_LLM_MODEL", "qwen-vl-max")
VISION_CONCURRENCY = max(1, int(os.getenv("VISION_CONCURRENCY", "3")))

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
VECTOR_STORE_PROVIDER = os.getenv("VECTOR_STORE_PROVIDER", "faiss")
PGVECTOR_DATABASE_URL = os.getenv("PGVECTOR_DATABASE_URL", "")

_default_cors = "http://localhost:5173,http://localhost:4173,http://localhost"
CORS_ORIGINS: List[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_cors).split(",") if o.strip()]


class Settings:
    pass


settings = Settings()

"""
企业 AI 智能助手 —— FastAPI 入口（多租户 + WebSocket + 循环图）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# ⚠️ langchain 1.3.x 兼容：必须在其他所有导入之前设置
import langchain
import os
os.environ.setdefault("LANGCHAIN_DEBUG", "false")
os.environ.setdefault("LANGCHAIN_VERBOSE", "false")
# langchain 1.3.x 不再有 langchain.debug/langchain.verbose 属性
# langchain_core.globals.get_debug() 从环境变量 fallback
from langchain_core.globals import set_debug, set_verbose
set_debug(False)
set_verbose(False)

from utils.exception_handlers import (
    http_exception_handler,
    integrity_error_handler,
    sqlalchemy_error_handler,
    general_exception_handler,
)

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database.session import engine, get_db
from models.base import Base
from sqlalchemy import inspect as sa_inspect

# 导入所有模型
from models.user import User
from models.conversation import Conversation
from models.message import Message
from models.tenant import Tenant
from models.knowledge_doc import KnowledgeDoc
from models.system_log import SystemLog

from api.chat import router as chat_router
from api.chat_stream import router as chat_stream_router
from api.ws_chat import router as ws_router
from router.conversations import router as conv_router
from router.knowledge import router as knowledge_router
from router.logs import router as logs_router
from router.tools import router as tools_router
from router.dashboard import router as dashboard_router
from router.users import router as user_router

from tools.tool_manager import register_default_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表 + 迁移旧表 + 注册工具"""
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)

    # 迁移：给旧表加 tenant_id 列
    inspector = sa_inspect(engine)
    try:
        columns = [c["name"] for c in inspector.get_columns("users")]
        if "tenant_id" not in columns:
            print("迁移：给 users 表加 tenant_id/role 列...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN tenant_id INT DEFAULT NULL"))
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'admin'"))
                conn.commit()
        conv_cols = [c["name"] for c in inspector.get_columns("conversations")]
        if "tenant_id" not in conv_cols:
            print("迁移：给 conversations 表加 tenant_id 列...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN tenant_id INT DEFAULT NULL"))
                conn.commit()
    except Exception as e:
        print(f"迁移警告（可忽略）: {e}")

    print("数据库表创建完成")
    register_default_tools()
    print("默认工具注册完成")
    yield


app = FastAPI(
    title="Enterprise AI Assistant",
    description="企业 AI 智能助手（多租户 + WebSocket + 循环图）",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.get("/")
def root():
    return {"message": "Enterprise AI Assistant is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/db-test")
def db_test(db=Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {"db_status": "ok", "result": result}
    except Exception as e:
        return {"db_status": "error", "detail": str(e)}


# 路由
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(chat_stream_router)
app.include_router(ws_router)
app.include_router(conv_router)
app.include_router(knowledge_router)
app.include_router(logs_router)
app.include_router(tools_router)
app.include_router(dashboard_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

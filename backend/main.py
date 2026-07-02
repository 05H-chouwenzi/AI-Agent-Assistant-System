"""
企业 AI 智能助手 —— FastAPI 入口
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils.exception_handlers import (
    http_exception_handler,
    integrity_error_handler,
    sqlalchemy_error_handler,
    general_exception_handler,
)

from sqlalchemy.exc import IntegrityError,SQLAlchemyError

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from database.session import engine,get_db
from models.base import Base
from router.users import router as user_router


# 导入所有模型 —— 确保 SQLAlchemy 能发现它们
from models.user import User
from models.conversation import Conversation
from models.message import Message
from models.knowledge_doc import KnowledgeDoc
from models.system_log import SystemLog

from api.chat import router as chat_router
from api.chat_stream import router as chat_stream_router
from router.conversations import router as conv_router
from router.knowledge import router as knowledge_router
from router.logs import router as logs_router

from router.tools import router as tools_router
from router.dashboard import router as dashboard_router
from tools.tool_manager import register_default_tools

# ========== 应用生命周期 ==========
@asynccontextmanager
async def lifespan(app:FastAPI):
    """
    应用启动时：自动创建所有数据库表 & 注册工具
    应用关闭时：（预留清理逻辑）
    """
    # 启动时执行
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成")
    register_default_tools()
    print("默认工具注册完成")
    yield
    # 关闭时执行

# ========== 创建应用 ==========
app=FastAPI(
    title="Enterprise AI Assistant",
    description="企业 AI 智能助手 MVP",
    version="0.1.0",
    lifespan=lifespan,
    
)
# CORS —— 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 全局异常 ==========
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(user_router)

# ========== 路由 ==========
@app.get("/")
def root():
    """
    根目录:确认服务已启动
    """
    return {"message": "Enterprise AI Assistant is running"}

@app.get("/health")
def health_check():
    """
    健康检查: 部署/监控常用
    """
    return {"status": "ok"}

@app.get("/db-test")
def db_test(db=Depends(get_db)):
    """
    数据库测试: 测试数据库连接
    """
    try:
        result=db.execute(text("SELECT 1")).scalar()
        return {"db_status":"ok","result":result}
    except Exception as e:
        return {"db_status":"error","detail":str(e)}
    
app.include_router(chat_router)
app.include_router(chat_stream_router)
app.include_router(conv_router)
app.include_router(knowledge_router)
app.include_router(logs_router)

app.include_router(tools_router)
app.include_router(dashboard_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

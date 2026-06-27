"""
数据库会话管理
- 读取 .env 中的 DATABASE_URL
- 创建 SQLAlchemy 引擎
- 提供 get_db 依赖注入函数
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,Session

# 1. 加载 .env 文件（向上查找 backend 目录的 .env）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 2. 读取数据库连接 URL
DATABASE_URL=os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("未找到DATABASE_URL,请检查backend/.env文件")

# 3. 创建引擎
engine=create_engine(
    DATABASE_URL,
    pool_pre_ping=True,#    pool_pre_ping=True：每次连接前先 ping，防止 MySQL 8 小时断连
    pool_recycle=3600,#    pool_recycle=3600：每小时回收连接
    echo=False,
)

# 4. 创建会话工厂
SessionLocal=sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# 5. 依赖注入函数 —— FastAPI 路由里用它获取数据库会话
def get_db():
    """
    FastAPI 依赖注入：每个请求获取一个独立会话，请求结束自动关闭。
    
    用法：
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            ...
    """
    db=SessionLocal()
    try:
        yield db 
    finally:
        db.close()
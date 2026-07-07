"""
数据库会话管理
- 从 config.settings 导入 DATABASE_URL（单一配置源）
- 创建 SQLAlchemy 引擎
- 提供 get_db 依赖注入函数
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config.settings import DATABASE_URL

# 1. 创建引擎
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,     # 每次连接前先 ping，防止 MySQL 8 小时断连
    pool_recycle=3600,      # 每小时回收连接
    echo=False,
)

# 2. 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# 3. 依赖注入函数 —— FastAPI 路由里用它获取数据库会话
def get_db():
    """
    FastAPI 依赖注入：每个请求获取一个独立会话，请求结束自动关闭。

    用法：
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

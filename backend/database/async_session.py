"""
异步数据库会话 —— 用于 WebSocket + Agent 图的异步操作
与原有的 sync session 共存，互不干扰。
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config.settings import DATABASE_URL


# 将 mysql+pymysql:// 转为 mysql+aiomysql://
_ASYNC_DATABASE_URL = DATABASE_URL.replace("mysql+pymysql://", "mysql+aiomysql://", 1)

async_engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_db():
    """异步 DB 依赖注入"""
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.core_config import settings
import logging

# 禁用 SQLAlchemy 引擎的 INFO 级别日志（只保留 WARNING 和 ERROR）
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

# 创建异步数据库引擎
engine = create_async_engine(
    settings.database_url_async,
    echo=settings.API_DEBUG,  # 在调试模式下打印 SQL 语句
    future=True,
    pool_pre_ping=True,  # 连接前检查连接是否有效
    pool_recycle=3600,  # 1小时后回收连接
    connect_args={
        "server_settings": {
            "application_name": settings.APP_NAME,
        },
        "timeout": 10,  # 连接超时 10 秒
    }
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


# 依赖注入：获取数据库会话
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 初始化数据库表
async def init_db():
    from app.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

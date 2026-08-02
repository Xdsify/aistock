"""数据库连接管理"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

engine = None
async_session: async_sessionmaker[AsyncSession] = None


async def init_db(database_url: str):
    """初始化异步数据库连接池"""
    global engine, async_session

    # 将postgresql://替换为postgresql+asyncpg://
    async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        async_url,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)


async def close_db():
    """关闭数据库连接"""
    global engine
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    """获取数据库会话 (FastAPI依赖注入)"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

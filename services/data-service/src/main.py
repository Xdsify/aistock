"""数据采集服务 - 主入口"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import Response
from loguru import logger
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .config import settings
from .storage.database import init_db, close_db
from .storage.redis_client import init_redis, close_redis
from .api import router
from .ingestors.scheduler import DataScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务生命周期管理"""
    logger.info("数据服务启动中...")

    # 初始化连接
    await init_db(settings.database_url)
    logger.info("数据库连接池已初始化")
    await init_redis(settings.redis_url)
    logger.info("Redis连接已初始化")

    # 启动数据调度器
    scheduler = DataScheduler()
    scheduler_task = asyncio.create_task(scheduler.run())

    yield

    # 优雅关闭
    logger.info("数据服务关闭中...")
    scheduler_task.cancel()
    await close_redis()
    await close_db()


app = FastAPI(
    title="AI炒股 - 数据服务",
    description="A股行情数据采集、存储与分发",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/data")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "data-service"}


@app.get("/metrics")
async def metrics():
    """Prometheus 指标"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

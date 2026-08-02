"""风控管理器 - 主入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from .config import settings
from .redis_client import init_redis, close_redis
from .api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("风控管理器启动中...")
    await init_redis(settings.redis_url)
    logger.info("Redis连接池已初始化")
    logger.info(f"风险参数: 单股上限={settings.max_single_stock_pct*100}%, "
                f"行业上限={settings.max_sector_pct*100}%, "
                f"日亏损上限={settings.daily_loss_limit_pct*100}%")

    yield

    logger.info("风控管理器关闭中...")
    await close_redis()


app = FastAPI(
    title="AI炒股 - 风控管理",
    description="事前/事中/事后风险管理",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/risk")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "risk-manager"}

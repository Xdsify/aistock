"""策略引擎 - 主入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from .config import settings
from .api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("策略引擎启动中...")
    # 初始化策略引擎
    logger.info("策略引擎已就绪")

    yield

    logger.info("策略引擎关闭中...")


app = FastAPI(
    title="AI炒股 - 策略引擎",
    description="策略定义、信号生成和回测",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/strategy")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "strategy-engine"}

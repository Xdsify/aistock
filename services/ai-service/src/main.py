"""AI分析服务 - 主入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import Response
from loguru import logger
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .config import settings
from .client import deepseek_client
from .api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI服务启动中...")
    await deepseek_client.initialize()
    logger.info(f"DeepSeek客户端已初始化, 模型: {settings.default_model}")

    yield

    logger.info("AI服务关闭中...")
    await deepseek_client.close()


app = FastAPI(
    title="AI炒股 - AI分析服务",
    description="DeepSeek驱动的市场分析、信号增强和风险评估",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/ai")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "ai-service",
        "model": settings.default_model,
        "daily_tokens_used": deepseek_client.daily_tokens,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus 指标"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

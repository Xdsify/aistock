"""策略引擎 - 主入口"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, time
from fastapi import FastAPI
from fastapi.responses import Response
from loguru import logger
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import redis.asyncio as aioredis

from .config import settings
from .api import router
from .signals.pipeline import SignalPipeline
from .strategies.registry import load_user_strategies

# 默认监控列表 (与 data-service 保持一致)
DEFAULT_WATCHLIST = [
    "000001.SZ", "000002.SZ", "000858.SZ", "600519.SH",
    "300750.SZ", "601318.SH", "688981.SH", "002594.SZ",
]

LOOP_INTERVAL = 60  # 策略评估间隔(秒)

redis: aioredis.Redis = None
pipeline: SignalPipeline = None
_last_seen: dict = {}  # symbol -> 最后处理的 trade_date (避免同一根K线重复触发)


def is_trading_time() -> bool:
    """判断是否在A股交易时段"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    morning = 9 * 60 + 30
    noon_end = 11 * 60 + 30
    afternoon = 13 * 60
    close = 15 * 60
    return (morning <= t <= noon_end) or (afternoon <= t <= close)


async def get_watchlist() -> list:
    """获取监控列表 (Redis watchlist:active, 为空用默认)"""
    try:
        watched = await redis.smembers("watchlist:active")
        symbols = [s for s in watched if s]
        return symbols or DEFAULT_WATCHLIST
    except Exception:
        return DEFAULT_WATCHLIST


async def run_once():
    """一次策略评估: 同步激活策略 + 喂最新K线"""
    if pipeline is None or redis is None:
        return
    active_names = await redis.smembers("strategy:active")
    if not active_names:
        return
    await pipeline.sync_strategies(active_names)

    symbols = await get_watchlist()
    for symbol in symbols:
        data = await redis.get(f"kline:daily:{symbol}")
        if not data:
            continue
        try:
            records = json.loads(data)
        except Exception:
            continue
        if not records:
            continue

        latest_date = records[-1].get("trade_date", "")
        if _last_seen.get(symbol) == latest_date:
            continue  # 同一根K线不重复触发

        signals = await pipeline.feed_klines(symbol, records)
        _last_seen[symbol] = latest_date
        if signals:
            logger.info(f"[{symbol}] 生成 {len(signals)} 个信号")


async def strategy_loop():
    """后台策略循环: 交易时段喂K线给激活策略"""
    logger.info("策略评估循环已启动")
    while True:
        try:
            if is_trading_time():
                await run_once()
            else:
                logger.debug("非交易时段, 跳过策略评估")
        except Exception as e:
            logger.error(f"策略评估异常: {e}")
        await asyncio.sleep(LOOP_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("策略引擎启动中...")
    global redis, pipeline

    # 加载用户自定义策略
    load_user_strategies()

    redis = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    await redis.ping()
    pipeline = SignalPipeline(redis)
    loop_task = asyncio.create_task(strategy_loop())

    yield

    logger.info("策略引擎关闭中...")
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass
    await redis.aclose()


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


@app.get("/metrics")
async def metrics():
    """Prometheus 指标"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

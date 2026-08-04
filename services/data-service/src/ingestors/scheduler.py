"""数据采集调度器"""
import asyncio
import json
from datetime import date, datetime, time, timedelta
from loguru import logger

from ..storage import redis_client as _redis
from .akshare_ingestor import akshare

# 默认监控列表 (Redis watchlist:active 为空时使用)
DEFAULT_WATCHLIST = [
    "000001.SZ", "000002.SZ", "000858.SZ", "600519.SH",
    "300750.SZ", "601318.SH", "688981.SH", "002594.SZ",
]

REALTIME_INTERVAL = 30          # 主循环间隔 / 盘中实时轮询 (秒)
SENTIMENT_INTERVAL = 300        # 市场情绪更新间隔 (秒)
DAILY_KLINES_INTERVAL = 3600    # 日线缓存更新间隔 (秒)


class DataScheduler:
    """定时数据采集调度器"""

    def __init__(self):
        self.running = False
        self._tasks: list = []

    async def run(self):
        """主调度循环"""
        self.running = True
        logger.info("数据调度器已启动")

        last_sentiment = 0.0
        last_daily = 0.0

        while self.running:
            try:
                now = datetime.now()
                is_trading = now.weekday() < 5 and self._in_trading_session(now.time())

                # 1. 盘中轮询实时行情 → 缓存 + 发布 market:quote
                if is_trading:
                    await self._poll_realtime()

                # 2. 市场情绪 → 缓存 + 发布 market:sentiment
                if now.timestamp() - last_sentiment >= SENTIMENT_INTERVAL:
                    await self._update_sentiment()
                    last_sentiment = now.timestamp()

                # 3. 日线缓存 (供策略引擎/API读取)
                if now.timestamp() - last_daily >= DAILY_KLINES_INTERVAL:
                    await self._update_daily_kline()
                    last_daily = now.timestamp()

            except Exception as e:
                logger.error(f"数据调度异常: {e}")

            await asyncio.sleep(REALTIME_INTERVAL)

    @staticmethod
    def _in_trading_session(t: time) -> bool:
        """是否在A股连续竞价时段 (9:30-11:30, 13:00-15:00)"""
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        return (morning_start <= t <= morning_end) or (afternoon_start <= t <= afternoon_end)

    async def _get_watchlist(self) -> list:
        """获取监控列表 (Redis watchlist:active, 为空用默认)"""
        r = _redis.redis_client
        if r is None:
            return DEFAULT_WATCHLIST
        try:
            watched = await r.smembers("watchlist:active")
            symbols = [s for s in watched if s]
            return symbols or DEFAULT_WATCHLIST
        except Exception:
            return DEFAULT_WATCHLIST

    async def _poll_realtime(self):
        """实时行情轮询: 一次拉全市场 → 按监控列表缓存并发布 market:quote"""
        symbols = await self._get_watchlist()
        r = _redis.redis_client
        if r is None:
            return
        loop = asyncio.get_event_loop()

        try:
            spot_map = await loop.run_in_executor(None, akshare._sync_get_spot_map)
        except Exception as e:
            logger.warning(f"实时行情获取失败: {e}")
            return
        if not spot_map:
            return

        published = 0
        for symbol in symbols:
            code = symbol.split(".")[0]
            quote = spot_map.get(code)
            if not quote:
                continue
            payload = dict(quote)
            payload["symbol"] = symbol
            payload["timestamp"] = datetime.now().isoformat()
            await r.setex(f"market:realtime:{symbol}", 60, json.dumps(payload, ensure_ascii=False))
            await r.publish("market:quote", json.dumps(payload, ensure_ascii=False))
            published += 1
        if published:
            logger.debug(f"实时行情已发布: {published} 只")

    async def _update_sentiment(self):
        """更新市场情绪 → 缓存 + 发布 market:sentiment"""
        r = _redis.redis_client
        if r is None:
            return
        loop = asyncio.get_event_loop()
        try:
            sentiment = await loop.run_in_executor(None, akshare._sync_get_sentiment_raw)
            if not sentiment:
                return
            sentiment["timestamp"] = datetime.now().isoformat()
            await r.setex("market:sentiment", 300, json.dumps(sentiment, ensure_ascii=False))
            await r.publish("market:sentiment", json.dumps(sentiment, ensure_ascii=False))
            logger.info(f"市场情绪已更新: 上证{sentiment.get('sh_index')} "
                        f"{sentiment.get('trend')} 涨跌比{sentiment.get('advance_decline_ratio')}")
        except Exception as e:
            logger.warning(f"市场情绪更新失败: {e}")

    async def _update_daily_kline(self):
        """更新日线缓存: kline:daily:{symbol} (供策略引擎/API使用)"""
        symbols = await self._get_watchlist()
        r = _redis.redis_client
        if r is None:
            return
        loop = asyncio.get_event_loop()

        end = date.today()
        start = end - timedelta(days=90)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        for symbol in symbols:
            code = symbol.split(".")[0]
            try:
                df = await loop.run_in_executor(
                    None, akshare._sync_get_kline_raw, code, start_str, end_str
                )
                if df is not None and not df.empty:
                    records = df.copy()
                    records["trade_date"] = records["trade_date"].dt.strftime("%Y-%m-%d")
                    await r.setex(
                        f"kline:daily:{symbol}", 86400,
                        json.dumps(records.to_dict(orient="records"), ensure_ascii=False),
                    )
                    logger.debug(f"日线缓存更新: {symbol} {len(records)}根")
            except Exception as e:
                logger.warning(f"日线更新 {symbol} 失败: {e}")
            await asyncio.sleep(0.5)

    def stop(self):
        """停止调度器"""
        self.running = False
        for task in self._tasks:
            task.cancel()
        logger.info("数据调度器已停止")

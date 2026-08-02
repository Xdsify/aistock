"""数据采集调度器"""
import asyncio
from datetime import datetime, time
from loguru import logger


class DataScheduler:
    """定时数据采集调度器"""

    def __init__(self):
        self.running = False
        self._tasks: list = []

    async def run(self):
        """主调度循环"""
        self.running = True
        logger.info("数据调度器已启动")

        while self.running:
            try:
                now = datetime.now()

                # 交易日判断
                if now.weekday() < 5:
                    current_time = now.time()
                    morning_start = time(9, 30)
                    morning_end = time(11, 30)
                    afternoon_start = time(13, 0)
                    afternoon_end = time(15, 0)

                    is_trading = (
                        (morning_start <= current_time <= morning_end)
                        or (afternoon_start <= current_time <= afternoon_end)
                    )

                    if is_trading:
                        await self._poll_realtime()
                else:
                    logger.debug("非交易日, 跳过数据采集")

            except Exception as e:
                logger.error(f"数据调度异常: {e}")

            await asyncio.sleep(60)

    async def _poll_realtime(self):
        """实时行情轮询"""
        logger.debug("实时行情轮询...")

    async def _update_daily_kline(self):
        """更新日线数据"""
        logger.debug("日线数据更新...")

    def stop(self):
        """停止调度器"""
        self.running = False
        for task in self._tasks:
            task.cancel()
        logger.info("数据调度器已停止")

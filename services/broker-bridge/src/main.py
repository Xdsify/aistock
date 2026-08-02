"""券商桥接服务 - Python端gRPC服务器

注意: 此服务需要在Windows上原生运行以使用xtquant/miniQMT
Docker部署时需特殊网络配置连接宿主机
"""
import os
import sys
import json
import asyncio
from datetime import datetime, date
from loguru import logger
import redis.asyncio as aioredis

# ============================================
# 配置
# ============================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
XTQUANT_PATH = os.getenv("XTQUANT_PATH", "C:/xtquant")

# 尝试导入xtquant (仅在Windows可用)
try:
    sys.path.insert(0, XTQUANT_PATH)
    # from xtquant import xtdata, xttrader
    XTQUANT_AVAILABLE = False  # 设为False,用模拟模式
    logger.info("xtquant已加载")
except ImportError:
    XTQUANT_AVAILABLE = False
    logger.warning("xtquant不可用,使用模拟交易模式")


class BrokerBridge:
    """券商桥接 - 模拟/实盘交易"""

    def __init__(self):
        self.redis: aioredis.Redis = None
        self.connected = False
        self.mode = "SIMULATION"  # SIMULATION / LIVE

    async def initialize(self):
        """初始化连接"""
        self.redis = aioredis.from_url(
            REDIS_URL, encoding="utf-8", decode_responses=True
        )
        logger.info(f"券商桥接初始化, 模式: {self.mode}")

        if XTQUANT_AVAILABLE:
            await self._connect_live()
        else:
            await self._init_simulation()

    async def _connect_live(self):
        """连接实盘券商"""
        # TODO: 实现xtquant连接
        # session = xttrader.XtQuantTrader(...)
        # session.start()
        # session.subscribe()
        self.connected = True
        self.mode = "LIVE"

    async def _init_simulation(self):
        """初始化模拟交易"""
        self.mode = "SIMULATION"
        self.connected = True

        # 初始化模拟账户
        initial_capital = 500000.0  # 50万模拟资金
        await self.redis.set("account:total_equity", str(initial_capital))
        await self.redis.set("account:available_cash", str(initial_capital))
        await self.redis.set("account:initial_capital", str(initial_capital))

        logger.info(f"模拟账户已初始化: {initial_capital:,.0f}元")

    async def place_order(self, symbol: str, action: str,
                          price: float, volume: int,
                          order_type: str = "LIMIT") -> dict:
        """下单

        Returns:
            {"order_id": str, "status": str, "message": str}
        """
        import uuid
        order_id = str(uuid.uuid4())[:12]

        if self.mode == "SIMULATION":
            # 模拟成交
            await self._simulate_fill(order_id, symbol, action, price, volume)
            return {
                "order_id": order_id,
                "status": "FILLED",
                "filled_volume": volume,
                "avg_price": price,
                "message": f"模拟成交: {action} {symbol} {volume}股@{price:.2f}",
            }
        else:
            # TODO: 实盘下单
            # result = xttrader.order(...)
            return {"order_id": order_id, "status": "PENDING", "message": "实盘下单待实现"}

    async def _simulate_fill(self, order_id: str, symbol: str,
                             action: str, price: float, volume: int):
        """模拟成交处理"""
        # 计算金额
        amount = price * volume
        commission = max(5.0, amount * 0.00025)  # 最低5元佣金
        stamp_tax = amount * 0.001 if action == "SELL" else 0  # 卖方印花税千1

        # 更新账户
        cash = float(await self.redis.get("account:available_cash") or 0)
        equity = float(await self.redis.get("account:total_equity") or 0)

        if action == "BUY":
            cash -= (amount + commission)
        else:
            cash += (amount - commission - stamp_tax)

        await self.redis.set("account:available_cash", str(round(cash, 2)))

        # 更新持仓
        pos_key = f"position:{symbol}"
        pos_data = await self.redis.get(pos_key)
        if pos_data:
            pos = json.loads(pos_data)
        else:
            pos = {
                "symbol": symbol,
                "total_qty": 0,
                "available_sell": 0,
                "locked_qty": 0,
                "avg_cost": 0,
                "realized_pnl": 0,
            }

        if action == "BUY":
            old_value = pos["total_qty"] * pos["avg_cost"]
            new_value = volume * price
            pos["total_qty"] += volume
            pos["locked_qty"] += volume  # T+1锁定
            pos["avg_cost"] = (old_value + new_value) / max(pos["total_qty"], 1)
            pos["available_sell"] = pos["total_qty"] - pos["locked_qty"]
        else:
            realized = volume * (price - pos["avg_cost"])
            pos["total_qty"] -= volume
            pos["available_sell"] -= volume
            pos["realized_pnl"] += realized

        pos["current_price"] = price
        pos["market_value"] = pos["total_qty"] * price
        pos["updated_at"] = datetime.now().isoformat()

        await self.redis.set(pos_key, json.dumps(pos))

        # 发布订单成交事件
        fill_data = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "price": price,
            "volume": volume,
            "status": "FILLED",
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "timestamp": datetime.now().isoformat(),
        }
        await self.redis.publish("order:update", json.dumps(fill_data))

    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        if self.mode == "SIMULATION":
            return True
        # TODO: 实盘撤单
        return False

    async def query_position(self, symbol: str) -> dict:
        """查询持仓"""
        data = await self.redis.get(f"position:{symbol}")
        return json.loads(data) if data else {"total_qty": 0}

    async def query_account(self) -> dict:
        """查询账户"""
        equity = float(await self.redis.get("account:total_equity") or 0)
        cash = float(await self.redis.get("account:available_cash") or 0)

        # 计算总市值
        market_value = 0
        async for key in self.redis.scan_iter("position:*"):
            pos = json.loads(await self.redis.get(key))
            market_value += pos.get("market_value", 0)

        return {
            "total_equity": equity,
            "available_cash": cash,
            "market_value": market_value,
            "mode": self.mode,
        }

    async def subscribe_quotes(self, symbols: list[str]):
        """订阅实时行情"""
        await self.redis.sadd("watchlist:active", *symbols)
        logger.info(f"已订阅 {len(symbols)} 只股票实时行情")

    async def on_new_trading_day(self):
        """新交易日初始化"""
        # 释放T+1锁定
        async for key in self.redis.scan_iter("position:*"):
            pos = json.loads(await self.redis.get(key))
            if pos.get("locked_qty", 0) > 0:
                pos["available_sell"] += pos["locked_qty"]
                pos["locked_qty"] = 0
                await self.redis.set(key, json.dumps(pos))
                logger.info(f"{pos['symbol']} T+1锁定已释放")

        # 重置日盈亏
        today = date.today().isoformat()
        await self.redis.set(f"pnl:daily:{today}", "0")
        logger.info(f"新交易日 {today} 已初始化")


# 单例
bridge = BrokerBridge()


async def main():
    """主函数 - 启动gRPC服务或命令行模式"""
    await bridge.initialize()

    # 订阅示例股票
    await bridge.subscribe_quotes([
        "000001.SZ", "000002.SZ", "000858.SZ",
        "600519.SH", "300750.SZ", "601318.SH",
    ])

    logger.info(f"券商桥接服务运行中 (模式: {bridge.mode})")
    logger.info("按 Ctrl+C 退出")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("服务关闭")


if __name__ == "__main__":
    asyncio.run(main())

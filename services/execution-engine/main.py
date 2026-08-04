"""
模拟执行引擎 (Python版)
- 订阅策略信号, 自动在模拟账户下单
- 持仓追踪 + T+1锁定
- REST API给前端Dashboard
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import uuid
import asyncio
from datetime import datetime, date
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from loguru import logger
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import redis.asyncio as aioredis

from metrics import orders_total, pnl_daily, total_equity, positions_value

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ============ 全局状态 ============
rdb: aioredis.Redis = None
SIMULATION = True
INITIAL_CAPITAL = 500000.0

# 内存持仓快照
positions: dict[str, dict] = {}
orders: dict[str, dict] = {}
signals_log: list[dict] = []
trades: list = []  # 已实现成交记录 (供胜率/盈亏比统计)


def is_trading_time() -> bool:
    """是否在A股交易时段 (周一至周五 9:30-11:30, 13:00-15:00)"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    morning = 9 * 60 + 30
    noon_end = 11 * 60 + 30
    afternoon = 13 * 60
    close = 15 * 60
    return (morning <= t <= noon_end) or (afternoon <= t <= close)

# ============ 初始化 ============
async def init():
    global rdb
    rdb = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await rdb.ping()

    # 初始化模拟账户
    if not await rdb.exists("account:total_equity"):
        await rdb.set("account:total_equity", str(INITIAL_CAPITAL))
        await rdb.set("account:available_cash", str(INITIAL_CAPITAL))
        await rdb.set("account:initial_capital", str(INITIAL_CAPITAL))
        logger.info(f"模拟账户初始化: {INITIAL_CAPITAL:,.0f}元")
    else:
        equity = await rdb.get("account:total_equity")
        logger.info(f"模拟账户: {float(equity):,.0f}元")

    # 加载已有持仓
    async for key in rdb.scan_iter("position:*"):
        data = await rdb.get(key)
        if data:
            pos = json.loads(data)
            positions[pos["symbol"]] = pos

    # 加载已有成交记录
    items = await rdb.lrange("trade:list", 0, -1)
    for it in items:
        try:
            trades.append(json.loads(it))
        except Exception:
            continue

    # 订阅信号频道
    asyncio.create_task(subscribe_signals())


# ============ 信号订阅 & 自动执行 ============
async def subscribe_signals():
    """订阅策略信号, 自动下单

    signal:new      — 策略管道产生的原始信号 (requires_confirmation=True 时需人工批准)
    signal:approved — 人工/系统批准后的执行信号 (requires_confirmation=False, 直接执行)
    """
    pubsub = rdb.pubsub()
    await pubsub.subscribe("signal:new", "signal:approved")
    logger.info("监听信号频道: signal:new / signal:approved")

    async for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
        try:
            signal = json.loads(msg["data"])
            logger.info(f"收到信号: {signal['action']} {signal['symbol']} 强度={signal.get('strength',0):.0%}")

            # 需要人工确认的,记录但不自动执行
            if signal.get("requires_confirmation"):
                logger.info(f"  信号需人工确认,跳过自动执行")
                signals_log.append(signal)
                await rdb.lpush("signal:pending", json.dumps(signal))
                continue

            # 执行
            result = await execute_signal(signal)
            if result["success"]:
                logger.info(f"  下单成功: {result['order_id']}")
                signal["status"] = "EXECUTED"
                signal["order_id"] = result["order_id"]
            else:
                logger.warning(f"  下单失败: {result.get('error')}")
                signal["status"] = "REJECTED"
                signal["error"] = result.get("error")

            signals_log.append(signal)
            await rdb.lpush("signal:list", json.dumps(signal))

        except Exception as e:
            logger.error(f"信号处理异常: {e}")


async def execute_signal(signal: dict) -> dict:
    """执行交易信号 (模拟模式)"""
    symbol = signal["symbol"]
    action = signal["action"]
    price = signal.get("price", 0)
    volume = signal.get("volume", 0)
    position_pct = signal.get("position_pct", 0.1)

    # 交易时段检查 (ENFORCE_TRADING_HOURS=false 可关闭, 便于学习测试)
    if os.getenv("ENFORCE_TRADING_HOURS", "true").lower() in ("1", "true", "yes"):
        if not is_trading_time():
            return {"success": False, "error": "非交易时间，拒绝下单"}

    if price <= 0:
        return {"success": False, "error": "价格无效"}

    # 计算成交量
    if volume <= 0:
        cash = float(await rdb.get("account:available_cash") or 0)
        if action == "BUY":
            volume = int(cash * position_pct / price / 100) * 100
        else:
            pos = positions.get(symbol, {})
            volume = pos.get("available_sell", 0)
    if volume < 100:
        return {"success": False, "error": f"成交量太小({volume}股)"}

    # 风控检查
    if action == "BUY":
        cash = float(await rdb.get("account:available_cash") or 0)
        cost = price * volume + max(5, price * volume * 0.00025)
        if cost > cash:
            return {"success": False, "error": f"资金不足(需要{cost:.0f}, 可用{cash:.0f})"}

    if action == "SELL":
        pos = positions.get(symbol, {})
        available = pos.get("available_sell", 0)
        if volume > available:
            return {"success": False, "error": f"可卖不足(尝试{volume}, 可卖{available})"}

    # 创建订单
    order_id = str(uuid.uuid4())[:8]
    commission = max(5.0, price * volume * 0.00025)
    stamp_tax = price * volume * 0.001 if action == "SELL" else 0

    order = {
        "order_id": order_id,
        "signal_id": signal.get("signal_id", ""),
        "symbol": symbol,
        "action": action,
        "price": price,
        "volume": volume,
        "filled_volume": volume,
        "avg_fill_price": price,
        "status": "FILLED",
        "commission": round(commission, 2),
        "stamp_tax": round(stamp_tax, 2),
        "timestamp": datetime.now().isoformat(),
    }
    orders[order_id] = order
    orders_total.labels(action).inc()  # Prometheus 指标

    # 更新账户资金
    cash = float(await rdb.get("account:available_cash") or 0)
    if action == "BUY":
        cash -= (price * volume + commission)
    else:
        cash += (price * volume - commission - stamp_tax)
    await rdb.set("account:available_cash", str(round(cash, 2)))

    # 记录卖出成交 (已实现盈亏, 供胜率/盈亏比统计)
    if action == "SELL":
        pos = positions.get(symbol, {})
        realized = volume * (price - pos.get("avg_cost", 0))
        trade = {
            "time": datetime.now().isoformat()[:19],
            "symbol": symbol, "action": "SELL",
            "price": price, "volume": volume,
            "pnl": round(realized, 2),
        }
        trades.append(trade)
        await rdb.lpush("trade:list", json.dumps(trade))
        await rdb.ltrim("trade:list", 0, 199)

    # 更新持仓
    await update_position(symbol, action, price, volume, signal.get("name", ""))

    # 发布更新
    await rdb.publish("order:update", json.dumps(order))
    await rdb.set(f"order:{order_id}", json.dumps(order))

    # 更新总资产
    await recalculate_equity()

    return {"success": True, "order_id": order_id}


async def update_position(symbol: str, action: str, price: float, volume: int, name: str = ""):
    """更新持仓 + T+1锁定"""
    pos = positions.get(symbol, {
        "symbol": symbol, "name": name or symbol, "total_qty": 0, "available_sell": 0,
        "locked_qty": 0, "avg_cost": 0, "realized_pnl": 0,
        "current_price": 0, "market_value": 0, "unrealized_pnl": 0,
    })
    if name:
        pos["name"] = name

    if action == "BUY":
        old_value = pos["total_qty"] * pos["avg_cost"]
        pos["total_qty"] += volume
        pos["locked_qty"] += volume  # T+1锁定
        pos["avg_cost"] = (old_value + price * volume) / pos["total_qty"]
    else:
        realized = volume * (price - pos["avg_cost"])
        pos["total_qty"] -= volume
        pos["available_sell"] -= volume
        pos["realized_pnl"] += realized

    pos["available_sell"] = pos["total_qty"] - pos["locked_qty"]
    pos["current_price"] = price
    pos["market_value"] = pos["total_qty"] * price
    pos["unrealized_pnl"] = pos["total_qty"] * (price - pos["avg_cost"]) if pos["total_qty"] > 0 else 0
    pos["updated_at"] = datetime.now().isoformat()

    if pos["total_qty"] <= 0:
        positions.pop(symbol, None)
        await rdb.delete(f"position:{symbol}")
    else:
        positions[symbol] = pos
        await rdb.set(f"position:{symbol}", json.dumps(pos))

    await rdb.publish("position:update", json.dumps(pos))


async def recalculate_equity():
    """重算总资产 (优先用实时价, 无则用买入价)"""
    cash = float(await rdb.get("account:available_cash") or 0)
    market_value = 0
    for symbol, pos in positions.items():
        live = await _live_price(symbol)
        price = live if live else pos.get("current_price", 0)
        market_value += pos.get("total_qty", 0) * price
    equity = cash + market_value
    await rdb.set("account:total_equity", str(round(equity, 2)))

    today = date.today().isoformat()
    initial = float(await rdb.get("account:initial_capital") or INITIAL_CAPITAL)
    pnl = equity - initial
    await rdb.set(f"pnl:daily:{today}", str(round(pnl, 2)))

    # Prometheus 指标
    total_equity.set(round(equity, 2))
    pnl_daily.set(round(pnl, 2))
    positions_value.set(round(market_value, 2))

    # 权益历史快照 (供前端权益曲线)
    snapshot = {"time": datetime.now().isoformat()[:19], "value": round(equity, 2)}
    await rdb.lpush("equity:history", json.dumps(snapshot))
    await rdb.ltrim("equity:history", 0, 499)


# ============ REST API ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init()
    logger.info("模拟执行引擎启动")
    yield

app = FastAPI(title="AI炒股-执行引擎", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/metrics")
async def metrics():
    """Prometheus 指标"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    equity = float(await rdb.get("account:total_equity") or 0)
    return {"status": "ok", "mode": "SIMULATION", "equity": equity}


@app.get("/api/account")
async def get_account():
    equity = float(await rdb.get("account:total_equity") or INITIAL_CAPITAL)
    cash = float(await rdb.get("account:available_cash") or INITIAL_CAPITAL)
    market_value = sum(p.get("market_value", 0) for p in positions.values())
    initial = float(await rdb.get("account:initial_capital") or INITIAL_CAPITAL)
    total_pnl = equity - initial

    return {
        "total_equity": round(equity, 2),
        "available_cash": round(cash, 2),
        "market_value": round(market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl / initial * 100, 2),
        "positions_count": len(positions),
        "mode": "SIMULATION",
    }


async def _live_price(symbol: str):
    """从 Redis 实时行情 (data-service 盘中写入) 取最新价, 无则 None"""
    try:
        data = await rdb.get(f"market:realtime:{symbol}")
        if data:
            price = float(json.loads(data).get("price", 0))
            return price if price > 0 else None
    except Exception:
        pass
    return None


@app.get("/api/positions")
async def get_positions():
    result = []
    for symbol, pos in positions.items():
        p = dict(pos)
        live = await _live_price(symbol)
        p["live"] = bool(live)  # 现价是否来自实时行情 (False=以买入价计)
        if live:
            p["current_price"] = live
            p["market_value"] = round(pos.get("total_qty", 0) * live, 2)
            p["unrealized_pnl"] = round(pos.get("total_qty", 0) * (live - pos.get("avg_cost", 0)), 2)
        result.append(p)
    return result


@app.get("/api/orders")
async def get_orders():
    return list(orders.values())[-50:]


@app.get("/api/signals")
async def get_signals():
    return signals_log[-50:]


@app.get("/api/equity-history")
async def get_equity_history(limit: int = 300):
    """权益历史曲线点 (Redis equity:history, 最新在前)"""
    items = await rdb.lrange("equity:history", 0, max(limit - 1, 0))
    points = []
    for it in items:
        try:
            points.append(json.loads(it))
        except Exception:
            continue
    points.reverse()  # 时间从旧到新
    return {"points": points, "count": len(points)}


@app.get("/api/stats")
async def get_stats():
    """交易统计: 胜率 / 盈亏比 (基于已实现成交)"""
    sells = [t for t in trades if t.get("action") == "SELL"]
    wins = 0
    gross_profit = 0.0
    gross_loss = 0.0
    for t in sells:
        pnl = t.get("pnl", 0)
        if pnl > 0:
            wins += 1
            gross_profit += pnl
        else:
            gross_loss += abs(pnl)
    return {
        "win_rate": round(wins / max(len(sells), 1) * 100, 1),
        "profit_factor": round(gross_profit / gross_loss, 2)
        if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
        "trades_count": len(sells),
    }


@app.post("/api/order/manual")
async def manual_order(req: dict):
    """手动下单"""
    signal = {
        "symbol": req["symbol"],
        "name": req.get("name", ""),
        "action": req["action"].upper(),
        "price": req["price"],
        "volume": req.get("volume", 0),
        "position_pct": req.get("position_pct", 0.1),
        "signal_id": f"manual_{uuid.uuid4().hex[:6]}",
        "requires_confirmation": False,
    }
    result = await execute_signal(signal)
    return result


@app.post("/api/emergency-stop")
async def emergency_stop():
    await rdb.set("circuit_breaker:emergency_stop", "1")
    return {"success": True, "message": "紧急停止已执行"}


@app.post("/api/signals/approve")
async def approve_signal(req: dict):
    """批准待确认信号"""
    signal = req.get("signal", {})
    signal["requires_confirmation"] = False
    result = await execute_signal(signal)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)

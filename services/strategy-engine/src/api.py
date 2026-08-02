"""策略引擎API路由"""
import json
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger
import redis.asyncio as aioredis

from .config import settings
from .strategies.examples import BUILTIN_STRATEGIES
from .strategies.base import BarData, Action

router = APIRouter()
_redis: aioredis.Redis = None


async def _get_redis():
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis


class StrategyConfig(BaseModel):
    name: str
    params: dict = {}
    enable_ai: bool = True
    require_confirmation: bool = True


class BarInput(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
    amount: float = 0


class SignalApproveRequest(BaseModel):
    signal: dict


class QuickBuyRequest(BaseModel):
    symbol: str
    name: str = ""
    price: float
    position_pct: float = 0.1
    reason: str = ""


@router.get("/list")
async def list_strategies():
    """列出所有可用策略"""
    strategies = []
    for name, cls in BUILTIN_STRATEGIES.items():
        strategies.append({
            "name": name,
            "author": cls.author,
            "description": cls.__doc__ or "",
            "params": {
                "max_position_pct": cls.max_position_pct,
                "stop_loss_pct": cls.stop_loss_pct,
                "take_profit_pct": cls.take_profit_pct,
                "requires_ai": cls.requires_ai,
                "requires_confirmation": cls.requires_confirmation,
            },
        })
    return {"strategies": strategies}


@router.get("/active")
async def list_active():
    """列出当前激活的策略"""
    return {"active": []}


@router.post("/activate")
async def activate_strategy(config: StrategyConfig):
    """激活策略"""
    if config.name not in BUILTIN_STRATEGIES:
        raise HTTPException(404, f"策略不存在: {config.name}")
    return {"success": True, "strategy": config.name}


@router.post("/test-signal")
async def test_signal(bar: BarInput):
    """测试: 用指定的K线数据运行所有策略，返回信号"""
    bar_data = BarData(
        symbol=bar.symbol, open=bar.open, high=bar.high, low=bar.low,
        close=bar.close, volume=bar.volume, amount=bar.amount,
    )
    signals = []
    for name, strategy_class in BUILTIN_STRATEGIES.items():
        strategy = strategy_class()
        strategy.on_init()
        strategy.update_bar(bar_data)
        for _ in range(25):
            strategy.update_bar(bar_data)
        signal = strategy.on_bar(bar_data)
        if signal:
            signals.append({
                "strategy": name, "action": signal.action.value,
                "strength": signal.strength, "price": signal.price,
                "stop_loss": signal.stop_loss, "take_profit": signal.take_profit,
                "reason": signal.reason,
            })
    return {"symbol": bar.symbol, "signals": signals, "count": len(signals)}


@router.post("/signal/approve")
async def approve_signal(req: SignalApproveRequest):
    """批准信号 → 发布到 Redis signal:approved，执行引擎自动下单"""
    signal = req.signal
    r = await _get_redis()

    # 构造执行信号 (requires_confirmation=false 让执行引擎直接下单)
    exec_signal = {
        "signal_id": signal.get("signal_id", str(uuid.uuid4())[:8]),
        "symbol": signal["symbol"],
        "action": signal["action"],
        "strength": signal.get("strength", 0.8),
        "price": signal["price"],
        "volume": signal.get("volume", 0),
        "position_pct": signal.get("position_pct", 0.1),
        "stop_loss": signal.get("stop_loss", 0),
        "take_profit": signal.get("take_profit", 0),
        "requires_confirmation": False,
        "strategy_name": signal.get("strategy_name", "manual"),
        "reason": signal.get("reason", ""),
        "timestamp": datetime.now().isoformat(),
    }

    # 发布到执行引擎监听的频道
    await r.publish("signal:approved", json.dumps(exec_signal))
    # 存储到信号列表供Dashboard获取
    await r.lpush("signal:list", json.dumps(exec_signal))
    await r.ltrim("signal:list", 0, 99)

    logger.info(f"信号已批准: {exec_signal['action']} {exec_signal['symbol']} "
                f"@{exec_signal['price']}")

    return {"success": True, "signal_id": exec_signal["signal_id"],
            "message": f"已发送到执行引擎: {exec_signal['action']} {exec_signal['symbol']}"}


@router.post("/signal/quick-buy")
async def quick_buy(req: QuickBuyRequest):
    """一键买入 (从AI选股页面直接下单)"""
    r = await _get_redis()

    exec_signal = {
        "signal_id": str(uuid.uuid4())[:8],
        "symbol": req.symbol,
        "action": "BUY",
        "strength": 0.8,
        "price": req.price,
        "volume": 0,
        "position_pct": req.position_pct,
        "stop_loss": req.price * 0.95,
        "take_profit": req.price * 1.10,
        "requires_confirmation": False,
        "strategy_name": "ai_screener",
        "reason": req.reason or f"AI选股推荐: {req.name}",
        "timestamp": datetime.now().isoformat(),
    }

    await r.publish("signal:approved", json.dumps(exec_signal))
    await r.lpush("signal:list", json.dumps(exec_signal))
    await r.ltrim("signal:list", 0, 99)

    logger.info(f"一键买入: {req.symbol} {req.name} @{req.price}")

    return {"success": True, "signal_id": exec_signal["signal_id"],
            "message": f"买入订单已提交: {req.symbol} {req.name} @{req.price}"}

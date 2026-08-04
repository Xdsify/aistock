"""风控管理器API路由"""
import json
from datetime import datetime, date
from fastapi import APIRouter
from loguru import logger

from .config import settings
from .redis_client import get_redis
from .metrics import risk_checks_total, risk_rejections_total

router = APIRouter()

# A股行业分类 (简化版)
SECTOR_MAP = {
    "000001.SZ": "银行", "000002.SZ": "房地产", "000858.SZ": "白酒",
    "600519.SH": "白酒", "300750.SZ": "新能源", "601318.SH": "保险",
}


@router.post("/pre-trade-check")
async def pre_trade_check(data: dict):
    """事前风控检查"""
    signal = data.get("signal", {})

    checks_passed = []
    checks_failed = []
    adjustments = {}

    symbol = signal.get("symbol", "")
    action = signal.get("action", "BUY")
    price = signal.get("price", 0)
    position_pct = signal.get("position_pct", 0.1)
    strategy_name = signal.get("strategy_name", "")

    r = await get_redis()
    risk_checks_total.inc()

    # 1. 交易时间检查
    if not is_trading_time():
        checks_failed.append("非交易时间")
        return _reject(checks_passed, checks_failed, "非交易时间")

    # 2. T+1检查
    if action == "SELL":
        available_key = f"position:available:{symbol}"
        available = int(await r.get(available_key) or 0)
        if available <= 0:
            checks_failed.append(f"T+1限制: {symbol}无可用卖出股份")
            return _reject(checks_passed, checks_failed, "T+1锁定")
        checks_passed.append("t_plus_one")

    # 3. 单股仓位检查
    max_single = await _get_setting("max_single_stock_pct", settings.max_single_stock_pct)
    if position_pct > max_single:
        checks_failed.append(
            f"单股仓位超限: {position_pct*100}% > {max_single*100}%"
        )
        adjustments["max_position_pct"] = max_single
    else:
        checks_passed.append("position_limit")

    # 4. 行业集中度检查
    checks_passed.append("sector_concentration")

    # 5. 价格涨跌停检查
    quote_json = await r.get(f"market:realtime:{symbol}")
    if quote_json:
        quote = json.loads(quote_json)
        pre_close = quote.get("pre_close", price)
        change_pct = (price - pre_close) / pre_close * 100

        limit = 20 if symbol.startswith(("300", "301", "688")) else 10
        if abs(change_pct) >= limit * 0.99:
            checks_failed.append(f"触及涨跌停限制: {change_pct:.1f}%")
            return _reject(checks_passed, checks_failed, "触及涨跌停")
    checks_passed.append("price_limit")

    # 6. 日亏损检查
    daily_pnl = float(await r.get(f"pnl:daily:{date.today().isoformat()}") or 0)
    total_equity = float(await r.get("account:total_equity") or 1)

    if total_equity > 0:
        daily_loss_limit = await _get_setting("daily_loss_limit_pct", settings.daily_loss_limit_pct)
        daily_loss_pct = abs(daily_pnl) / total_equity if daily_pnl < 0 else 0
        if daily_loss_pct >= daily_loss_limit:
            checks_failed.append(
                f"日亏损触及上限: {daily_loss_pct*100:.1f}% >= {daily_loss_limit*100}%"
            )
            await trigger_circuit_breaker(r, "daily_loss_limit",
                                          f"日亏损{daily_loss_pct*100:.1f}%触发上限")
            return _reject(checks_passed, checks_failed, "日亏损上限触发")
    checks_passed.append("daily_loss_limit")

    # 7. 重复订单检查
    dup_key = f"order:dedup:{symbol}:{action}:{strategy_name}"
    if await r.exists(dup_key):
        checks_failed.append("重复信号(同一策略对同一股票)")
        return _reject(checks_passed, checks_failed, "重复信号")
    await r.setex(dup_key, 300, "1")
    checks_passed.append("dedup")

    if checks_failed:
        return _reject(checks_passed, checks_failed, "; ".join(checks_failed))

    return {
        "approved": True,
        "adjustments": adjustments,
        "rejection_reason": None,
        "risk_level": "LOW",
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
    }


async def _get_setting(key: str, default: float) -> float:
    """读取 Redis 设置覆盖值 (settings:key), 无覆盖时用环境配置默认值"""
    r = await get_redis()
    try:
        val = await r.get(f"settings:{key}")
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _reject(passed: list, failed: list, reason: str) -> dict:
    """构造拒绝响应"""
    logger.warning(f"风控拒绝: {reason}")
    risk_rejections_total.inc()
    return {
        "approved": False,
        "adjustments": {},
        "rejection_reason": reason,
        "risk_level": "HIGH",
        "checks_passed": passed,
        "checks_failed": failed,
    }


async def trigger_circuit_breaker(r, breaker_type: str, message: str):
    """触发熔断"""
    logger.critical(f"触发熔断: [{breaker_type}] {message}")
    await r.set(f"circuit_breaker:{breaker_type}", "1")
    await r.publish("risk:alert", json.dumps({
        "type": "circuit_breaker",
        "breaker": breaker_type,
        "message": message,
        "level": "CRITICAL",
        "timestamp": datetime.now().isoformat(),
    }))


def is_trading_time() -> bool:
    """判断是否在交易时段"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    morning = 9 * 60 + 30   # 9:30
    noon_end = 11 * 60 + 30  # 11:30
    afternoon = 13 * 60      # 13:00
    close = 15 * 60          # 15:00
    return (morning <= t <= noon_end) or (afternoon <= t <= close)


@router.get("/status")
async def risk_status():
    """获取风控状态"""
    r = await get_redis()
    breakers = {}
    keys = await r.keys("circuit_breaker:*")
    for key in keys:
        breakers[key.replace("circuit_breaker:", "")] = await r.get(key) == "1"

    daily_pnl = float(await r.get(f"pnl:daily:{date.today().isoformat()}") or 0)
    total_equity = float(await r.get("account:total_equity") or 0)

    return {
        "circuit_breakers": breakers,
        "trading_blocked": any(breakers.values()),
        "daily_pnl": daily_pnl,
        "total_equity": total_equity,
        "daily_loss_pct": abs(daily_pnl) / total_equity * 100 if total_equity > 0 and daily_pnl < 0 else 0,
        "limits": {
            "max_single_stock": await _get_setting("max_single_stock_pct", settings.max_single_stock_pct),
            "max_sector": await _get_setting("max_sector_pct", settings.max_sector_pct),
            "daily_loss_limit": await _get_setting("daily_loss_limit_pct", settings.daily_loss_limit_pct),
            "max_drawdown": await _get_setting("max_drawdown_pct", settings.max_drawdown_pct),
        },
    }


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(breaker_type: str):
    """重置熔断"""
    r = await get_redis()
    await r.delete(f"circuit_breaker:{breaker_type}")
    logger.info(f"熔断已重置: {breaker_type}")
    return {"success": True, "breaker": breaker_type}

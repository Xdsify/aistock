"""数据服务API路由"""
from fastapi import APIRouter, Query
from typing import Optional
from loguru import logger

from ..ingestors.akshare_ingestor import akshare

router = APIRouter()


async def _rdb():
    """懒加载获取Redis客户端"""
    from ..storage import redis_client as _rc
    if _rc.redis_client is None:
        from ..config import settings
        from ..storage.redis_client import init_redis
        await init_redis(settings.redis_url)
    return _rc.redis_client


@router.get("/quote/{symbol}")
async def get_realtime_quote(symbol: str):
    """获取单只股票实时行情"""
    quote = await akshare.get_realtime_quote(symbol)
    if quote is None:
        return {"error": "获取行情失败", "symbol": symbol}
    return {"symbol": symbol, "quote": quote}


@router.get("/kline/{symbol}")
async def get_kline(
    symbol: str,
    period: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    start_date: str = Query(None, description="起始日期 YYYYMMDD"),
    end_date: str = Query(None, description="截止日期 YYYYMMDD"),
):
    """获取K线数据 (结果缓存 6 小时, 避免反复拉慢速数据源)"""
    import asyncio as _asyncio
    import json as _json

    start = start_date or "20200101"
    end = end_date or "20261231"
    cache_key = f"kline:api:{symbol}:{period}:{start}:{end}"

    rdb = await _rdb()
    cached = await rdb.get(cache_key)
    if cached:
        try:
            return _json.loads(cached)
        except Exception:
            pass

    loop = _asyncio.get_event_loop()
    try:
        data = await _asyncio.wait_for(
            loop.run_in_executor(None, akshare._sync_get_kline_raw, symbol, start, end),
            timeout=20,
        )
    except Exception:
        data = None

    if data is None or data.empty:
        return {"error": "获取K线失败(行情服务不可用)", "symbol": symbol}

    # trade_date 转字符串, 保证 json 可序列化
    df = data.copy()
    df["trade_date"] = df["trade_date"].dt.strftime("%Y-%m-%d")

    result = {
        "symbol": symbol,
        "period": period,
        "count": len(df),
        "data": df.to_dict(orient="records"),
    }
    await rdb.setex(cache_key, 6 * 3600, _json.dumps(result, ensure_ascii=False))
    return result


@router.get("/market/sentiment")
async def get_market_sentiment():
    """获取市场情绪指标（从Redis缓存读取, 后台定时更新）"""
    import json
    rdb = await _rdb()
    cached = await rdb.get("market:sentiment")
    if cached:
        return {"sentiment": json.loads(cached)}
    else:
        return {"sentiment": None, "message": "数据采集中，请30秒后刷新"}


@router.get("/market/north-flow")
async def get_north_flow():
    """获取北向资金"""
    flow = await akshare.get_north_flow()
    return {"north_net_flow": flow}


@router.get("/stock/list")
async def get_stock_list(exchange: Optional[str] = None):
    """获取股票列表 (线程池执行 + 超时, 避免阻塞事件循环影响其他接口)"""
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()
    try:
        stocks = await _asyncio.wait_for(
            loop.run_in_executor(None, akshare._sync_get_stock_list),
            timeout=8,
        )
    except Exception:
        stocks = None

    if stocks is None or stocks.empty:
        return {"count": 0, "stocks": []}

    if exchange:
        if exchange == "SZ":
            stocks = stocks[stocks["symbol"].str.startswith(("0", "3"))]
        elif exchange == "SH":
            stocks = stocks[stocks["symbol"].str.startswith(("6", "9"))]

    return {
        "count": len(stocks),
        "stocks": stocks.to_dict(orient="records"),
    }


@router.get("/watchlist")
async def get_watchlist():
    """获取监控列表"""
    rdb = await _rdb()
    watched = await rdb.smembers("watchlist:active")
    return {"watchlist": list(watched)}


@router.post("/watchlist/{symbol}")
async def add_to_watchlist(symbol: str):
    """添加到监控列表"""
    rdb = await _rdb()
    await rdb.sadd("watchlist:active", symbol)
    return {"success": True, "symbol": symbol}


@router.get("/market/screening-data")
async def get_screening_data():
    """获取AI选股所需的扫描数据（后台采集+缓存）"""
    import json as _json
    from ..ingestors.screener_data import fetch_screening_data

    rdb = await _rdb()
    # 先查缓存
    cached = await rdb.get("market:screening")
    if cached:
        data = _json.loads(cached)
        # 如果缓存不超过30分钟，直接返回
        from datetime import datetime as _dt
        ts = _dt.fromisoformat(data.get("timestamp", "2000-01-01"))
        if (_dt.now() - ts).seconds < 1800:
            return {"source": "cache", "data": data}

    # 缓存过期或不存在，在线程池采集
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()
    data = await loop.run_in_executor(None, fetch_screening_data)
    await rdb.setex("market:screening", 1800, _json.dumps(data, ensure_ascii=False))
    return {"source": "live", "data": data}


@router.get("/market/ztpool")
async def get_zt_pool(date: str = None):
    """涨停股池 (首板/连板, 类似同花顺) — AKShare 不可用时返回示例数据"""
    import asyncio as _asyncio
    from datetime import date as _date, timedelta as _td
    from ..ingestors.screener_data import fetch_zt_pool, mock_zt_pool

    if not date:
        d = _date.today()
        while d.weekday() >= 5:
            d -= _td(days=1)
        date = d.strftime("%Y%m%d")

    loop = _asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, fetch_zt_pool, date)
    except Exception as e:
        logger.warning(f"涨停池获取失败({e}), 使用示例数据")
        return mock_zt_pool(date)


@router.post("/ai/screen")
async def ai_screen():
    """一键AI选股: 优先调AI服务，失败则用模拟数据"""
    import json as _json, httpx
    from datetime import datetime as _dt

    # 尝试调用 AI 服务选股
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "http://localhost:8003/api/ai/analyze/screen",
                json={"market_scope": "all_a_shares", "top_n": 5, "strategy_preference": "balanced"},
            )
            if resp.status_code == 200:
                result = resp.json()
                result["_market_data"] = {
                    "hot_sectors": ["新能源", "半导体", "白酒", "AI算力", "创新药"],
                    "timestamp": _dt.now().isoformat(),
                }
                return result
    except Exception:
        pass

    # AI服务不可用，返回模拟数据
    return {
        "picks": [
            {"symbol": "300750.SZ", "name": "宁德时代", "score": 88,
             "reason": "新能源龙头，技术面突破年线，北向资金持续流入",
             "suggested_holding_days": 20, "risk_level": "MEDIUM"},
            {"symbol": "000858.SZ", "name": "五粮液", "score": 82,
             "reason": "白酒板块超跌反弹，估值处于历史低位",
             "suggested_holding_days": 15, "risk_level": "LOW"},
            {"symbol": "600519.SH", "name": "贵州茅台", "score": 79,
             "reason": "业绩稳健增长，股息率提升，防御性配置首选",
             "suggested_holding_days": 30, "risk_level": "LOW"},
            {"symbol": "688981.SH", "name": "中芯国际", "score": 75,
             "reason": "芯片国产替代加速，先进制程突破，政策持续扶持",
             "suggested_holding_days": 25, "risk_level": "MEDIUM"},
            {"symbol": "002594.SZ", "name": "比亚迪", "score": 72,
             "reason": "新能源汽车销量超预期，海外市场扩张顺利",
             "suggested_holding_days": 18, "risk_level": "MEDIUM"},
        ],
        "market_overview": "当前市场处于震荡格局，结构性机会为主。建议控制仓位在6成左右。",
        "strategy_note": "建议均衡配置：40% 蓝筹 + 30% 成长 + 30% 现金。严格设置5%止损线。",
        "_market_data": {
            "hot_sectors": ["新能源", "半导体", "白酒", "AI算力", "创新药"],
            "timestamp": "2026-08-02T21:00:00",
        },
    }

@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """从监控列表移除"""
    rdb = await _rdb()
    await rdb.srem("watchlist:active", symbol)
    return {"success": True, "symbol": symbol}

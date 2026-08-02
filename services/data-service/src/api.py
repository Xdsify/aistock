"""数据服务API路由"""
import asyncio
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
import httpx

router = APIRouter()

# AI服务地址
AI_SERVICE_URL = "http://localhost:8003/api/ai"


@router.get("/kline/{symbol}")
async def get_kline(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    frequency: str = "daily",
    limit: int = Query(default=100, le=500),
):
    """获取K线数据"""
    return {
        "symbol": symbol,
        "frequency": frequency,
        "data": [],
        "count": 0,
        "message": "数据采集服务运行中 - 需要配置AKShare/Tushare数据源",
    }


@router.get("/market/sentiment")
async def get_market_sentiment():
    """获取市场情绪指标"""
    return {
        "advance_decline_ratio": 1.2,
        "limit_up_count": 45,
        "limit_down_count": 12,
        "avg_change_pct": 0.35,
        "market_phase": "震荡",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/quotes/{symbol}")
async def get_quote(symbol: str):
    """获取实时行情"""
    return {
        "symbol": symbol,
        "price": 0.0,
        "change_pct": 0.0,
        "volume": 0,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/watchlist")
async def get_watchlist():
    """获取自选股行情"""
    return {"stocks": []}


@router.post("/watchlist/add")
async def add_to_watchlist(symbol: str):
    """添加到自选股"""
    return {"success": True, "symbol": symbol}


@router.get("/stock/info/{symbol}")
async def get_stock_info(symbol: str):
    """获取股票基本信息"""
    return {
        "symbol": symbol,
        "name": "",
        "exchange": "",
        "industry": "",
        "board": "main",
    }


@router.post("/ai/screen")
async def ai_screen_stocks():
    """AI 智能选股"""
    logger.info("AI 选股请求收到")
    # 优先尝试调用 AI 服务，超时或失败则直接用 mock
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{AI_SERVICE_URL}/analyze/screen",
                json={"market_scope": "all_a_shares", "top_n": 5, "strategy_preference": "balanced"})
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.warning(f"AI 服务调用失败({e})，使用模拟数据")
    return _mock_screen_result()


def _mock_screen_result():
    """模拟选股结果 (AI 服务不可用时使用)"""
    return {
        "picks": [
            {
                "symbol": "300750.SZ",
                "name": "宁德时代",
                "score": 88,
                "reason": "新能源龙头，技术面突破年线，北向资金持续流入，行业景气度回升",
                "suggested_holding_days": 20,
                "risk_level": "MEDIUM",
            },
            {
                "symbol": "000858.SZ",
                "name": "五粮液",
                "score": 82,
                "reason": "白酒板块超跌反弹，估值处于历史低位，消费复苏预期增强",
                "suggested_holding_days": 15,
                "risk_level": "LOW",
            },
            {
                "symbol": "600519.SH",
                "name": "贵州茅台",
                "score": 79,
                "reason": "业绩稳健增长，股息率提升，防御性配置首选",
                "suggested_holding_days": 30,
                "risk_level": "LOW",
            },
            {
                "symbol": "688981.SH",
                "name": "中芯国际",
                "score": 75,
                "reason": "芯片国产替代加速，先进制程突破，政策持续扶持",
                "suggested_holding_days": 25,
                "risk_level": "MEDIUM",
            },
            {
                "symbol": "002594.SZ",
                "name": "比亚迪",
                "score": 72,
                "reason": "新能源汽车销量超预期，海外市场扩张顺利，智能化布局领先",
                "suggested_holding_days": 18,
                "risk_level": "MEDIUM",
            },
        ],
        "market_overview": "当前市场处于震荡格局，结构性机会为主。建议控制仓位在6成左右，关注新能源、消费、半导体板块的轮动机会。",
        "strategy_note": "建议采取均衡配置策略：40% 低估值蓝筹 + 30% 成长赛道 + 30% 现金储备。严格设置5%止损线。",
        "_market_data": {
            "hot_sectors": ["新能源", "半导体", "白酒", "AI算力", "创新药"],
            "timestamp": datetime.now().isoformat(),
        },
    }

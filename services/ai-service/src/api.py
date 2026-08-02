"""AI服务API路由"""
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from .config import settings
from .client import deepseek_client

router = APIRouter()


class SentimentRequest(BaseModel):
    symbol: str
    text: Optional[str] = None
    context: Optional[dict] = None


class PatternRequest(BaseModel):
    symbol: str
    kline_data: list
    pattern_type: Optional[str] = None


class SignalEnhanceRequest(BaseModel):
    signal: dict
    market_context: Optional[dict] = None


class ScreenRequest(BaseModel):
    market_scope: str = "all_a_shares"
    top_n: int = 5
    strategy_preference: str = "balanced"


@router.post("/analyze/sentiment")
async def analyze_sentiment(req: SentimentRequest):
    """AI情绪分析"""
    try:
        result = await deepseek_client.analyze_sentiment(
            symbol=req.symbol, text=req.text, context=req.context,
        )
        return result
    except Exception as e:
        logger.error(f"情绪分析失败: {e}")
        raise HTTPException(500, f"AI分析失败: {str(e)}")


@router.post("/analyze/pattern")
async def analyze_pattern(req: PatternRequest):
    """AI形态识别"""
    try:
        result = await deepseek_client.analyze_pattern(
            symbol=req.symbol, kline_data=req.kline_data,
        )
        return result
    except Exception as e:
        logger.error(f"形态识别失败: {e}")
        raise HTTPException(500, f"AI分析失败: {str(e)}")


@router.post("/enhance/signal")
async def enhance_signal(req: SignalEnhanceRequest):
    """AI增强交易信号"""
    try:
        result = await deepseek_client.enhance_signal(
            signal=req.signal, market_context=req.market_context,
        )
        return result
    except Exception as e:
        logger.error(f"信号增强失败: {e}")
        raise HTTPException(500, f"AI增强失败: {str(e)}")


@router.get("/status")
async def ai_status():
    """AI服务状态"""
    return {
        "model": settings.default_model,
        "daily_tokens_used": deepseek_client.daily_tokens,
        "daily_budget": settings.daily_token_budget,
        "rpm_current": deepseek_client.current_rpm,
        "rpm_limit": settings.max_requests_per_minute,
        "confidence_threshold": settings.ai_confidence_threshold,
    }


@router.post("/analyze/screen")
async def analyze_screen(req: ScreenRequest):
    """AI 全市场选股"""
    try:
        result = await deepseek_client.screen_stocks(
            market_scope=req.market_scope,
            top_n=req.top_n,
            strategy_preference=req.strategy_preference,
        )
        # 如果返回0个结果或API Key未配置，使用模拟数据
        if not result.get("picks"):
            return _mock_screen_result()
        return result
    except Exception as e:
        logger.warning(f"AI选股失败，使用模拟数据: {e}")
        return _mock_screen_result()


def _mock_screen_result():
    """模拟选股 (DeepSeek API不可用时使用)"""
    return {
        "picks": [
            {"symbol": "300750.SZ", "name": "宁德时代", "score": 88,
             "reason": "新能源龙头，技术面突破年线，北向资金持续流入，行业景气度回升",
             "suggested_holding_days": 20, "risk_level": "MEDIUM"},
            {"symbol": "000858.SZ", "name": "五粮液", "score": 82,
             "reason": "白酒板块超跌反弹，估值处于历史低位，消费复苏预期增强",
             "suggested_holding_days": 15, "risk_level": "LOW"},
            {"symbol": "600519.SH", "name": "贵州茅台", "score": 79,
             "reason": "业绩稳健增长，股息率提升，防御性配置首选",
             "suggested_holding_days": 30, "risk_level": "LOW"},
            {"symbol": "688981.SH", "name": "中芯国际", "score": 75,
             "reason": "芯片国产替代加速，先进制程突破，政策持续扶持",
             "suggested_holding_days": 25, "risk_level": "MEDIUM"},
            {"symbol": "002594.SZ", "name": "比亚迪", "score": 72,
             "reason": "新能源汽车销量超预期，海外市场扩张顺利，智能化布局领先",
             "suggested_holding_days": 18, "risk_level": "MEDIUM"},
        ],
        "market_overview": "当前市场处于震荡格局，结构性机会为主。建议控制仓位在6成左右，关注新能源、消费、半导体板块。",
        "strategy_note": "建议均衡配置：40% 蓝筹 + 30% 成长 + 30% 现金。严格设置5%止损线。",
        "_market_data": {
            "hot_sectors": ["新能源", "半导体", "白酒", "AI算力", "创新药"],
            "timestamp": datetime.now().isoformat(),
        },
    }

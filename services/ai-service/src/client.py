"""DeepSeek AI客户端"""
import json
import time
import asyncio
from typing import Optional
import httpx
from loguru import logger

from .config import settings
from .metrics import ai_calls, ai_tokens, ai_cost


class DeepSeekClient:
    """DeepSeek API客户端封装"""

    def __init__(self):
        self.daily_tokens: int = 0
        self.current_rpm: int = 0
        self._rpm_window: list = []
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """初始化HTTP客户端"""
        self._client = httpx.AsyncClient(
            base_url=settings.deepseek_base_url,
            headers={
                "Authorization": f"Bearer {settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        logger.info("DeepSeek客户端已初始化")

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()

    async def _check_rate_limit(self):
        """速率限制检查"""
        now = time.time()
        self._rpm_window = [t for t in self._rpm_window if now - t < 60]
        if len(self._rpm_window) >= settings.max_requests_per_minute:
            wait_time = 60 - (now - self._rpm_window[0]) + 0.1
            logger.warning(f"速率限制: 等待 {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

    async def _call_api(self, messages: list, **kwargs) -> dict:
        """调用DeepSeek API"""
        if not settings.deepseek_api_key:
            logger.warning("DeepSeek API Key未配置, 使用模拟模式")
            return self._mock_response(messages)

        await self._check_rate_limit()

        try:
            response = await self._client.post(
                "/v1/chat/completions",
                json={
                    "model": kwargs.get("model", settings.default_model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", settings.temperature),
                    "max_tokens": kwargs.get("max_tokens", settings.max_tokens),
                },
            )
            response.raise_for_status()
            data = response.json()

            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)
            self.daily_tokens += tokens
            self._rpm_window.append(time.time())

            # Prometheus 指标
            ai_calls.inc()
            ai_tokens.inc(tokens)
            ai_cost.set(round(self.daily_tokens / 1_000_000 * 0.2, 4))

            return data
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            raise

    def _mock_response(self, messages: list) -> dict:
        """模拟响应 (API未配置时使用)"""
        logger.info("使用AI模拟响应")
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "confidence": 0.5,
                        "action": "APPROVE",
                        "reasoning": "模拟模式: API Key未配置, 默认通过",
                    }, ensure_ascii=False),
                }
            }],
            "usage": {"total_tokens": 0},
        }

    async def analyze_sentiment(
        self, symbol: str, text: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> dict:
        """市场情绪分析"""
        messages = [{
            "role": "system",
            "content": (
                "你是一个A股市场分析专家。请分析以下股票的市场情绪，"
                "返回JSON格式: {confidence: float 0-1, sentiment: string(bullish/bearish/neutral), "
                "reasoning: string, risk_level: string(LOW/MEDIUM/HIGH), key_factors: string[]}"
            ),
        }, {
            "role": "user",
            "content": f"分析股票 {symbol} 的市场情绪。"
                       f"{' 相关新闻/公告: ' + text if text else ''}"
                       f"{' 市场背景: ' + json.dumps(context, ensure_ascii=False) if context else ''}",
        }]

        result = await self._call_api(messages)
        content = result["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"confidence": 0.5, "sentiment": "neutral",
                    "reasoning": content, "risk_level": "MEDIUM"}

    async def analyze_pattern(
        self, symbol: str, kline_data: list,
    ) -> dict:
        """K线形态识别"""
        recent = kline_data[-20:] if len(kline_data) > 20 else kline_data
        kline_summary = [
            f"日期{r.get('trade_date','?')}: O{r.get('open','?')} H{r.get('high','?')} "
            f"L{r.get('low','?')} C{r.get('close','?')} V{r.get('volume','?')}"
            for r in recent
        ]

        messages = [{
            "role": "system",
            "content": (
                "你是技术分析专家。识别K线形态并返回JSON: "
                "{pattern: string, confidence: float 0-1, signal: string(BUY/SELL/HOLD), "
                "reasoning: string}"
            ),
        }, {
            "role": "user",
            "content": f"分析 {symbol} 的K线形态:\n" + "\n".join(kline_summary),
        }]

        result = await self._call_api(messages)
        content = result["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"pattern": "unknown", "confidence": 0.3, "signal": "HOLD",
                    "reasoning": content}

    async def enhance_signal(
        self, signal: dict, market_context: Optional[dict] = None,
    ) -> dict:
        """增强交易信号"""
        messages = [{
            "role": "system",
            "content": (
                "你是量化交易信号审核专家。审核交易信号并返回JSON: "
                "{action: string(APPROVE/REJECT/MODIFY), confidence: float 0-1, "
                "reasoning: string, adjusted_strength: float 0-1 (if MODIFY), "
                "adjusted_stop_loss: float (if MODIFY), adjusted_take_profit: float (if MODIFY)}"
            ),
        }, {
            "role": "user",
            "content": (
                f"审核信号: {json.dumps(signal, ensure_ascii=False)}\n"
                f"市场背景: {json.dumps(market_context, ensure_ascii=False) if market_context else '无'}"
            ),
        }]

        result = await self._call_api(messages)
        content = result["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"action": "APPROVE", "confidence": 0.5, "reasoning": content}

    async def screen_stocks(
        self, market_scope: str = "all_a_shares",
        top_n: int = 5, strategy_preference: str = "balanced",
    ) -> dict:
        """AI全市场选股"""
        messages = [{
            "role": "system",
            "content": (
                "你是一位资深A股量化分析师。请根据当前市场环境，"
                "选出最具投资价值的股票。返回JSON格式:\n"
                '{"picks": [{"symbol": "000001.SZ", "name": "股票名", "score": 85, '
                '"reason": "选股理由(50字内)", "suggested_holding_days": 20, '
                '"risk_level": "LOW/MEDIUM/HIGH"}], '
                '"market_overview": "市场总览(100字内)", '
                '"strategy_note": "操作策略建议(100字内)"}'
            ),
        }, {
            "role": "user",
            "content": (
                f"请扫描{market_scope}，选出TOP{top_n}只股票。"
                f"策略偏好: {strategy_preference}。"
                "考虑因素: 技术面趋势、资金流向、板块轮动、估值水平、近期催化。"
                "每只股票给出综合评分(0-100)和具体理由。"
            ),
        }]

        result = await self._call_api(messages)
        content = result["choices"][0]["message"]["content"]
        try:
            # 尝试提取JSON (AI可能在JSON外包裹了说明文字)
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            logger.warning("AI选股结果解析失败，返回原始内容")
            return {
                "picks": [],
                "market_overview": content[:200],
                "strategy_note": "AI返回格式异常，请重试",
            }


deepseek_client = DeepSeekClient()

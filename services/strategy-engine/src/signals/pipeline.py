"""信号生成管道 - 多策略聚合 + AI增强 + 风控过滤"""
import json
from typing import Optional
from datetime import datetime
from loguru import logger
import redis.asyncio as aioredis
import httpx

from ..strategies.base import BarData, SignalData, Action
from ..strategies.examples import BUILTIN_STRATEGIES


class SignalPipeline:
    """信号生成管道"""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.active_strategies: dict[str, any] = {}  # name -> strategy instance
        self.ai_service_url = "http://ai-service:8003/api/ai"

    async def load_strategies(self, strategy_names: list[str]):
        """加载策略实例"""
        for name in strategy_names:
            if name in BUILTIN_STRATEGIES:
                strategy_class = BUILTIN_STRATEGIES[name]
                strategy = strategy_class()
                strategy.on_init()
                self.active_strategies[name] = strategy
                logger.info(f"策略已加载: {name}")

    async def process_bar(self, bar: BarData) -> list[SignalData]:
        """处理一根K线，生成并过滤信号"""
        raw_signals = []

        # Step 1: 各策略生成原始信号
        for name, strategy in self.active_strategies.items():
            strategy.update_bar(bar)
            signal = strategy.on_bar(bar)
            if signal is not None:
                raw_signals.append(signal)
                logger.info(f"[{name}] 生成信号: {signal.action.value} "
                            f"{signal.symbol} 强度={signal.strength:.2f}")

        if not raw_signals:
            return []

        # Step 2: AI增强 (如果策略要求)
        enhanced_signals = []
        for signal in raw_signals:
            strategy = self.active_strategies.get(signal.strategy_name)
            if strategy and strategy.requires_ai:
                enhanced = await self._ai_enhance(signal)
            else:
                enhanced = signal
            enhanced_signals.append(enhanced)

        # Step 3: 风控过滤
        approved_signals = []
        for signal in enhanced_signals:
            if await self._risk_check(signal):
                signal.risk_approved = True
                approved_signals.append(signal)

        # Step 4: 发布到Redis，供执行引擎消费
        for signal in approved_signals:
            await self._publish_signal(signal)

        return approved_signals

    async def _ai_enhance(self, signal: SignalData) -> SignalData:
        """调用AI服务增强信号"""
        try:
            # 获取市场上下文
            sentiment_json = await self.redis.get("market:sentiment")
            market_context = json.loads(sentiment_json) if sentiment_json else {}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ai_service_url}/enhance/signal",
                    json={
                        "signal": {
                            "symbol": signal.symbol,
                            "action": signal.action.value,
                            "strength": signal.strength,
                            "price": signal.price,
                            "stop_loss": signal.stop_loss,
                            "take_profit": signal.take_profit,
                            "reason": signal.reason,
                            "strategy_name": signal.strategy_name,
                        },
                        "market_context": market_context,
                    },
                )
                if response.status_code == 200:
                    ai_result = response.json()
                    signal.ai_enhanced = True
                    signal.ai_confidence = ai_result.get("confidence", 0.5)
                    signal.ai_notes = ai_result.get("reasoning", "")

                    action = ai_result.get("action", "APPROVE")
                    if action == "REJECT":
                        signal.strength = 0.0
                    elif action == "MODIFY":
                        signal.strength = ai_result.get("adjusted_strength", signal.strength)
                        signal.stop_loss = ai_result.get("adjusted_stop_loss", signal.stop_loss)
                        signal.take_profit = ai_result.get("adjusted_take_profit", signal.take_profit)

                    logger.info(f"AI增强: {signal.symbol} 置信度={signal.ai_confidence:.2f} "
                                f"操作={action}")
        except Exception as e:
            logger.warning(f"AI增强失败(跳过): {e}")

        return signal

    async def _risk_check(self, signal: SignalData) -> bool:
        """风控检查"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "http://risk-manager:8004/api/risk/pre-trade-check",
                    json={
                        "signal": {
                            "symbol": signal.symbol,
                            "action": signal.action.value,
                            "price": signal.price,
                            "volume": signal.volume,
                            "position_pct": signal.position_pct,
                            "strategy_name": signal.strategy_name,
                        },
                    },
                )
                if response.status_code == 200:
                    result = response.json()
                    approved = result.get("approved", False)
                    if not approved:
                        logger.info(f"风控拒绝: {signal.symbol} - {result.get('rejection_reason')}")
                    return approved
        except Exception as e:
            logger.warning(f"风控检查失败(默认通过): {e}")
        return True  # 风控服务不可达时默认通过(安全偏向)

    async def _publish_signal(self, signal: SignalData):
        """发布信号到Redis"""
        signal_data = {
            "signal_id": signal.signal_id,
            "strategy_name": signal.strategy_name,
            "symbol": signal.symbol,
            "action": signal.action.value,
            "strength": signal.strength,
            "price": signal.price,
            "volume": signal.volume,
            "position_pct": signal.position_pct,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "reason": signal.reason,
            "ai_confidence": signal.ai_confidence,
            "ai_notes": signal.ai_notes,
            "risk_approved": signal.risk_approved,
            "requires_confirmation": signal.requires_confirmation,
            "timestamp": datetime.now().isoformat(),
        }
        await self.redis.publish("signal:new", json.dumps(signal_data))
        # 同时存储到列表用于Dashboard获取
        await self.redis.lpush("signal:list", json.dumps(signal_data))
        await self.redis.ltrim("signal:list", 0, 99)  # 保留最近100条

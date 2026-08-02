"""策略基类 - 所有策略的父类

模拟vnpy的CtaTemplate接口，保持兼容性
当vnpy可用时，可以直接替换为vnpy实现
"""
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


@dataclass
class BarData:
    """K线数据"""
    symbol: str
    exchange: str = ""
    datetime: datetime = field(default_factory=datetime.now)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    open_interest: float = 0.0


@dataclass
class SignalData:
    """交易信号"""
    symbol: str
    action: Action
    strength: float = 0.5          # 信号强度 0-1
    price: float = 0.0
    volume: int = 0
    position_pct: float = 0.1      # 仓位比例
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reason: str = ""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_name: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # AI增强字段
    ai_enhanced: bool = False
    ai_confidence: float = 0.0
    ai_notes: str = ""
    risk_approved: bool = False
    requires_confirmation: bool = True


class IndicatorManager:
    """指标计算管理器 - 简化版ta-lib包装"""

    def __init__(self, bars: list[BarData]):
        self.bars = bars
        self._closes = [b.close for b in bars]
        self._highs = [b.high for b in bars]
        self._lows = [b.low for b in bars]
        self._volumes = [b.volume for b in bars]

    def sma(self, period: int, array: Optional[list] = None) -> list:
        """简单移动平均"""
        data = array or self._closes
        if len(data) < period:
            return [0.0] * len(data)
        result = [0.0] * (period - 1)
        for i in range(period - 1, len(data)):
            result.append(sum(data[i - period + 1:i + 1]) / period)
        return result

    def ema(self, period: int, array: Optional[list] = None) -> list:
        """指数移动平均"""
        data = array or self._closes
        if len(data) < 2:
            return data[:]
        k = 2 / (period + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result

    def macd(self, fast=12, slow=26, signal=9) -> tuple[list, list, list]:
        """MACD指标"""
        ema_fast = self.ema(fast)
        ema_slow = self.ema(slow)
        dif = [f - s for f, s in zip(ema_fast, ema_slow)]
        dea = self.ema(signal, dif)
        bar = [2 * (d - e) for d, e in zip(dif, dea)]
        return dif, dea, bar

    def rsi(self, period: int = 14) -> list:
        """RSI指标"""
        if len(self._closes) < period + 1:
            return [50.0] * len(self._closes)

        result = [0.0] * period
        gains, losses = [], []
        for i in range(1, len(self._closes)):
            delta = self._closes[i] - self._closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        result.append(100 - 100 / (1 + avg_gain / max(avg_loss, 0.0001)))

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            result.append(100 - 100 / (1 + avg_gain / max(avg_loss, 0.0001)))

        return result

    def bollinger_bands(self, period=20, std=2) -> tuple[list, list, list]:
        """布林带"""
        ma = self.sma(period)
        result_upper = []
        result_lower = []
        for i in range(len(ma)):
            if i < period - 1:
                result_upper.append(0.0)
                result_lower.append(0.0)
            else:
                window = self._closes[i - period + 1:i + 1]
                avg = sum(window) / period
                variance = sum((x - avg) ** 2 for x in window) / period
                sigma = variance ** 0.5
                result_upper.append(avg + std * sigma)
                result_lower.append(avg - std * sigma)
        return result_upper, ma, result_lower

    def vol_ratio(self, period=5) -> list:
        """成交量比"""
        vol_ma = self.sma(period, self._volumes)
        return [
            v / max(m, 0.0001) for v, m in zip(self._volumes, vol_ma)
        ]

    def latest(self, indicator_list: list) -> float:
        """获取最新指标值"""
        return indicator_list[-1] if indicator_list else 0.0


class BaseStrategy(ABC):
    """策略基类"""

    author: str = "unknown"
    name: str = "base_strategy"

    # 可调参数
    max_position_pct: float = 0.1    # 单仓位上限
    stop_loss_pct: float = 5.0       # 止损百分比
    take_profit_pct: float = 10.0    # 止盈百分比
    requires_ai: bool = True         # 是否需要AI增强
    requires_confirmation: bool = True  # 是否需要人工确认

    def __init__(self):
        self.pos: int = 0            # 持仓数量 (正=多仓)
        self.avg_cost: float = 0.0   # 平均成本
        self.bars: list[BarData] = []
        self.am: Optional[IndicatorManager] = None
        self.signals: list[SignalData] = []

    def update_bar(self, bar: BarData):
        """更新K线数据并重新计算指标"""
        self.bars.append(bar)
        if len(self.bars) > 500:
            self.bars = self.bars[-500:]  # 保留最近500根K线
        self.am = IndicatorManager(self.bars)

    def generate_signal(self, action: Action, bar: BarData,
                        strength: float = 0.5,
                        reason: str = "") -> SignalData:
        """生成交易信号"""
        signal = SignalData(
            symbol=bar.symbol,
            action=action,
            strength=strength,
            price=bar.close,
            position_pct=self.max_position_pct,
            stop_loss=self._calc_stop_loss(bar.close, action),
            take_profit=self._calc_take_profit(bar.close, action),
            reason=reason,
            strategy_name=self.name,
            requires_confirmation=self.requires_confirmation,
        )
        self.signals.append(signal)
        return signal

    def _calc_stop_loss(self, entry_price: float, action: Action) -> float:
        """计算止损价"""
        if action == Action.BUY:
            return entry_price * (1 - self.stop_loss_pct / 100)
        else:
            return entry_price * (1 + self.stop_loss_pct / 100)

    def _calc_take_profit(self, entry_price: float, action: Action) -> float:
        """计算止盈价"""
        if action == Action.BUY:
            return entry_price * (1 + self.take_profit_pct / 100)
        else:
            return entry_price * (1 - self.take_profit_pct / 100)

    @abstractmethod
    def on_bar(self, bar: BarData) -> Optional[SignalData]:
        """K线触发 - 子类必须实现策略逻辑"""
        ...

    def on_init(self):
        """策略初始化钩子"""
        pass

    def ai_filter_signal(self, signal: SignalData) -> SignalData:
        """AI过滤信号钩子 - 子类可覆写"""
        return signal

    def ai_risk_override(self, bar: BarData) -> bool:
        """AI风险覆写钩子 - 返回True则阻止所有交易"""
        return False

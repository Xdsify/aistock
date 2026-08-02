"""示例策略实现"""
from typing import Optional
from .base import BaseStrategy, BarData, Action, SignalData


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略 - 经典趋势追踪"""

    name = "ma_cross"
    author = "system"
    requires_ai = True
    requires_confirmation = True

    # 参数
    fast_period: int = 5
    slow_period: int = 20
    max_position_pct: float = 0.15
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 12.0

    def on_bar(self, bar: BarData) -> Optional[SignalData]:
        if len(self.bars) < self.slow_period + 1:
            return None

        fast_ma = self.am.latest(self.am.sma(self.fast_period))
        slow_ma = self.am.latest(self.am.sma(self.slow_period))
        prev_fast = self.am.sma(self.fast_period)[-2]
        prev_slow = self.am.sma(self.slow_period)[-2]

        # 金叉买入
        if prev_fast <= prev_slow and fast_ma > slow_ma and self.pos == 0:
            strength = min(1.0, (fast_ma - slow_ma) / slow_ma * 20)
            volume_ratio = self.am.latest(self.am.vol_ratio(5))
            if volume_ratio > 1.2:  # 放量确认
                strength = min(1.0, strength * 1.3)
            return self.generate_signal(
                Action.BUY, bar, strength,
                f"MA金叉: MA{self.fast_period}({fast_ma:.2f})上穿MA{self.slow_period}({slow_ma:.2f})"
            )

        # 死叉卖出
        elif prev_fast >= prev_slow and fast_ma < slow_ma and self.pos > 0:
            return self.generate_signal(
                Action.SELL, bar, 0.8,
                f"MA死叉: MA{self.fast_period}({fast_ma:.2f})下穿MA{self.slow_period}({slow_ma:.2f})"
            )

        return None


class RSIStrategy(BaseStrategy):
    """RSI反转策略 - 超买超卖"""

    name = "rsi_reversal"
    author = "system"
    requires_ai = True

    # 参数
    rsi_period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    max_position_pct: float = 0.1
    stop_loss_pct: float = 4.0
    take_profit_pct: float = 8.0

    def on_bar(self, bar: BarData) -> Optional[SignalData]:
        if len(self.bars) < self.rsi_period + 2:
            return None

        rsi = self.am.rsi(self.rsi_period)
        rsi_now = self.am.latest(rsi)
        rsi_prev = rsi[-2]

        # 超卖反弹
        if rsi_prev < self.oversold and rsi_now >= self.oversold and self.pos == 0:
            strength = (self.oversold - rsi_now) / self.oversold
            return self.generate_signal(
                Action.BUY, bar, abs(strength),
                f"RSI超卖反弹: RSI({self.rsi_period})={rsi_now:.1f}"
            )

        # 超买回落
        if rsi_prev > self.overbought and rsi_now <= self.overbought and self.pos > 0:
            return self.generate_signal(
                Action.SELL, bar, 0.7,
                f"RSI超买回落: RSI({self.rsi_period})={rsi_now:.1f}"
            )

        return None


class VolumeBreakoutStrategy(BaseStrategy):
    """放量突破策略"""

    name = "volume_breakout"
    author = "system"
    requires_ai = True

    # 参数
    lookback: int = 20
    vol_multiple: float = 2.0
    max_position_pct: float = 0.12
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 15.0

    def on_bar(self, bar: BarData) -> Optional[SignalData]:
        if len(self.bars) < self.lookback + 2:
            return None

        # 成交量条件
        vol_ratio = self.am.latest(self.am.vol_ratio(self.lookback))
        if vol_ratio < self.vol_multiple:
            return None

        # 价格突破条件
        recent_high = max(b.high for b in self.bars[-self.lookback:-1])
        recent_low = min(b.low for b in self.bars[-self.lookback:-1])

        # 放量向上突破
        if bar.close > recent_high and self.pos == 0:
            strength = min(1.0, (bar.close - recent_high) / recent_high * 30)
            strength *= min(3.0, vol_ratio) / 3.0  # 量越大强度越高
            return self.generate_signal(
                Action.BUY, bar, strength,
                f"放量突破: 量比{vol_ratio:.1f}, 突破{self.lookback}日高点{recent_high:.2f}"
            )

        # 放量向下突破
        if bar.close < recent_low and self.pos > 0:
            return self.generate_signal(
                Action.SELL, bar, 0.9,
                f"放量下破: 跌破{self.lookback}日低点{recent_low:.2f}"
            )

        return None


class BollingerReversalStrategy(BaseStrategy):
    """布林带反转策略"""

    name = "bollinger_reversal"
    author = "system"
    requires_ai = False  # 简单策略不需要AI

    # 参数
    bb_period: int = 20
    bb_std: float = 2.0
    max_position_pct: float = 0.1
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 6.0

    def on_bar(self, bar: BarData) -> Optional[SignalData]:
        if len(self.bars) < self.bb_period + 1:
            return None

        upper, middle, lower = self.am.bollinger_bands(
            self.bb_period, self.bb_std
        )

        # 价格触及下轨反弹
        if bar.low <= self.am.latest(lower) and bar.close > self.am.latest(lower):
            if self.pos == 0:
                # 确认RSI不在极端超卖
                rsi = self.am.latest(self.am.rsi(14))
                if rsi < 40:
                    return self.generate_signal(
                        Action.BUY, bar, 0.7,
                        f"布林下轨反弹: 价格{bar.close:.2f}, 下轨{self.am.latest(lower):.2f}"
                    )

        # 价格触及上轨回落
        if bar.high >= self.am.latest(upper) and bar.close < self.am.latest(upper):
            if self.pos > 0:
                return self.generate_signal(
                    Action.SELL, bar, 0.6,
                    f"布林上轨回落: 价格{bar.close:.2f}, 上轨{self.am.latest(upper):.2f}"
                )

        return None


# 注册所有内置策略
BUILTIN_STRATEGIES = {
    "ma_cross": MACrossStrategy,
    "rsi_reversal": RSIStrategy,
    "volume_breakout": VolumeBreakoutStrategy,
    "bollinger_reversal": BollingerReversalStrategy,
}

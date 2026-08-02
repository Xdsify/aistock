"""
示例策略文件 - 用户自定义策略模板

将此文件复制并修改来创建你自己的策略
新策略只需实现 on_bar 方法即可
"""
import sys
sys.path.insert(0, '/app')

from src.strategies.base import BaseStrategy, BarData, Action, SignalData
from typing import Optional


class MyCustomStrategy(BaseStrategy):
    """我的自定义策略"""

    name = "my_custom"
    author = "your_name"
    requires_ai = True
    requires_confirmation = True

    # ===== 策略参数 (可在UI中调整) =====
    fast_ma = 5
    slow_ma = 20
    stop_loss_pct = 4.0
    take_profit_pct = 10.0
    max_position_pct = 0.12

    # ===== 策略逻辑 =====
    def on_bar(self, bar: BarData) -> Optional[SignalData]:
        """
        K线触发时调用此方法

        Args:
            bar: 当前K线数据

        Returns:
            交易信号，或 None (不操作)
        """

        # 确保有足够的历史数据
        if len(self.bars) < self.slow_ma + 1:
            return None

        # 计算指标
        fast_values = self.am.sma(self.fast_ma)
        slow_values = self.am.sma(self.slow_ma)

        fast_ma_now = self.am.latest(fast_values)
        slow_ma_now = self.am.latest(slow_values)
        fast_ma_prev = fast_values[-2]
        slow_ma_prev = slow_values[-2]

        # 获取成交量比作为确认
        vol_ratio = self.am.latest(self.am.vol_ratio(5))

        # === 买入条件: 金叉 + 放量确认 ===
        if (fast_ma_prev <= slow_ma_prev and
                fast_ma_now > slow_ma_now and
                self.pos == 0 and
                vol_ratio > 1.0):

            strength = min(1.0, (fast_ma_now - slow_ma_now) / slow_ma_now * 20)
            return self.generate_signal(
                Action.BUY, bar, strength,
                f"金叉买入: MA{self.fast_ma}={fast_ma_now:.2f} > MA{self.slow_ma}={slow_ma_now:.2f}"
            )

        # === 卖出条件: 死叉 ===
        elif (fast_ma_prev >= slow_ma_prev and
              fast_ma_now < slow_ma_now and
              self.pos > 0):

            return self.generate_signal(
                Action.SELL, bar, 0.8,
                f"死叉卖出: MA{self.fast_ma}={fast_ma_now:.2f} < MA{self.slow_ma}={slow_ma_now:.2f}"
            )

        # === 止损条件 ===
        if self.pos > 0 and self.avg_cost > 0:
            loss_pct = (bar.close - self.avg_cost) / self.avg_cost * 100
            if loss_pct < -self.stop_loss_pct:
                return self.generate_signal(
                    Action.SELL, bar, 1.0,
                    f"止损卖出: 亏损{loss_pct:.1f}% > {self.stop_loss_pct}%"
                )

        return None

"""执行引擎 Prometheus 指标"""
from prometheus_client import Counter, Gauge

orders_total = Counter("atrading_orders_total", "提交的订单数", ["action"])
pnl_daily = Gauge("atrading_pnl_daily", "当日盈亏(元)")
total_equity = Gauge("atrading_total_equity", "总资产(元)")
positions_value = Gauge("atrading_positions_value", "持仓市值(元)")

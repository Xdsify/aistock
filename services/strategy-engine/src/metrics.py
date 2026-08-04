"""策略引擎 Prometheus 指标"""
from prometheus_client import Counter

signals_total = Counter(
    "atrading_signals_total", "生成的交易信号数", ["action"]
)

"""AI服务 Prometheus 指标"""
from prometheus_client import Counter, Gauge

ai_calls = Counter("atrading_ai_calls_total", "AI API 调用次数")
ai_tokens = Counter("atrading_ai_tokens_total", "AI Token 消耗总量")
ai_cost = Gauge("atrading_ai_cost_daily", "当日 AI 估算费用(USD, 按0.2$/1M tokens粗算)")

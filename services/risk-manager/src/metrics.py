"""风控服务 Prometheus 指标"""
from prometheus_client import Counter

risk_checks_total = Counter("atrading_risk_checks_total", "风控检查次数")
risk_rejections_total = Counter("atrading_risk_rejections_total", "风控拒绝次数")

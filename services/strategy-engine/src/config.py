"""策略引擎配置"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://aistock:aistock@localhost:5432/aistock"
    redis_url: str = "redis://localhost:6379"

    # 下游服务地址 (docker 用服务名, 本地开发用 localhost)
    ai_service_url: str = "http://ai-service:8003/api/ai"
    risk_service_url: str = "http://risk-manager:8004/api/risk"

    # 策略配置
    default_commission_rate: float = 0.00025     # 默认佣金率 万2.5
    default_stamp_tax_rate: float = 0.001        # 印花税 千1 (仅卖出)
    default_slippage: float = 0.001              # 滑点 千1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

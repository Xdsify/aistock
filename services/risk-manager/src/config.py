"""风控管理器配置"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://aistock:aistock@localhost:5432/aistock"
    redis_url: str = "redis://localhost:6379"

    # 风控参数
    max_single_stock_pct: float = 0.20     # 单股最大仓位
    max_sector_pct: float = 0.40           # 单行业最大仓位
    daily_loss_limit_pct: float = 0.05     # 日亏损上限
    max_drawdown_pct: float = 0.08         # 最大回撤

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

"""数据服务配置"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://aistock:aistock@localhost:5432/aistock"
    redis_url: str = "redis://localhost:6379"
    tushare_token: str = ""

    # 数据更新配置
    daily_kline_update_hour: int = 16  # 收盘后更新日线 (16:00)
    realtime_poll_interval: int = 3     # 实时轮询间隔(秒)

    # AKShare重试配置
    max_retries: int = 3
    retry_delay: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

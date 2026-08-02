"""AI服务配置"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    redis_url: str = "redis://localhost:6379"
    database_url: str = "postgresql://aistock:aistock@localhost:5432/aistock"

    # AI模型配置
    default_model: str = "deepseek-chat"
    reasoner_model: str = "deepseek-reasoner"  # 用于复杂分析
    temperature: float = 0.3
    max_tokens: int = 2000

    # 成本控制
    daily_token_budget: int = 1_000_000
    max_requests_per_minute: int = 30
    ai_confidence_threshold: float = 0.6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

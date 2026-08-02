"""Redis客户端管理 - 共享连接池"""
import redis.asyncio as aioredis

redis_client: aioredis.Redis = None


async def init_redis(redis_url: str):
    """初始化Redis连接池"""
    global redis_client
    redis_client = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    await redis_client.ping()


async def close_redis():
    """关闭Redis连接"""
    global redis_client
    if redis_client:
        await redis_client.close()


async def get_redis() -> aioredis.Redis:
    """获取共享Redis客户端"""
    return redis_client

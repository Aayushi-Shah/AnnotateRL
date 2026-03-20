from redis.asyncio import Redis
from app.core.config import settings

_client: Redis | None = None


async def init_redis() -> None:
    global _client
    _client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await _client.ping()


async def close_redis() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def get_redis() -> Redis:
    if _client is None:
        raise RuntimeError("Redis not initialized")
    return _client

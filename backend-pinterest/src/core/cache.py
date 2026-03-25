from typing import Any
from redis.asyncio import Redis, RedisError

from src.core.logger import logger
from src.core.config import settings


class CacheService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str):
        try:
            value = await self.redis.get(key)
            if value is None:
                raise Exception()
            return value
        except RedisError as e:
            logger.error(f"Error getting key {key}: {e}")
            raise Exception(f"Error getting key for {key}")

    async def get_pattern(self, pattern: str):
        try:
            keys = await self.redis.keys(pattern)
            if not keys:
                raise Exception()
            values = await self.redis.mget(keys)
            return values
        except RedisError as e:
            logger.error(f"Error getting keys with pattern {pattern}: {e}")
            raise Exception(f"Error get keys with pattern {pattern}")

    async def set(self, key: str, value: Any, ttl: int = 3600):
        try:
            if not key:
                raise Exception()
            await self.redis.set(key, value, ex=ttl)
        except RedisError as e:
            logger.error(f"Error setting key {key}: {e}")
            raise Exception(f"Error set key {key}")

    async def delete(self, key: str):
        try:
            if not key:
                raise Exception()
            await self.redis.delete(key)
        except RedisError as e:
            logger.error(f"Error deleting key {key}: {e}")
            raise Exception(f"Error delete key {key}")

    async def delete_pattern(self, pattern: str):
        try:
            keys = await self.redis.keys(pattern)
            if not keys:
                raise Exception()
            await self.redis.delete(*keys)
        except RedisError as e:
            logger.error(f"Error deleting keys with pattern {pattern}: {e}")
            raise Exception(f"Error delete keys with pattern {pattern}")


async def get_cache_service() -> CacheService:
    redis = await Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=settings.redis_socket_timeout,
    )
    return CacheService(redis)

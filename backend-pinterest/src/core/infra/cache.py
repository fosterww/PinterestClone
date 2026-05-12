from typing import Any

from redis.asyncio import Redis, RedisError

from core.logger import logger


class CacheService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str):
        try:
            value = await self.redis.get(key)
            return value
        except RedisError as e:
            logger.error(f"Error getting key {key}: {e}")
            raise Exception(f"Error getting key for {key}")

    async def set(self, key: str, value: Any, ttl: int = 3600):
        try:
            if not key:
                raise Exception()
            await self.redis.set(key, value, ex=ttl)
        except RedisError as e:
            logger.error(f"Error setting key {key}: {e}")
            raise Exception(f"Error set key {key}")

    async def increment(self, key: str, amount: int = 1) -> int:
        try:
            if not key:
                raise Exception()
            return await self.redis.incrby(key, amount)
        except RedisError as e:
            logger.error(f"Error incrementing key {key}: {e}")
            raise Exception(f"Error increment key {key}")

    async def decrement(self, key: str, amount: int = 1) -> int:
        try:
            if not key:
                raise Exception()
            return await self.redis.decrby(key, amount)
        except RedisError as e:
            logger.error(f"Error decrementing key {key}: {e}")
            raise Exception(f"Error decrement key {key}")

    async def expire_at(self, key: str, when) -> None:
        try:
            if not key:
                raise Exception()
            await self.redis.expireat(key, when)
        except RedisError as e:
            logger.error(f"Error setting expire time for key {key}: {e}")
            raise Exception(f"Error expire key {key}")

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

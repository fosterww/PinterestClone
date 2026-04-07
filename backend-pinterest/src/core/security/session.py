import uuid

from redis.asyncio import Redis, RedisError
from core.logger import logger


class SessionService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def create_session(self, user_id: uuid.UUID):
        try:
            session_id = str(uuid.uuid4())
            await self.redis.set(f"session:{session_id}", str(user_id), ex=3600)
            return session_id
        except RedisError as e:
            logger.error(f"Error creating session for user {user_id}: {e}")
            raise Exception(f"Error creating session for user {user_id}")

    async def validate_session(self, session_id: str):
        try:
            user_id = await self.redis.get(f"session:{session_id}")
            if user_id is None:
                raise Exception()
            return user_id
        except RedisError as e:
            logger.error(f"Error validating session {session_id}: {e}")
            raise Exception(f"Error validating session for {session_id}")

    async def delete_session(self, session_id: str):
        try:
            await self.redis.delete(f"session:{session_id}")
        except RedisError as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            raise Exception(f"Error deleting session for {session_id}")

    async def refresh_session_ttl(self, session_id: str):
        try:
            await self.redis.expire(f"session:{session_id}", 3600)
        except RedisError as e:
            logger.error(f"Error refreshing session {session_id}: {e}")
            raise Exception(f"Error refreshing session for {session_id}")

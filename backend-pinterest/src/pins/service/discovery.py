import json
import uuid
from typing import List

from boards.models import PinModel
from core.infra.cache import CacheService
from core.logger import logger
from pins.repository.discover import DiscoverRepository
from pins.repository.pin import PinRepository
from pins.schemas import PinListResponse
from users.repository import UserRepository


class DiscoveryService:
    def __init__(
        self,
        pin_repo: PinRepository,
        discover_repo: DiscoverRepository,
        cache: CacheService,
        user_repo: UserRepository,
    ):
        self.pin_repo = pin_repo
        self.discover_repo = discover_repo
        self.cache = cache
        self.user_repo = user_repo

    async def _get_from_cache(self, pin_id: uuid.UUID) -> List[PinListResponse] | None:
        try:
            cache_key = f"related_pins:{pin_id}"
            payload = await self.cache.get(cache_key)
            if not payload:
                return None

            raw_items = json.loads(payload)
            return [PinListResponse.model_validate(item) for item in raw_items]
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    async def _set_to_cache(self, pin_id: uuid.UUID, pins: list[PinModel]) -> None:
        try:
            cache_key = f"related_pins:{pin_id}"
            payload = [
                PinListResponse.model_validate(pin).model_dump(mode="json")
                for pin in pins
            ]
            await self.cache.set(cache_key, json.dumps(payload), 600)
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    async def get_related_pins(
        self, pin_id: uuid.UUID, limit: int = 20
    ) -> List[PinModel]:
        cached_pins = await self._get_from_cache(pin_id)
        if cached_pins:
            return cached_pins
        base_pin = await self.pin_repo.get_pin_by_id(pin_id)
        if not base_pin or not self.pin_repo.is_trusted(base_pin) or not base_pin.tags:
            return []

        tag_ids = [tag.id for tag in base_pin.tags]
        related_pins = await self.discover_repo.get_related_by_tags(
            pin_id, tag_ids, limit
        )

        if related_pins:
            await self._set_to_cache(pin_id, related_pins)

        return related_pins

    async def record_tag_visit(
        self, user_id: uuid.UUID, tag_ids: list[uuid.UUID]
    ) -> None:
        try:
            key = f"user_interests:{user_id}"
            for tag_id in tag_ids:
                await self.cache.redis.lrem(key, 0, str(tag_id))
                await self.cache.redis.lpush(key, str(tag_id))
            await self.cache.redis.ltrim(key, 0, 49)
        except Exception as e:
            logger.error(f"Error recording tag visit for user {user_id}: {e}")

    async def get_personalized_feed(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> List[PinModel]:
        feed: list[PinModel] = []
        seen_pin_ids: list[uuid.UUID] = []

        followed_user_ids = await self.user_repo.get_followed_user_ids(user_id)
        if followed_user_ids:
            followed_pins = await self.discover_repo.get_following_feed(
                followed_user_ids, limit
            )
            feed.extend(followed_pins)
            seen_pin_ids.extend(pin.id for pin in followed_pins)
            if len(feed) >= limit:
                return feed

        key = f"user_interests:{user_id}"
        try:
            tag_id_strs = await self.cache.redis.lrange(key, 0, -1)
            tag_ids = []
            for tid in tag_id_strs:
                try:
                    tid_str = tid.decode("utf-8") if isinstance(tid, bytes) else tid
                    tag_ids.append(uuid.UUID(tid_str))
                except ValueError:
                    continue
        except Exception as e:
            logger.warning(f"Error getting interests for user {user_id}: {e}")
            tag_ids = []

        remaining = limit - len(feed)
        if remaining > 0:
            personalized_pins = await self.discover_repo.get_personalized_feed(
                tag_ids,
                remaining,
                exclude_pin_ids=seen_pin_ids,
            )
            feed.extend(personalized_pins)
            seen_pin_ids.extend(pin.id for pin in personalized_pins)

        remaining = limit - len(feed)
        if remaining > 0:
            latest_pins = await self.discover_repo.get_latest_pins(
                remaining,
                exclude_pin_ids=seen_pin_ids,
            )
            feed.extend(latest_pins)

        return feed

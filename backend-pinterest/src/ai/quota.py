import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from ai.models import AIOperationType
from core.config import settings
from core.exception import AppError
from core.infra.cache import CacheService


@dataclass(frozen=True)
class QuotaMetadata:
    operation_type: AIOperationType
    limit: int
    used: int
    remaining: int
    resets_at: datetime


class AIQuotaExceededError(AppError):
    def __init__(self, metadata: QuotaMetadata):
        super().__init__(
            status_code=429,
            detail={
                "message": "AI quota exceeded",
                "quota": quota_metadata_to_dict(metadata),
            },
        )


def quota_metadata_to_dict(metadata: QuotaMetadata) -> dict:
    return {
        "operation_type": metadata.operation_type.value,
        "limit": metadata.limit,
        "used": metadata.used,
        "remaining": metadata.remaining,
        "resets_at": metadata.resets_at.isoformat(),
    }


def daily_limits() -> dict[AIOperationType, int]:
    return {
        AIOperationType.IMAGE_GENERATION: settings.ai_image_generations_per_day,
        AIOperationType.TAG_GENERATION: settings.ai_tag_generations_per_day,
        AIOperationType.RETRIES: settings.ai_retries_per_day,
        AIOperationType.DESCRIPTION_GENERATION: (
            settings.ai_description_generations_per_day
        ),
        AIOperationType.IMAGE_INDEXING: settings.ai_image_indexings_per_day,
        AIOperationType.VISUAL_SEARCH: settings.ai_visual_searches_per_day,
    }


def operation_unit_cost(operation_type: AIOperationType) -> Decimal:
    if operation_type == AIOperationType.IMAGE_GENERATION:
        return Decimal(settings.ai_openai_image_generation_cost_usd)
    return Decimal("0.000000")


class QuotaService:
    def __init__(self, cache_service: CacheService):
        self.cache = cache_service

    async def check_and_reserve(
        self, user_id: uuid.UUID, operation_type: AIOperationType
    ) -> QuotaMetadata:
        limit = self._limit_for(operation_type)
        key = self._key(user_id, operation_type)
        used = await self.cache.increment(key)
        resets_at = self._next_reset_at()

        if used == 1:
            await self.cache.expire_at(key, resets_at)

        if used > limit:
            await self.cache.decrement(key)
            metadata = self._metadata(operation_type, limit, limit, resets_at)
            raise AIQuotaExceededError(metadata)

        return self._metadata(operation_type, limit, used, resets_at)

    async def rollback(
        self, user_id: uuid.UUID, operation_type: AIOperationType
    ) -> QuotaMetadata:
        limit = self._limit_for(operation_type)
        key = self._key(user_id, operation_type)
        used = max(await self.cache.decrement(key), 0)
        if used == 0:
            await self.cache.delete(key)
        return self._metadata(operation_type, limit, used, self._next_reset_at())

    async def get_metadata(
        self, user_id: uuid.UUID, operation_type: AIOperationType
    ) -> QuotaMetadata:
        limit = self._limit_for(operation_type)
        raw_used = await self.cache.get(self._key(user_id, operation_type))
        used = self._parse_count(raw_used)
        return self._metadata(operation_type, limit, used, self._next_reset_at())

    def _limit_for(self, operation_type: AIOperationType) -> int:
        return daily_limits()[operation_type]

    def _key(self, user_id: uuid.UUID, operation_type: AIOperationType) -> str:
        today = datetime.now(UTC).date().isoformat()
        return f"ai:usage:{user_id}:{today}:{operation_type.value}"

    def _next_reset_at(self) -> datetime:
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        return datetime.combine(tomorrow, time.min, tzinfo=UTC)

    def _metadata(
        self,
        operation_type: AIOperationType,
        limit: int,
        used: int,
        resets_at: datetime,
    ) -> QuotaMetadata:
        used = min(max(used, 0), limit)
        return QuotaMetadata(
            operation_type=operation_type,
            limit=limit,
            used=used,
            remaining=max(limit - used, 0),
            resets_at=resets_at,
        )

    def _parse_count(self, raw_value) -> int:
        if raw_value is None:
            return 0
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode()
        return int(raw_value)

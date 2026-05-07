import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai.models import AIOperationModel, AIOperationType, AIProvider, AIStatus


async def record_ai_operation(
    db: AsyncSession,
    *,
    provider: AIProvider,
    model: str,
    operation_type: AIOperationType,
    status: AIStatus,
    prompt_version: str | None = None,
    input_parameters: Mapping[str, Any] | None = None,
    latency_ms: int | None = None,
    error_message: str | None = None,
    user_id: uuid.UUID | None = None,
    related_pin_id: uuid.UUID | None = None,
    generated_pin_id: uuid.UUID | None = None,
) -> AIOperationModel:
    operation = AIOperationModel(
        user_id=user_id,
        related_pin_id=related_pin_id,
        generated_pin_id=generated_pin_id,
        provider=provider,
        model=model,
        operation_type=operation_type,
        prompt_version=prompt_version,
        input_parameters=dict(input_parameters or {}),
        status=status,
        latency_ms=latency_ms,
        error_message=_truncate_error(error_message),
    )
    db.add(operation)
    await db.flush()
    return operation


def _truncate_error(error_message: str | None) -> str | None:
    if not error_message:
        return None
    return error_message[:1000]

import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ai.repository import AIRepository
from ai.schemas import GenerateImageRequest, GenerateImageResponse, AIOperationOutput
from ai.service import OpenAIService
from core.dependencies import get_ai_service
from core.exception import NotFoundError
from core.security.auth import get_current_user
from core.security.limiter import limiter
from database import get_db
from users.models import UserModel

router = APIRouter()


@router.post("/generate-image", response_model=GenerateImageResponse)
@limiter.limit("1/minute")
async def generate_image(
    request: Request,
    data: GenerateImageRequest,
    current_user: UserModel = Depends(get_current_user),
    service: OpenAIService = Depends(get_ai_service),
) -> GenerateImageResponse:
    return await service.generate_image(data, current_user)


@router.get("/operations/{operation_id}", response_model=AIOperationOutput)
@limiter.limit("5/minute")
async def get_operation(
    request: Request,
    operation_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIOperationOutput:
    operation = await AIRepository(db).get_operation_by_id(operation_id, current_user)
    if operation is None:
        raise NotFoundError("AI operation not found")
    return AIOperationOutput.from_operation(operation)

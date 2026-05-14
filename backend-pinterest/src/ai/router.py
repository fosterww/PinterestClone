import uuid
from fastapi import APIRouter, Depends, Request

from ai.schemas import GenerateImageRequest, GenerateImageResponse, AIOperationOutput
from ai.service import OpenAIService
from core.dependencies import get_ai_service
from core.security.auth import get_current_user
from core.security.limiter import limiter
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
    """Generate image using AI."""
    return await service.generate_image(data, current_user)


@router.get("/operations/{operation_id}", response_model=AIOperationOutput)
@limiter.limit("5/minute")
async def get_operation(
    request: Request,
    operation_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: OpenAIService = Depends(get_ai_service),
) -> AIOperationOutput:
    """Get AI operation by id."""
    return await service.get_operation_by_id(operation_id, current_user)

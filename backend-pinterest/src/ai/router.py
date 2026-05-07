from fastapi import APIRouter, Depends, Request

from ai.schemas import GenerateImageRequest, GenerateImageResponse
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
    return await service.generate_image(data, current_user)

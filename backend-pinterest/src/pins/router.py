import uuid
import base64
from typing import Annotated, Optional, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    UploadFile,
    File,
    Form,
    Request,
)
from src.core.limiter import limiter
from src.core.s3 import S3Service
from src.core.clarifai import ClarifaiService
from src.core.dependencies import (
    get_pin_repository,
    get_pin_service,
    get_s3_service,
    get_clarifai_service,
)
from src.core.auth import get_current_user
from src.users.models import UserModel
from src.pins.schemas import PinCreate, PinUpdate, PinResponse, Pagination, FilterPins

from src.pins.repository import PinRepository
from src.pins.service import PinService
from src.pins.task import index_image_task, delete_image_task


router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_new_pin(
    request: Request,
    s3_service: S3Service = Depends(get_s3_service),
    image: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    tags: Annotated[list[str], Form()] = [],
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinResponse:
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if image.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {image.content_type}",
        )

    content = await image.read()
    await image.seek(0)

    image_url = await s3_service.upload_image_to_s3(image)
    data = PinCreate(title=title, description=description, link_url=link_url, tags=tags)
    pin = await service.create_pin(current_user, data, image_url=image_url)

    base64_image = base64.b64encode(content).decode("utf-8")
    index_image_task.delay(str(pin.id), base64_image)
    return pin


@router.get("/")
@limiter.limit("10/minute")
async def list_pins(
    request: Request,
    tags: Annotated[list[str], Query()] = [],
    pagination: Pagination = Depends(),
    filter_pins: FilterPins = Depends(),
    repo: PinRepository = Depends(get_pin_repository),
) -> list[PinResponse]:
    return await repo.get_pins(
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        tags=tags,
        created_at=filter_pins.created_at,
        popularity=filter_pins.popularity,
    )


@router.get("/{pin_id}")
@limiter.limit("10/minute")
async def read_pin(
    request: Request,
    pin_id: uuid.UUID,
    repo: PinRepository = Depends(get_pin_repository),
) -> PinResponse:
    pin = await repo.get_pin_by_id(pin_id)
    if pin is None:
        raise HTTPException(status_code=404, detail="Pin not found")
    return PinResponse.model_validate(pin)


@router.get("/user/{username}")
@limiter.limit("10/minute")
async def read_user_pins(
    request: Request,
    username: str,
    repo: PinRepository = Depends(get_pin_repository),
) -> List[PinResponse]:
    return await repo.get_user_pins(username)


@router.post("/{pin_id}/like")
@limiter.limit("5/minute")
async def like_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinResponse:
    return await service.like_pin(pin_id, current_user.id)


@router.post("/{pin_id}/unlike")
@limiter.limit("5/minute")
async def unlike_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinResponse:
    return await service.unlike_pin(pin_id, current_user.id)


@router.patch("/{pin_id}")
@limiter.limit("5/minute")
async def patch_pin(
    request: Request,
    pin_id: uuid.UUID,
    data: PinUpdate,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
    repo: PinRepository = Depends(get_pin_repository),
) -> PinResponse:
    pin = await repo.get_pin_by_id(pin_id)
    return await service.update_pin(pin, data, current_user)


@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def remove_pin(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
    repo: PinRepository = Depends(get_pin_repository),
):
    pin = await repo.get_pin_by_id(pin_id)
    await service.delete_pin(pin, current_user)

    delete_image_task.delay(str(pin_id))


@router.get("/{pin_id}/related")
@limiter.limit("5/minute")
async def get_related_pins(
    request: Request,
    pin_id: uuid.UUID,
    clarifai_service: ClarifaiService = Depends(get_clarifai_service),
    service: PinService = Depends(get_pin_service),
    repo: PinRepository = Depends(get_pin_repository),
) -> list[PinResponse]:
    similar_ids = await clarifai_service.search_similar_images_by_id(str(pin_id))
    db_related_pins = await service.get_related_pins(pin_id, limit=20)
    clarifai_pins = await repo.get_pins_by_ids(similar_ids)

    seen_ids = set()
    merged_pins = []

    clarifai_dict = {p.id: p for p in clarifai_pins}

    for cid in similar_ids:
        try:
            c_uuid = uuid.UUID(cid)
            if c_uuid in clarifai_dict and c_uuid not in seen_ids:
                merged_pins.append(clarifai_dict[c_uuid])
                seen_ids.add(c_uuid)
        except ValueError:
            pass

    for db_pin in db_related_pins:
        if db_pin.id not in seen_ids:
            merged_pins.append(db_pin)
            seen_ids.add(db_pin.id)

    return merged_pins

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
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.limiter import limiter
from src.core.s3 import get_s3_service, S3Service
from src.core.clarifai import get_clarifai_service, ClarifaiService
from src.core.cache import get_cache_service, CacheService
from src.database import get_db
from src.core.auth import get_current_user
from src.users.models import UserModel
from src.pins.schemas import PinCreate, PinUpdate, PinResponse, Pagination, FilterPins
from src.pins.service import (
    create_pin,
    get_pins,
    get_pin_by_id,
    update_pin,
    delete_pin,
    get_related_pins_from_db,
    get_pins_by_ids,
    get_user_pins,
    like_pin,
    unlike_pin,
)
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
    db: AsyncSession = Depends(get_db),
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
    pin = await create_pin(db, current_user, data, image_url=image_url)

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
    db: AsyncSession = Depends(get_db),
) -> list[PinResponse]:
    return await get_pins(
        db,
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
    request: Request, pin_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> PinResponse:
    return await get_pin_by_id(db, pin_id)


@router.get("/user/{username}")
@limiter.limit("10/minute")
async def read_user_pins(
    request: Request,
    username: str,
    db: AsyncSession = Depends(get_db),
) -> List[PinResponse]:
    return await get_user_pins(username, db)


@router.post("/{pin_id}/like")
@limiter.limit("5/minute")
async def like_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinResponse:
    return await like_pin(db, pin_id, current_user.id)


@router.post("/{pin_id}/unlike")
@limiter.limit("5/minute")
async def unlike_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinResponse:
    return await unlike_pin(db, pin_id, current_user.id)


@router.patch("/{pin_id}")
@limiter.limit("5/minute")
async def patch_pin(
    request: Request,
    pin_id: uuid.UUID,
    data: PinUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinResponse:
    pin = await get_pin_by_id(db, pin_id)
    return await update_pin(db, pin, data, current_user)


@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def remove_pin(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pin = await get_pin_by_id(db, pin_id)
    await delete_pin(db, pin, current_user)

    delete_image_task.delay(str(pin_id))


@router.get("/{pin_id}/related")
@limiter.limit("5/minute")
async def get_related_pins(
    request: Request,
    pin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    clarifai_service: ClarifaiService = Depends(get_clarifai_service),
    cache_service: CacheService = Depends(get_cache_service),
) -> list[PinResponse]:
    similar_ids = await clarifai_service.search_similar_images_by_id(str(pin_id))
    db_related_pins = await get_related_pins_from_db(
        db, pin_id, limit=20, cache_service=cache_service
    )
    clarifai_pins = await get_pins_by_ids(db, similar_ids)

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

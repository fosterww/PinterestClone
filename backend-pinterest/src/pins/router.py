import uuid
from typing import Annotated, Optional, List

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
    UploadFile,
    File,
    Form,
    Request,
)
from src.core.security.limiter import limiter
from src.core.infra.clarifai import ClarifaiService
from src.core.dependencies import (
    get_pin_repository,
    get_pin_service,
)
from src.core.infra.clarifai import get_clarifai_service
from src.core.security.auth import get_current_user
from src.users.models import UserModel
from src.pins.schemas import (
    PinCreate,
    PinUpdate,
    PinResponse,
    PinListResponse,
    Pagination,
    FilterPins,
    PinCommentCreate,
    PinCommentResponse,
)

from src.pins.repository import PinRepository
from src.pins.service import PinService
from src.pins.task import delete_image_task


router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_new_pin(
    request: Request,
    image: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    tags: Annotated[list[str], Form()] = [],
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinListResponse:
    data = PinCreate(title=title, description=description, link_url=link_url, tags=tags)
    return await service.create_pin(image, current_user, data)


@router.get("/")
@limiter.limit("10/minute")
async def list_pins(
    request: Request,
    tags: Annotated[list[str], Query()] = [],
    pagination: Pagination = Depends(),
    filter_pins: FilterPins = Depends(),
    repo: PinRepository = Depends(get_pin_repository),
) -> List[PinListResponse]:
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
    service: PinService = Depends(get_pin_service),
) -> PinResponse:
    return await service.get_pin_detail(pin_id)


@router.get("/user/{username}")
@limiter.limit("10/minute")
async def read_user_pins(
    request: Request,
    username: str,
    repo: PinRepository = Depends(get_pin_repository),
) -> List[PinListResponse]:
    return await repo.get_user_pins(username)


@router.post("/{pin_id}/like")
@limiter.limit("5/minute")
async def like_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinListResponse:
    return await service.like_pin(pin_id, current_user.id)


@router.post("/{pin_id}/unlike")
@limiter.limit("5/minute")
async def unlike_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinListResponse:
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
) -> PinListResponse:
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


@router.get("/{pin_id}/comments")
@limiter.limit("5/minute")
async def get_comments(
    request: Request,
    pin_id: uuid.UUID,
    service: PinService = Depends(get_pin_service),
) -> List[PinCommentResponse]:
    return await service.get_comments(pin_id)


@router.post("/{pin_id}/comments")
@limiter.limit("5/minute")
async def add_comment(
    request: Request,
    pin_id: uuid.UUID,
    data: PinCommentCreate,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinCommentResponse:
    return await service.add_comment(
        pin_id, data.parent_id, current_user.id, data.comment
    )


@router.post("/{pin_id}/comments/{comment_id}/like")
@limiter.limit("5/minute")
async def like_comment(
    request: Request,
    pin_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinCommentResponse:
    return await service.add_comment_like(pin_id, comment_id, current_user.id)


@router.post("/{pin_id}/comments/{comment_id}/unlike")
@limiter.limit("5/minute")
async def unlike_comment(
    request: Request,
    pin_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinCommentResponse:
    return await service.delete_comment_like(pin_id, comment_id, current_user.id)


@router.patch("/{pin_id}/comments/{comment_id}")
@limiter.limit("5/minute")
async def patch_comment(
    request: Request,
    comment_id: uuid.UUID,
    text: str = Form(...),
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinCommentResponse:
    return await service.update_comment(comment_id, current_user.id, text)


@router.delete(
    "/{pin_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("5/minute")
async def remove_comment(
    request: Request,
    pin_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> None:
    await service.delete_comment(pin_id, comment_id, current_user)


@router.get("/{pin_id}/related")
@limiter.limit("5/minute")
async def get_related_pins(
    request: Request,
    pin_id: uuid.UUID,
    clarifai_service: ClarifaiService = Depends(get_clarifai_service),
    service: PinService = Depends(get_pin_service),
    repo: PinRepository = Depends(get_pin_repository),
) -> List[PinListResponse]:
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

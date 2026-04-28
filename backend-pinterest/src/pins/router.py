import uuid
from typing import Optional, List

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

from core.security.limiter import limiter
from core.infra.clarifai import ClarifaiService, get_clarifai_service
from core.dependencies import (
    get_pin_repository,
    get_pin_service,
    get_comment_service,
    get_discovery_service,
)
from core.security.auth import get_current_user
from users.models import UserModel
from pins.schemas import (
    PinCreate,
    PinUpdate,
    PinResponse,
    PinListResponse,
    Pagination,
    FilterPins,
    PinCommentCreate,
    PinCommentResponse,
)

from pins.repository.pin import PinRepository
from pins.service.pin import PinService
from pins.service.comment import CommentService
from pins.service.discovery import DiscoveryService
from pins.task import delete_image_task


router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_new_pin(
    request: Request,
    image: UploadFile | None = File(None),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    generate_ai_description: bool = Form(False),
    generated_pin_id: uuid.UUID | None = Form(None),
    tags: list[str] = Form(default_factory=list),
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinListResponse:
    """Create a new pin."""
    data = PinCreate(
        title=title,
        description=description,
        link_url=link_url,
        tags=tags,
        generate_ai_description=generate_ai_description,
        generated_pin_id=generated_pin_id,
    )
    return await service.create_pin(image, current_user, data)


@router.get("/")
@limiter.limit("10/minute")
async def list_pins(
    request: Request,
    tags: list[str] = Query(default_factory=list),
    pagination: Pagination = Depends(),
    filter_pins: FilterPins = Depends(),
    service: PinService = Depends(get_pin_service),
) -> List[PinListResponse]:
    """Get all pins with optional filtering and pagination."""
    return await service.get_pins(
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        tags=tags,
        created_at=filter_pins.created_at,
        popularity=filter_pins.popularity,
    )


@router.get("/personalized")
@limiter.limit("10/minute")
async def read_personalized_pins(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
) -> List[PinListResponse]:
    """Get personalized feed."""
    return await discovery_service.get_personalized_feed(current_user.id)


@router.get("/{pin_id}")
@limiter.limit("10/minute")
async def read_pin(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    pin_service: PinService = Depends(get_pin_service),
    comment_service: CommentService = Depends(get_comment_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
) -> PinResponse:
    """Get pin detail by id, including comments and recommendation tracking."""
    pin = await pin_service.get_pin_by_id_and_increment_views(pin_id)
    if pin.tags:
        tag_ids = [tag.id for tag in pin.tags]
        await discovery_service.record_tag_visit(current_user.id, tag_ids)
    comments = await comment_service.get_comments(pin_id)
    pin_data = PinListResponse.model_validate(pin)
    return PinResponse(**pin_data.model_dump(), comments=comments)


@router.get("/user/{username}")
@limiter.limit("10/minute")
async def read_user_pins(
    request: Request,
    username: str,
    repo: PinRepository = Depends(get_pin_repository),
) -> List[PinListResponse]:
    """Get all pins by username."""
    return await repo.get_user_pins(username)


@router.post("/{pin_id}/like")
@limiter.limit("5/minute")
async def like_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinListResponse:
    """Like a pin."""
    return await service.like_pin(pin_id, current_user.id)


@router.post("/{pin_id}/unlike")
@limiter.limit("5/minute")
async def unlike_pin_handler(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinListResponse:
    """Unlike a pin."""
    return await service.unlike_pin(pin_id, current_user.id)


@router.patch("/{pin_id}")
@limiter.limit("5/minute")
async def patch_pin(
    request: Request,
    pin_id: uuid.UUID,
    data: PinUpdate,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
) -> PinListResponse:
    """Update a pin."""
    pin = await service.get_pin_by_id(pin_id)
    return await service.update_pin(pin, data, current_user)


@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def remove_pin(
    request: Request,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    service: PinService = Depends(get_pin_service),
):
    """Delete a pin."""
    pin = await service.get_pin_by_id(pin_id)
    await service.delete_pin(pin, current_user)
    delete_image_task.delay(str(pin_id))


@router.get("/{pin_id}/comments")
@limiter.limit("5/minute")
async def get_comments(
    request: Request,
    pin_id: uuid.UUID,
    comment_service: CommentService = Depends(get_comment_service),
) -> List[PinCommentResponse]:
    """Get comments for a pin."""
    return await comment_service.get_comments(pin_id)


@router.post("/{pin_id}/comments")
@limiter.limit("5/minute")
async def add_comment(
    request: Request,
    pin_id: uuid.UUID,
    data: PinCommentCreate,
    current_user: UserModel = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> PinCommentResponse:
    """Add a comment to a pin."""
    return await comment_service.add_comment(
        pin_id, data.parent_id, current_user.id, data.comment
    )


@router.post("/{pin_id}/comments/{comment_id}/like")
@limiter.limit("5/minute")
async def like_comment(
    request: Request,
    pin_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> PinCommentResponse:
    """Like a comment."""
    return await comment_service.add_comment_like(pin_id, comment_id, current_user.id)


@router.post("/{pin_id}/comments/{comment_id}/unlike")
@limiter.limit("5/minute")
async def unlike_comment(
    request: Request,
    pin_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> PinCommentResponse:
    """Unlike a comment."""
    return await comment_service.delete_comment_like(
        pin_id, comment_id, current_user.id
    )


@router.patch("/{pin_id}/comments/{comment_id}")
@limiter.limit("5/minute")
async def patch_comment(
    request: Request,
    comment_id: uuid.UUID,
    text: str = Form(...),
    current_user: UserModel = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> PinCommentResponse:
    """Update a comment."""
    return await comment_service.update_comment(comment_id, current_user.id, text)


@router.delete(
    "/{pin_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("5/minute")
async def remove_comment(
    request: Request,
    pin_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> None:
    """Delete a comment."""
    await comment_service.delete_comment(pin_id, comment_id, current_user)


@router.get("/{pin_id}/related")
@limiter.limit("5/minute")
async def get_related_pins(
    request: Request,
    pin_id: uuid.UUID,
    clarifai_service: ClarifaiService = Depends(get_clarifai_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    pin_repo: PinRepository = Depends(get_pin_repository),
) -> List[PinListResponse]:
    """Get related pins combining Clarifai visual search and Tag-based discovery."""
    similar_ids = await clarifai_service.search_similar_images_by_id(str(pin_id))
    db_related_pins = await discovery_service.get_related_pins(pin_id, limit=20)
    clarifai_pins = await pin_repo.get_pins_by_ids(similar_ids)

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

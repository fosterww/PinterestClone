from fastapi import APIRouter, Depends, Query, Request

from core.dependencies import get_search_service
from core.security.auth import get_optional_current_user
from core.security.limiter import limiter
from search.schemas import SearchResponse, SearchTarget
from search.service import SearchService
from users.models import UserModel

router = APIRouter()


@router.get("/")
@limiter.limit("10/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=1),
    target: SearchTarget = SearchTarget.all,
    limit: int = Query(default=10, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel | None = Depends(get_optional_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Search across users, boards, and pins with an optional target filter."""
    current_user_id = current_user.id if current_user is not None else None
    return await search_service.search(q, target, limit, offset, current_user_id)

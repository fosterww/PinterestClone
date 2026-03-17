import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.s3 import upload_image_to_s3
from src.database import get_db
from src.core.auth import get_current_user
from src.users.models import UserModel
from src.pins.schemas import PinCreate, PinUpdate, PinResponse
from src.pins.service import (
    create_pin,
    get_pins,
    get_pin_by_id,
    update_pin,
    delete_pin,
)

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_new_pin(
    title: str = Form(...),
    description: str | None = Form(None),
    link_url: str | None = Form(None),
    image: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinResponse:
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if image.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {image.content_type}",
        )
    
    image_url = await upload_image_to_s3(image)

    data = PinCreate(title=title, description=description, link_url=link_url)
    pin = await create_pin(db, current_user, data, image_url=image_url)
    return pin


@router.get("/")
async def list_pins(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[PinResponse]:
    return await get_pins(db, offset, limit)


@router.get("/{pin_id}")
async def read_pin(pin_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PinResponse:
    return await get_pin_by_id(db, pin_id)


@router.patch("/{pin_id}")
async def patch_pin(
    pin_id: uuid.UUID,
    data: PinUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinResponse:
    pin = await get_pin_by_id(db, pin_id)
    return await update_pin(db, pin, data, current_user)


@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_pin(
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pin = await get_pin_by_id(db, pin_id)
    await delete_pin(db, pin, current_user)

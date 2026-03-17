import pytest
import pytest_asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.auth.service import register_user
from src.users.schemas import UserCreate
from src.pins.schemas import PinCreate, PinUpdate
from src.pins.service import create_pin, get_pins, get_pin_by_id, update_pin, delete_pin

@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession):
    user_data = UserCreate(
        username="pin_svc_tester",
        email="pin_svc@example.com",
        password="securepassword"
    )
    return await register_user(db_session, user_data)

@pytest_asyncio.fixture
async def another_user(db_session: AsyncSession):
    user_data = UserCreate(
        username="pin_svc_other",
        email="pin_svc_other@example.com",
        password="securepassword"
    )
    return await register_user(db_session, user_data)

@pytest.mark.asyncio
async def test_create_and_get_pin(db_session: AsyncSession, sample_user):
    pin_data = PinCreate(
        title="Test Pin",
        description="A beautiful test pin",
        link_url="https://example.com"
    )
    image_url = "https://example.com/image.jpg"

    created_pin = await create_pin(db_session, sample_user, pin_data, image_url)
    assert created_pin is not None
    assert created_pin.title == "Test Pin"
    assert created_pin.image_url == image_url
    assert created_pin.owner_id == sample_user.id

    fetched_pin = await get_pin_by_id(db_session, created_pin.id)
    assert fetched_pin is not None
    assert fetched_pin.id == created_pin.id
    assert fetched_pin.title == "Test Pin"

@pytest.mark.asyncio
async def test_get_pins_pagination(db_session: AsyncSession, sample_user):
    image_url = "https://example.com/image.jpg"

    for i in range(5):
        pin_data = PinCreate(title=f"Pin {i}")
        await create_pin(db_session, sample_user, pin_data, image_url)
        
    pins_page_1 = await get_pins(db_session, offset=0, limit=3)
    assert len(pins_page_1) == 3
    
    pins_page_2 = await get_pins(db_session, offset=3, limit=3)
    assert len(pins_page_2) == 2

@pytest.mark.asyncio
async def test_update_pin_success_and_forbidden(db_session: AsyncSession, sample_user, another_user):
    pin_data = PinCreate(title="Original Title")
    image_url = "https://example.com/image.jpg"
    created_pin = await create_pin(db_session, sample_user, pin_data, image_url)

    update_data = PinUpdate(title="Updated Title")
    updated_pin = await update_pin(db_session, created_pin, update_data, sample_user)
    assert updated_pin.title == "Updated Title"

    with pytest.raises(HTTPException) as excinfo:
        await update_pin(db_session, created_pin, update_data, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the pin owner"

@pytest.mark.asyncio
async def test_delete_pin_success_and_forbidden(db_session: AsyncSession, sample_user, another_user):
    pin_data = PinCreate(title="To be deleted")
    image_url = "https://example.com/image.jpg"
    created_pin = await create_pin(db_session, sample_user, pin_data, image_url)
    
    with pytest.raises(HTTPException) as excinfo:
        await delete_pin(db_session, created_pin, another_user)
    assert excinfo.value.status_code == 403
    
    await delete_pin(db_session, created_pin, sample_user)
    
    with pytest.raises(HTTPException) as excinfo:
        await get_pin_by_id(db_session, created_pin.id)
    assert excinfo.value.status_code == 404

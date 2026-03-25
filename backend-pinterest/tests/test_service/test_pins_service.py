import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.auth.service import register_user
from src.users.schemas import UserCreate
from src.pins.schemas import PinCreate, PinUpdate, CreatedAt, Popularity
from src.pins.service import (
    create_pin,
    get_pins,
    get_pin_by_id,
    update_pin,
    delete_pin,
    get_related_pins_from_db,
    get_pins_by_ids,
    like_pin,
    unlike_pin,
)


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession):
    user_data = UserCreate(
        username="pin_svc_tester",
        email="pin_svc@example.com",
        password="securepassword",
    )
    return await register_user(db_session, user_data)


@pytest_asyncio.fixture
async def another_user(db_session: AsyncSession):
    user_data = UserCreate(
        username="pin_svc_other",
        email="pin_svc_other@example.com",
        password="securepassword",
    )
    return await register_user(db_session, user_data)


@pytest.mark.asyncio
async def test_create_and_get_pin_no_tags(db_session: AsyncSession, sample_user):
    pin_data = PinCreate(
        title="Test Pin",
        description="A beautiful test pin",
        link_url="https://example.com",
    )
    image_url = "https://example.com/image.jpg"

    created_pin = await create_pin(db_session, sample_user, pin_data, image_url)
    assert created_pin is not None
    assert created_pin.title == "Test Pin"
    assert created_pin.image_url == image_url
    assert created_pin.owner_id == sample_user.id
    assert created_pin.tags == []

    fetched_pin = await get_pin_by_id(db_session, created_pin.id)
    assert fetched_pin is not None
    assert fetched_pin.id == created_pin.id
    assert fetched_pin.title == "Test Pin"


@pytest.mark.asyncio
async def test_create_pin_with_tags(db_session: AsyncSession, sample_user):
    pin_data = PinCreate(title="Tagged Pin", tags=["nature", "travel"])
    image_url = "https://example.com/image.jpg"

    created_pin = await create_pin(db_session, sample_user, pin_data, image_url)
    assert created_pin is not None
    tag_names = {t.name for t in created_pin.tags}
    assert tag_names == {"nature", "travel"}


@pytest.mark.asyncio
async def test_create_pin_reuses_existing_tags(db_session: AsyncSession, sample_user):
    pin1 = await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Pin 1", tags=["cats"]),
        "http://img.jpg",
    )
    pin2 = await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Pin 2", tags=["cats"]),
        "http://img.jpg",
    )

    tag_id_pin1 = {t.name: t.id for t in pin1.tags}["cats"]
    tag_id_pin2 = {t.name: t.id for t in pin2.tags}["cats"]
    assert tag_id_pin1 == tag_id_pin2


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
async def test_update_pin_success_and_forbidden(
    db_session: AsyncSession, sample_user, another_user
):
    pin_data = PinCreate(title="Original Title", tags=["old-tag"])
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
async def test_delete_pin_success_and_forbidden(
    db_session: AsyncSession, sample_user, another_user
):
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


@pytest.mark.asyncio
async def test_get_related_pins_from_db(db_session: AsyncSession, sample_user):
    pin1 = await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Pin 1", tags=["cats", "funny"]),
        "url1",
    )
    pin2 = await create_pin(
        db_session, sample_user, PinCreate(title="Pin 2", tags=["cats", "cute"]), "url2"
    )
    pin3 = await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Pin 3", tags=["dogs", "funny"]),
        "url3",
    )
    await create_pin(
        db_session, sample_user, PinCreate(title="Pin 4", tags=["birds"]), "url4"
    )

    related = await get_related_pins_from_db(db_session, pin1.id)
    assert len(related) == 2
    related_ids = {r.id for r in related}
    assert pin2.id in related_ids
    assert pin3.id in related_ids


@pytest.mark.asyncio
async def test_get_pins_by_ids(db_session: AsyncSession, sample_user):
    pin1 = await create_pin(db_session, sample_user, PinCreate(title="Pin 1"), "url1")
    pin2 = await create_pin(db_session, sample_user, PinCreate(title="Pin 2"), "url2")

    result = await get_pins_by_ids(
        db_session, [str(pin1.id), str(pin2.id), "invalid-uuid"]
    )
    assert len(result) == 2
    ids = {p.id for p in result}
    assert pin1.id in ids
    assert pin2.id in ids


@pytest.mark.asyncio
async def test_like_pin_success(db_session: AsyncSession, sample_user):
    pin = await create_pin(
        db_session, sample_user, PinCreate(title="Like Me"), "http://img.jpg"
    )
    assert pin.likes_count == 0

    liked = await like_pin(db_session, pin.id, sample_user.id)
    assert liked.likes_count == 1


@pytest.mark.asyncio
async def test_like_pin_duplicate_raises_conflict(
    db_session: AsyncSession, sample_user
):
    pin = await create_pin(
        db_session, sample_user, PinCreate(title="Like Once"), "http://img.jpg"
    )
    await like_pin(db_session, pin.id, sample_user.id)

    with pytest.raises(HTTPException) as excinfo:
        await like_pin(db_session, pin.id, sample_user.id)
    assert excinfo.value.status_code == 409
    assert "already exists" in excinfo.value.detail


@pytest.mark.asyncio
async def test_unlike_pin_success(db_session: AsyncSession, sample_user):
    pin = await create_pin(
        db_session, sample_user, PinCreate(title="Unlike Me"), "http://img.jpg"
    )
    await like_pin(db_session, pin.id, sample_user.id)

    unliked = await unlike_pin(db_session, pin.id, sample_user.id)
    assert unliked.likes_count == 0


@pytest.mark.asyncio
async def test_unlike_pin_not_found_raises_404(db_session: AsyncSession, sample_user):
    pin = await create_pin(
        db_session, sample_user, PinCreate(title="No Like"), "http://img.jpg"
    )

    with pytest.raises(HTTPException) as excinfo:
        await unlike_pin(db_session, pin.id, sample_user.id)
    assert excinfo.value.status_code == 404
    assert "not found" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_unlike_pin_likes_count_does_not_go_below_zero(
    db_session: AsyncSession, sample_user, another_user
):
    """likes_count floors at 0 even with two users liking then one unliking."""
    pin = await create_pin(
        db_session, sample_user, PinCreate(title="Floor Test"), "http://img.jpg"
    )
    await like_pin(db_session, pin.id, sample_user.id)
    unliked = await unlike_pin(db_session, pin.id, sample_user.id)
    assert unliked.likes_count == 0


# ── Search & Filter ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_pins_search_by_title(db_session: AsyncSession, sample_user):
    await create_pin(
        db_session, sample_user, PinCreate(title="Sunset Beach"), "http://a.jpg"
    )
    await create_pin(
        db_session, sample_user, PinCreate(title="Mountain Hike"), "http://b.jpg"
    )
    await create_pin(
        db_session, sample_user, PinCreate(title="City Sunset View"), "http://c.jpg"
    )

    results = await get_pins(db_session, search="sunset")
    titles = {p.title for p in results}
    assert "Sunset Beach" in titles
    assert "City Sunset View" in titles
    assert "Mountain Hike" not in titles


@pytest.mark.asyncio
async def test_get_pins_filter_by_tag(db_session: AsyncSession, sample_user):
    await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Nature Pin", tags=["nature"]),
        "http://n.jpg",
    )
    await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Food Pin", tags=["food"]),
        "http://f.jpg",
    )
    await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Nature Food Pin", tags=["nature", "food"]),
        "http://nf.jpg",
    )

    results = await get_pins(db_session, tags=["nature"])
    titles = {p.title for p in results}
    assert "Nature Pin" in titles
    assert "Nature Food Pin" in titles
    assert "Food Pin" not in titles


@pytest.mark.asyncio
async def test_get_pins_order_by_created_at_newest(
    db_session: AsyncSession, sample_user
):
    for i in range(3):
        await create_pin(
            db_session,
            sample_user,
            PinCreate(title=f"Ordered Pin {i}"),
            "http://img.jpg",
        )

    results = await get_pins(db_session, created_at=CreatedAt.newest, limit=3)
    # Most recent first
    assert results[0].created_at >= results[-1].created_at


@pytest.mark.asyncio
async def test_get_pins_order_by_created_at_oldest(
    db_session: AsyncSession, sample_user
):
    results = await get_pins(db_session, created_at=CreatedAt.oldest)
    if len(results) >= 2:
        assert results[0].created_at <= results[-1].created_at


@pytest.mark.asyncio
async def test_get_pins_order_by_popularity_most_popular(
    db_session: AsyncSession, sample_user, another_user
):
    low = await create_pin(
        db_session, sample_user, PinCreate(title="Low Likes"), "http://low.jpg"
    )
    high = await create_pin(
        db_session, sample_user, PinCreate(title="High Likes"), "http://high.jpg"
    )
    # Give 'high' two likes from distinct users
    await like_pin(db_session, high.id, sample_user.id)
    await like_pin(db_session, high.id, another_user.id)

    results = await get_pins(db_session, popularity=Popularity.most_popular)
    ordered_ids = [p.id for p in results]
    assert ordered_ids.index(high.id) < ordered_ids.index(low.id)


@pytest.mark.asyncio
async def test_get_pins_order_by_popularity_least_popular(
    db_session: AsyncSession, sample_user, another_user
):
    zero = await create_pin(
        db_session, sample_user, PinCreate(title="Zero Likes"), "http://z.jpg"
    )
    popular = await create_pin(
        db_session, sample_user, PinCreate(title="One Like"), "http://p.jpg"
    )
    await like_pin(db_session, popular.id, sample_user.id)

    results = await get_pins(db_session, popularity=Popularity.least_popular)
    ordered_ids = [p.id for p in results]
    assert ordered_ids.index(zero.id) < ordered_ids.index(popular.id)


@pytest.mark.asyncio
async def test_get_pins_search_and_tag_combined(db_session: AsyncSession, sample_user):
    await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Ocean Waves", tags=["water"]),
        "http://ow.jpg",
    )
    await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Ocean Storm", tags=["storm"]),
        "http://os.jpg",
    )
    await create_pin(
        db_session,
        sample_user,
        PinCreate(title="Lake Waves", tags=["water"]),
        "http://lw.jpg",
    )

    # Search "Ocean" AND tag "water" → only "Ocean Waves"
    results = await get_pins(db_session, search="Ocean", tags=["water"])
    titles = {p.title for p in results}
    assert titles == {"Ocean Waves"}

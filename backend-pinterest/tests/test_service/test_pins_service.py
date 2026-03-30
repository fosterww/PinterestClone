import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.users.schemas import UserCreate
from src.pins.schemas import PinCreate, PinUpdate, CreatedAt, Popularity

from src.auth.service import AuthService
from src.pins.repository import PinRepository
from src.pins.service import PinService
from src.users.repository import UserRepository
from src.auth.repository import AuthRepository
from src.tags.service import TagService


@pytest.fixture
def auth_svc(db_session: AsyncSession, mock_session_service):
    user_repo = UserRepository(db_session)
    auth_repo = AuthRepository(db_session)
    return AuthService(db_session, mock_session_service, user_repo, auth_repo)


@pytest.fixture
def pin_svc(db_session: AsyncSession, mock_cache_service):
    repo = PinRepository(db_session)
    tag_service = TagService(db_session)
    return PinService(db_session, mock_cache_service, repo, tag_service)


@pytest_asyncio.fixture
async def sample_user(auth_svc: AuthService):
    user_data = UserCreate(
        username="pin_svc_tester",
        email="pin_svc@example.com",
        password="securepassword",
    )
    return await auth_svc.register_user(user_data)


@pytest_asyncio.fixture
async def another_user(auth_svc: AuthService):
    user_data = UserCreate(
        username="pin_svc_other",
        email="pin_svc_other@example.com",
        password="securepassword",
    )
    return await auth_svc.register_user(user_data)


@pytest.mark.asyncio
async def test_create_and_get_pin_no_tags(pin_svc: PinService, sample_user):
    pin_data = PinCreate(
        title="Test Pin",
        description="A beautiful test pin",
        link_url="https://example.com",
    )
    image_url = "https://example.com/image.jpg"

    created_pin = await pin_svc.create_pin(sample_user, pin_data, image_url)
    assert created_pin is not None
    assert created_pin.title == "Test Pin"
    assert created_pin.image_url == image_url
    assert created_pin.owner_id == sample_user.id
    assert created_pin.tags == []

    fetched_pin = await pin_svc.get_pin_by_id(created_pin.id)
    assert fetched_pin is not None
    assert fetched_pin.id == created_pin.id
    assert fetched_pin.title == "Test Pin"


@pytest.mark.asyncio
async def test_create_pin_with_tags(pin_svc: PinService, sample_user):
    pin_data = PinCreate(title="Tagged Pin", tags=["nature", "travel"])
    image_url = "https://example.com/image.jpg"

    created_pin = await pin_svc.create_pin(sample_user, pin_data, image_url)
    assert created_pin is not None
    tag_names = {t.name for t in created_pin.tags}
    assert tag_names == {"nature", "travel"}


@pytest.mark.asyncio
async def test_create_pin_reuses_existing_tags(pin_svc: PinService, sample_user):
    pin1 = await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Pin 1", tags=["cats"]),
        "http://img.jpg",
    )
    pin2 = await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Pin 2", tags=["cats"]),
        "http://img.jpg",
    )

    tag_id_pin1 = {t.name: t.id for t in pin1.tags}["cats"]
    tag_id_pin2 = {t.name: t.id for t in pin2.tags}["cats"]
    assert tag_id_pin1 == tag_id_pin2


@pytest.mark.asyncio
async def test_get_pins_pagination(pin_svc: PinService, sample_user):
    image_url = "https://example.com/image.jpg"

    for i in range(5):
        pin_data = PinCreate(title=f"Pin {i}")
        await pin_svc.create_pin(sample_user, pin_data, image_url)

    pins_page_1 = await pin_svc.get_pins(offset=0, limit=3)
    assert len(pins_page_1) == 3

    pins_page_2 = await pin_svc.get_pins(offset=3, limit=3)
    assert len(pins_page_2) == 2


@pytest.mark.asyncio
async def test_update_pin_success_and_forbidden(
    pin_svc: PinService, sample_user, another_user
):
    pin_data = PinCreate(title="Original Title", tags=["old-tag"])
    image_url = "https://example.com/image.jpg"
    created_pin = await pin_svc.create_pin(sample_user, pin_data, image_url)

    update_data = PinUpdate(title="Updated Title")
    pin_model = await pin_svc.get_pin_by_id(created_pin.id)
    updated_pin = await pin_svc.update_pin(pin_model, update_data, sample_user)
    assert updated_pin.title == "Updated Title"

    pin_model2 = await pin_svc.get_pin_by_id(created_pin.id)
    with pytest.raises(HTTPException) as excinfo:
        await pin_svc.update_pin(pin_model2, update_data, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the pin owner"


@pytest.mark.asyncio
async def test_delete_pin_success_and_forbidden(
    pin_svc: PinService, sample_user, another_user
):
    pin_data = PinCreate(title="To be deleted")
    image_url = "https://example.com/image.jpg"
    created_pin = await pin_svc.create_pin(sample_user, pin_data, image_url)

    pin_model = await pin_svc.get_pin_by_id(created_pin.id)
    with pytest.raises(HTTPException) as excinfo:
        await pin_svc.delete_pin(pin_model, another_user)
    assert excinfo.value.status_code == 403

    pin_model2 = await pin_svc.get_pin_by_id(created_pin.id)
    await pin_svc.delete_pin(pin_model2, sample_user)

    with pytest.raises(Exception):
        await pin_svc.get_pin_by_id(created_pin.id)


@pytest.mark.asyncio
async def test_get_related_pins_from_db(pin_svc: PinService, sample_user):
    pin1 = await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Pin 1", tags=["cats", "funny"]),
        "url1",
    )
    pin2 = await pin_svc.create_pin(
        sample_user, PinCreate(title="Pin 2", tags=["cats", "cute"]), "url2"
    )
    pin3 = await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Pin 3", tags=["dogs", "funny"]),
        "url3",
    )
    await pin_svc.create_pin(
        sample_user, PinCreate(title="Pin 4", tags=["birds"]), "url4"
    )

    related = await pin_svc.get_related_pins(pin1.id)
    assert len(related) == 2
    related_ids = {r.id for r in related}
    assert pin2.id in related_ids
    assert pin3.id in related_ids


@pytest.mark.asyncio
async def test_get_pins_by_ids(pin_svc: PinService, sample_user):
    pin1 = await pin_svc.create_pin(sample_user, PinCreate(title="Pin 1"), "url1")
    pin2 = await pin_svc.create_pin(sample_user, PinCreate(title="Pin 2"), "url2")

    result = await pin_svc.get_pins_by_ids([str(pin1.id), str(pin2.id), "invalid-uuid"])
    assert len(result) == 2
    ids = {p.id for p in result}
    assert pin1.id in ids
    assert pin2.id in ids


@pytest.mark.asyncio
async def test_like_pin_success(pin_svc: PinService, sample_user):
    pin = await pin_svc.create_pin(
        sample_user, PinCreate(title="Like Me"), "http://img.jpg"
    )
    assert getattr(pin, "likes_count", 0) == 0

    liked = await pin_svc.like_pin(pin.id, sample_user.id)
    assert getattr(liked, "likes_count", 1) == 1


@pytest.mark.asyncio
async def test_like_pin_duplicate_raises_conflict(pin_svc: PinService, sample_user):
    pin = await pin_svc.create_pin(
        sample_user, PinCreate(title="Like Once"), "http://img.jpg"
    )
    await pin_svc.like_pin(pin.id, sample_user.id)

    with pytest.raises(HTTPException) as excinfo:
        await pin_svc.like_pin(pin.id, sample_user.id)
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_unlike_pin_success(pin_svc: PinService, sample_user):
    pin = await pin_svc.create_pin(
        sample_user, PinCreate(title="Unlike Me"), "http://img.jpg"
    )
    await pin_svc.like_pin(pin.id, sample_user.id)

    unliked = await pin_svc.unlike_pin(pin.id, sample_user.id)
    assert getattr(unliked, "likes_count", 0) == 0


@pytest.mark.asyncio
async def test_unlike_pin_likes_count_does_not_go_below_zero(
    pin_svc: PinService, sample_user, another_user
):
    pin = await pin_svc.create_pin(
        sample_user, PinCreate(title="Floor Test"), "http://img.jpg"
    )
    await pin_svc.like_pin(pin.id, sample_user.id)
    unliked = await pin_svc.unlike_pin(pin.id, sample_user.id)
    assert getattr(unliked, "likes_count", 0) == 0


@pytest.mark.asyncio
async def test_get_pins_search_by_title(pin_svc: PinService, sample_user):
    await pin_svc.create_pin(
        sample_user, PinCreate(title="Sunset Beach"), "http://a.jpg"
    )
    await pin_svc.create_pin(
        sample_user, PinCreate(title="Mountain Hike"), "http://b.jpg"
    )
    await pin_svc.create_pin(
        sample_user, PinCreate(title="City Sunset View"), "http://c.jpg"
    )

    results = await pin_svc.get_pins(search="sunset")
    titles = {p.title for p in results}
    assert "Sunset Beach" in titles
    assert "City Sunset View" in titles
    assert "Mountain Hike" not in titles


@pytest.mark.asyncio
async def test_get_pins_filter_by_tag(pin_svc: PinService, sample_user):
    await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Nature Pin", tags=["nature"]),
        "http://n.jpg",
    )
    await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Food Pin", tags=["food"]),
        "http://f.jpg",
    )
    await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Nature Food Pin", tags=["nature", "food"]),
        "http://nf.jpg",
    )

    results = await pin_svc.get_pins(tags=["nature"])
    titles = {p.title for p in results}
    assert "Nature Pin" in titles
    assert "Nature Food Pin" in titles
    assert "Food Pin" not in titles


@pytest.mark.asyncio
async def test_get_pins_order_by_created_at_newest(pin_svc: PinService, sample_user):
    for i in range(3):
        await pin_svc.create_pin(
            sample_user,
            PinCreate(title=f"Ordered Pin {i}"),
            "http://img.jpg",
        )

    results = await pin_svc.get_pins(created_at=CreatedAt.newest, limit=3)
    assert results[0].created_at >= results[-1].created_at


@pytest.mark.asyncio
async def test_get_pins_order_by_created_at_oldest(pin_svc: PinService, sample_user):
    results = await pin_svc.get_pins(created_at=CreatedAt.oldest)
    if len(results) >= 2:
        assert results[0].created_at <= results[-1].created_at


@pytest.mark.asyncio
async def test_get_pins_order_by_popularity_most_popular(
    pin_svc: PinService, sample_user, another_user
):
    low = await pin_svc.create_pin(
        sample_user, PinCreate(title="Low Likes"), "http://low.jpg"
    )
    high = await pin_svc.create_pin(
        sample_user, PinCreate(title="High Likes"), "http://high.jpg"
    )
    await pin_svc.like_pin(high.id, sample_user.id)
    await pin_svc.like_pin(high.id, another_user.id)

    results = await pin_svc.get_pins(popularity=Popularity.most_popular)
    ordered_ids = [p.id for p in results]
    assert ordered_ids.index(high.id) < ordered_ids.index(low.id)


@pytest.mark.asyncio
async def test_get_pins_order_by_popularity_least_popular(
    pin_svc: PinService, sample_user, another_user
):
    zero = await pin_svc.create_pin(
        sample_user, PinCreate(title="Zero Likes"), "http://z.jpg"
    )
    popular = await pin_svc.create_pin(
        sample_user, PinCreate(title="One Like"), "http://p.jpg"
    )
    await pin_svc.like_pin(popular.id, sample_user.id)

    results = await pin_svc.get_pins(popularity=Popularity.least_popular)
    ordered_ids = [p.id for p in results]
    assert ordered_ids.index(zero.id) < ordered_ids.index(popular.id)


@pytest.mark.asyncio
async def test_get_pins_search_and_tag_combined(pin_svc: PinService, sample_user):
    await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Ocean Waves", tags=["water"]),
        "http://ow.jpg",
    )
    await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Ocean Storm", tags=["storm"]),
        "http://os.jpg",
    )
    await pin_svc.create_pin(
        sample_user,
        PinCreate(title="Lake Waves", tags=["water"]),
        "http://lw.jpg",
    )

    results = await pin_svc.get_pins(search="Ocean", tags=["water"])
    titles = {p.title for p in results}
    assert titles == {"Ocean Waves"}

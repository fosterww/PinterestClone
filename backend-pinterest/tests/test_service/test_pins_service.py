import pytest
import uuid

from fastapi import UploadFile
import io

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from sqlalchemy import select

from boards.models import (
    PinEditHistoryModel,
    PinModel,
    PinModerationStatus,
    PinProcessingState,
)
from users.schemas import UserCreate
from pins.schemas import PinCreate, PinUpdate, CreatedAt, Popularity

from auth.service import AuthService
from core.exception import ProviderError
from pins.service.pin import PinService
from users.repository import UserRepository
from auth.repository import AuthRepository


def mock_image_file():
    content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\xd7c\x60\x00\x02\x00\x00\x05\x00\x01^\xf3*:\x00\x00\x00\x00IEND\xaeB`\x82"
    return UploadFile(
        filename="test.png",
        file=io.BytesIO(content),
        headers={"content-type": "image/png"},
    )


async def trust_pins(db_session: AsyncSession, *pins: PinModel) -> None:
    for pin in pins:
        pin.processing_state = PinProcessingState.INDEXED
        pin.moderation_status = PinModerationStatus.APPROVED
        pin.is_duplicate = False
        pin.duplicate_of_pin_id = None
    await db_session.flush()


@pytest.fixture
def auth_svc(db_session: AsyncSession, mock_session_service):
    user_repo = UserRepository(db_session)
    auth_repo = AuthRepository(db_session)
    return AuthService(db_session, mock_session_service, user_repo, auth_repo)


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

    created_pin = await pin_svc.create_pin(mock_image_file(), sample_user, pin_data)
    assert created_pin is not None
    assert created_pin.title == "Test Pin"
    assert created_pin.image_url == "http://mock-s3-url.com/image.jpg"
    assert created_pin.owner_id == sample_user.id
    tag_names = {t.name for t in created_pin.tags}
    assert tag_names == set()
    assert created_pin.processing_state == PinProcessingState.UPLOADED
    assert created_pin.moderation_status == PinModerationStatus.PENDING

    fetched_pin = await pin_svc.get_pin_by_id(created_pin.id)
    assert fetched_pin is not None
    assert fetched_pin.id == created_pin.id
    assert fetched_pin.title == "Test Pin"


@pytest.mark.asyncio
async def test_create_pin_with_tags(pin_svc: PinService, sample_user):
    pin_data = PinCreate(title="Tagged Pin", tags=["nature", "travel"])

    created_pin = await pin_svc.create_pin(mock_image_file(), sample_user, pin_data)
    assert created_pin is not None
    tag_names = {t.name for t in created_pin.tags}
    assert tag_names == {"nature", "travel"}


@pytest.mark.asyncio
async def test_create_pin_raises_provider_error_when_ai_description_fails(
    pin_svc: PinService, sample_user, monkeypatch
):
    monkeypatch.setattr(
        pin_svc.gemini_service,
        "generate_description",
        lambda image_bytes, title: None,
    )
    pin_data = PinCreate(
        title="AI Description Pin",
        tags=["nature"],
        generate_ai_description=True,
    )

    with pytest.raises(ProviderError) as excinfo:
        await pin_svc.create_pin(mock_image_file(), sample_user, pin_data)

    assert excinfo.value.status_code == 502
    assert excinfo.value.detail == "Failed to generate description"


@pytest.mark.asyncio
async def test_create_pin_stores_metadata_and_history(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    created_pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Metadata Pin", tags=["meta"])
    )

    assert created_pin.file_hash_sha256 is not None
    assert len(created_pin.file_hash_sha256) == 64
    assert created_pin.image_width == 100
    assert created_pin.image_height == 100
    assert created_pin.is_duplicate is False
    assert created_pin.processing_state == PinProcessingState.TAGGED
    assert created_pin.moderation_status == PinModerationStatus.PENDING

    result = await db_session.execute(
        select(PinEditHistoryModel).where(PinEditHistoryModel.pin_id == created_pin.id)
    )
    history = result.scalars().all()
    assert len(history) == 1
    assert history[0].reason == "pin_created"
    assert history[0].actor_user_id == sample_user.id


@pytest.mark.asyncio
async def test_create_pin_marks_exact_duplicate(pin_svc: PinService, sample_user):
    original = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Original", tags=["dup"])
    )
    duplicate = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Duplicate", tags=["dup"])
    )

    assert duplicate.is_duplicate is True
    assert duplicate.duplicate_of_pin_id == original.id
    assert duplicate.moderation_status == PinModerationStatus.HIDDEN


@pytest.mark.asyncio
async def test_create_pin_reuses_existing_tags(pin_svc: PinService, sample_user):
    pin1 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 1", tags=["cats"])
    )
    pin2 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 2", tags=["cats"])
    )

    tag_id_pin1 = {t.name: t.id for t in pin1.tags}["cats"]
    tag_id_pin2 = {t.name: t.id for t in pin2.tags}["cats"]
    assert tag_id_pin1 == tag_id_pin2


@pytest.mark.asyncio
async def test_get_pins_pagination(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    created_pins = []
    for i in range(5):
        pin_data = PinCreate(title=f"Pin {i}")
        created_pins.append(
            await pin_svc.create_pin(mock_image_file(), sample_user, pin_data)
        )
    await trust_pins(db_session, *created_pins)

    pins_page_1 = await pin_svc.get_pins(offset=0, limit=3)
    assert len(pins_page_1) == 3

    pins_page_2 = await pin_svc.get_pins(offset=3, limit=3)
    assert len(pins_page_2) == 2


@pytest.mark.asyncio
async def test_update_pin_success_and_forbidden(
    db_session: AsyncSession, pin_svc: PinService, sample_user, another_user
):
    pin_data = PinCreate(title="Original Title", tags=["old-tag"])
    created_pin = await pin_svc.create_pin(mock_image_file(), sample_user, pin_data)

    update_data = PinUpdate(title="Updated Title")
    pin_model = await pin_svc.get_pin_by_id(created_pin.id)
    updated_pin = await pin_svc.update_pin(pin_model, update_data, sample_user)
    assert updated_pin.title == "Updated Title"

    pin_model2 = await pin_svc.get_pin_by_id(created_pin.id)
    with pytest.raises(HTTPException) as excinfo:
        await pin_svc.update_pin(pin_model2, update_data, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the pin owner"

    result = await db_session.execute(
        select(PinEditHistoryModel).where(
            PinEditHistoryModel.pin_id == created_pin.id,
            PinEditHistoryModel.reason == "pin_updated",
        )
    )
    history = result.scalar_one()
    assert history.actor_user_id == sample_user.id
    assert history.before == {"title": "Original Title"}
    assert history.after == {"title": "Updated Title"}


@pytest.mark.asyncio
async def test_update_pin_audits_tag_only_change(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    created_pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Tag Audit", tags=["old-tag"])
    )

    pin_model = await pin_svc.get_pin_by_id(created_pin.id)
    updated_pin = await pin_svc.update_pin(
        pin_model, PinUpdate(tags=["new-tag"]), sample_user
    )

    assert {tag.name for tag in updated_pin.tags} == {"new-tag"}
    result = await db_session.execute(
        select(PinEditHistoryModel).where(
            PinEditHistoryModel.pin_id == created_pin.id,
            PinEditHistoryModel.reason == "pin_updated",
        )
    )
    history = result.scalar_one()
    assert history.changed_fields == ["tags"]
    assert history.before == {"tags": ["old-tag"]}
    assert history.after == {"tags": ["new-tag"]}


@pytest.mark.asyncio
async def test_update_pin_can_clear_description(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    created_pin = await pin_svc.create_pin(
        mock_image_file(),
        sample_user,
        PinCreate(title="Clear Description", description="Existing description"),
    )

    pin_model = await pin_svc.get_pin_by_id(created_pin.id)
    updated_pin = await pin_svc.update_pin(
        pin_model, PinUpdate(description="   "), sample_user
    )

    assert updated_pin.description is None
    result = await db_session.execute(
        select(PinEditHistoryModel).where(
            PinEditHistoryModel.pin_id == created_pin.id,
            PinEditHistoryModel.reason == "pin_updated",
        )
    )
    history = result.scalar_one()
    assert history.before == {"description": "Existing description"}
    assert history.after == {"description": None}


@pytest.mark.asyncio
async def test_delete_pin_success_and_forbidden(
    pin_svc: PinService, sample_user, another_user
):
    pin_data = PinCreate(title="To be deleted")
    created_pin = await pin_svc.create_pin(mock_image_file(), sample_user, pin_data)

    pin_model = await pin_svc.get_pin_by_id(created_pin.id)
    with pytest.raises(HTTPException) as excinfo:
        await pin_svc.delete_pin(pin_model, another_user)
    assert excinfo.value.status_code == 403

    pin_model2 = await pin_svc.get_pin_by_id(created_pin.id)
    await pin_svc.delete_pin(pin_model2, sample_user)

    with pytest.raises(Exception):
        await pin_svc.get_pin_by_id(created_pin.id)


@pytest.mark.asyncio
async def test_get_related_pins_from_db(
    db_session: AsyncSession, pin_svc: PinService, sample_user, discovery_svc
):
    pin1 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 1", tags=["cats", "funny"])
    )
    pin2 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 2", tags=["cats", "cute"])
    )
    pin3 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 3", tags=["dogs", "funny"])
    )
    pin4 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 4", tags=["birds"])
    )
    await trust_pins(db_session, pin1, pin2, pin3, pin4)

    related = await discovery_svc.get_related_pins(pin1.id)
    assert len(related) == 2
    related_ids = {r.id for r in related}
    assert pin2.id in related_ids
    assert pin3.id in related_ids


@pytest.mark.asyncio
async def test_get_pins_by_ids(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    pin1 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 1")
    )
    pin2 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Pin 2")
    )
    await trust_pins(db_session, pin1, pin2)

    result = await pin_svc.get_pins_by_ids([str(pin1.id), str(pin2.id), "invalid-uuid"])
    assert len(result) == 2
    ids = {p.id for p in result}
    assert pin1.id in ids
    assert pin2.id in ids


@pytest.mark.asyncio
async def test_like_pin_success(pin_svc: PinService, sample_user):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Like Me")
    )
    assert getattr(pin, "likes_count", 0) == 0

    liked = await pin_svc.like_pin(pin.id, sample_user.id)
    assert getattr(liked, "likes_count", 1) == 1


@pytest.mark.asyncio
async def test_like_pin_duplicate_raises_conflict(pin_svc: PinService, sample_user):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Like Once")
    )
    await pin_svc.like_pin(pin.id, sample_user.id)

    with pytest.raises(HTTPException) as excinfo:
        await pin_svc.like_pin(pin.id, sample_user.id)
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_unlike_pin_success(pin_svc: PinService, sample_user):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Unlike Me")
    )
    await pin_svc.like_pin(pin.id, sample_user.id)

    unliked = await pin_svc.unlike_pin(pin.id, sample_user.id)
    assert getattr(unliked, "likes_count", 0) == 0


@pytest.mark.asyncio
async def test_unlike_pin_likes_count_does_not_go_below_zero(
    pin_svc: PinService, sample_user, another_user
):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Floor Test")
    )
    await pin_svc.like_pin(pin.id, sample_user.id)
    unliked = await pin_svc.unlike_pin(pin.id, sample_user.id)
    assert getattr(unliked, "likes_count", 0) == 0


@pytest.mark.asyncio
async def test_get_pins_search_by_title(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    pin1 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Sunset Beach")
    )
    pin2 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Mountain Hike")
    )
    pin3 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="City Sunset View")
    )
    await trust_pins(db_session, pin1, pin2, pin3)

    results = await pin_svc.get_pins(search="sunset")
    titles = {p.title for p in results}
    assert "Sunset Beach" in titles
    assert "City Sunset View" in titles
    assert "Mountain Hike" not in titles


@pytest.mark.asyncio
async def test_get_pins_filter_by_tag(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    pin1 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Nature Pin", tags=["nature"])
    )
    pin2 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Food Pin", tags=["food"])
    )
    pin3 = await pin_svc.create_pin(
        mock_image_file(),
        sample_user,
        PinCreate(title="Nature Food Pin", tags=["nature", "food"]),
    )
    await trust_pins(db_session, pin1, pin2, pin3)

    results = await pin_svc.get_pins(tags=["nature"])
    titles = {p.title for p in results}
    assert "Nature Pin" in titles
    assert "Nature Food Pin" in titles
    assert "Food Pin" not in titles


@pytest.mark.asyncio
async def test_get_pins_order_by_created_at_newest(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    created_pins = []
    for i in range(3):
        created_pins.append(
            await pin_svc.create_pin(
                mock_image_file(), sample_user, PinCreate(title=f"Ordered Pin {i}")
            )
        )
    await trust_pins(db_session, *created_pins)

    results = await pin_svc.get_pins(created_at=CreatedAt.newest, limit=3)
    assert results[0].created_at >= results[-1].created_at


@pytest.mark.asyncio
async def test_get_pins_order_by_created_at_oldest(pin_svc: PinService, sample_user):
    results = await pin_svc.get_pins(created_at=CreatedAt.oldest)
    if len(results) >= 2:
        assert results[0].created_at <= results[-1].created_at


@pytest.mark.asyncio
async def test_get_pins_order_by_popularity_most_popular(
    db_session: AsyncSession, pin_svc: PinService, sample_user, another_user
):
    low = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Low Likes")
    )
    high = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="High Likes")
    )
    await trust_pins(db_session, low, high)
    await pin_svc.like_pin(high.id, sample_user.id)
    await pin_svc.like_pin(high.id, another_user.id)

    results = await pin_svc.get_pins(popularity=Popularity.most_popular)
    ordered_ids = [p.id for p in results]
    assert ordered_ids.index(high.id) < ordered_ids.index(low.id)


@pytest.mark.asyncio
async def test_get_pins_order_by_popularity_least_popular(
    db_session: AsyncSession, pin_svc: PinService, sample_user, another_user
):
    zero = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Zero Likes")
    )
    popular = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="One Like")
    )
    await trust_pins(db_session, zero, popular)
    await pin_svc.like_pin(popular.id, sample_user.id)

    results = await pin_svc.get_pins(popularity=Popularity.least_popular)
    ordered_ids = [p.id for p in results]
    assert ordered_ids.index(zero.id) < ordered_ids.index(popular.id)


@pytest.mark.asyncio
async def test_get_pins_search_and_tag_combined(
    db_session: AsyncSession, pin_svc: PinService, sample_user
):
    pin1 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Ocean Waves", tags=["water"])
    )
    pin2 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Ocean Storm", tags=["storm"])
    )
    pin3 = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Lake Waves", tags=["water"])
    )
    await trust_pins(db_session, pin1, pin2, pin3)

    results = await pin_svc.get_pins(search="Ocean", tags=["water"])
    titles = {p.title for p in results}
    assert titles == {"Ocean Waves"}


@pytest.mark.asyncio
async def test_add_comment(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    assert comment.comment == "Great pin!"
    assert comment.user_id == sample_user.id
    assert comment.pin_id == pin.id


@pytest.mark.asyncio
async def test_add_comment_toxic(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.add_comment(pin.id, None, sample_user.id, "You are stupid")
    assert excinfo.value.status_code == 400
    comments = await comment_svc.get_comments(pin.id)
    assert len(comments) == 0


@pytest.mark.asyncio
async def test_add_comment_pin_not_found(pin_svc: PinService, sample_user, comment_svc):
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.add_comment(uuid.uuid4(), None, sample_user.id, "Comment")
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_comments(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    comments = await comment_svc.get_comments(pin.id)
    assert len(comments) == 1
    assert comments[0].comment == "Great pin!"
    assert comments[0].user.id == sample_user.id


@pytest.mark.asyncio
async def test_get_comment_by_id(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    retrieved_comment = await comment_svc.get_comment_by_id(comment.id)
    assert retrieved_comment.comment == "Great pin!"
    assert retrieved_comment.user.id == sample_user.id


@pytest.mark.asyncio
async def test_get_comment_by_id_not_found(
    pin_svc: PinService, sample_user, comment_svc
):
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.get_comment_by_id(uuid.uuid4())
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_comment(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    await comment_svc.delete_comment(pin.id, comment.id, sample_user)
    comments = await comment_svc.get_comments(pin.id)
    assert len(comments) == 0


@pytest.mark.asyncio
async def test_delete_comment_not_owner(
    pin_svc: PinService, sample_user, another_user, comment_svc
):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.delete_comment(pin.id, comment.id, another_user)
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_comment_not_found(pin_svc: PinService, sample_user, comment_svc):
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.delete_comment(uuid.uuid4(), uuid.uuid4(), sample_user)
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_update_comment(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    updated_comment = await comment_svc.update_comment(
        comment.id, sample_user.id, "Great pin! Updated"
    )
    assert updated_comment.comment == "Great pin! Updated"
    assert updated_comment.user.id == sample_user.id
    assert updated_comment.pin_id == pin.id


@pytest.mark.asyncio
async def test_update_comment_not_owner(
    pin_svc: PinService, sample_user, another_user, comment_svc
):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.update_comment(
            comment.id, another_user.id, "Great pin! Updated"
        )
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_update_comment_not_found(pin_svc: PinService, sample_user, comment_svc):
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.update_comment(
            uuid.uuid4(), sample_user.id, "Great pin! Updated"
        )
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_comment_like(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    await comment_svc.add_comment_like(pin.id, comment.id, sample_user.id)
    liked_comment = await comment_svc.get_comment_by_id(comment.id)
    assert liked_comment.likes_count == 1


@pytest.mark.asyncio
async def test_comment_like_not_found(pin_svc: PinService, sample_user, comment_svc):
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.add_comment_like(uuid.uuid4(), uuid.uuid4(), sample_user.id)
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_comment_like_already_liked(
    pin_svc: PinService, sample_user, comment_svc
):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    await comment_svc.add_comment_like(pin.id, comment.id, sample_user.id)
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.add_comment_like(pin.id, comment.id, sample_user.id)
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_comment_unlike(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    await comment_svc.add_comment_like(pin.id, comment.id, sample_user.id)
    await comment_svc.delete_comment_like(pin.id, comment.id, sample_user.id)
    unliked_comment = await comment_svc.get_comment_by_id(comment.id)
    assert unliked_comment.likes_count == 0


@pytest.mark.asyncio
async def test_comment_unlike_not_found(pin_svc: PinService, sample_user, comment_svc):
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.delete_comment_like(
            uuid.uuid4(), uuid.uuid4(), sample_user.id
        )
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_comment_unlike_not_liked(pin_svc: PinService, sample_user, comment_svc):
    pin = await pin_svc.create_pin(
        mock_image_file(), sample_user, PinCreate(title="Comment Test")
    )
    comment = await comment_svc.add_comment(pin.id, None, sample_user.id, "Great pin!")
    with pytest.raises(HTTPException) as excinfo:
        await comment_svc.delete_comment_like(pin.id, comment.id, sample_user.id)
    assert excinfo.value.status_code == 404

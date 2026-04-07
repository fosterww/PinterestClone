import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tags.service import TagService
from boards.models import TagModel


@pytest.fixture
def tag_svc(db_session: AsyncSession):
    return TagService(db_session)


@pytest.mark.asyncio
async def test_get_or_create_tag_creates_new_tags(tag_svc: TagService):
    tags = await tag_svc.get_or_create_tag(["nature", "travel"])

    assert len(tags) == 2
    names = {t.name for t in tags}
    assert names == {"nature", "travel"}
    for t in tags:
        assert isinstance(t, TagModel)
        assert t.id is not None


@pytest.mark.asyncio
async def test_get_or_create_tag_reuses_existing_tags(tag_svc: TagService):
    first_call = await tag_svc.get_or_create_tag(["food", "lifestyle"])
    first_ids = {t.name: t.id for t in first_call}

    second_call = await tag_svc.get_or_create_tag(["food", "lifestyle"])
    second_ids = {t.name: t.id for t in second_call}

    assert first_ids == second_ids


@pytest.mark.asyncio
async def test_get_or_create_tag_partial_reuse(tag_svc: TagService):
    existing = await tag_svc.get_or_create_tag(["photography"])
    existing_id = existing[0].id

    tags = await tag_svc.get_or_create_tag(["photography", "art"])
    names = {t.name for t in tags}
    ids_by_name = {t.name: t.id for t in tags}

    assert names == {"photography", "art"}
    assert ids_by_name["photography"] == existing_id


@pytest.mark.asyncio
async def test_get_or_create_tag_empty_list(tag_svc: TagService):
    result = await tag_svc.get_or_create_tag([])
    assert result == []

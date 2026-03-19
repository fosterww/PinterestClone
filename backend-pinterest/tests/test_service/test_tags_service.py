import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.tags.service import get_or_create_tag
from src.boards.models import TagModel


@pytest.mark.asyncio
async def test_get_or_create_tag_creates_new_tags(db_session: AsyncSession):
    tags = await get_or_create_tag(db_session, ["nature", "travel"])

    assert len(tags) == 2
    names = {t.name for t in tags}
    assert names == {"nature", "travel"}
    for t in tags:
        assert isinstance(t, TagModel)
        assert t.id is not None


@pytest.mark.asyncio
async def test_get_or_create_tag_reuses_existing_tags(db_session: AsyncSession):
    first_call = await get_or_create_tag(db_session, ["food", "lifestyle"])
    first_ids = {t.name: t.id for t in first_call}

    second_call = await get_or_create_tag(db_session, ["food", "lifestyle"])
    second_ids = {t.name: t.id for t in second_call}

    assert first_ids == second_ids


@pytest.mark.asyncio
async def test_get_or_create_tag_partial_reuse(db_session: AsyncSession):
    existing = await get_or_create_tag(db_session, ["photography"])
    existing_id = existing[0].id

    tags = await get_or_create_tag(db_session, ["photography", "art"])
    names = {t.name for t in tags}
    ids_by_name = {t.name: t.id for t in tags}

    assert names == {"photography", "art"}
    assert ids_by_name["photography"] == existing_id


@pytest.mark.asyncio
async def test_get_or_create_tag_empty_list(db_session: AsyncSession):
    result = await get_or_create_tag(db_session, [])
    assert result == []

import pytest

from src.core.clarifai import index_image_bytes, delete_image, search_similar_images_by_id


@pytest.mark.asyncio
async def test_index_image_bytes(mocker):
    mocker.patch("src.core.clarifai.settings.clarifai_api_key", "test")
    mocker.patch("src.core.clarifai.settings.clarifai_app_id", "test")
    mocker.patch("src.core.clarifai.settings.clarifai_user_id", "test")
    mocker.patch("src.core.clarifai.httpx.AsyncClient")

    result = await index_image_bytes("test", b"test")

    assert result is None

@pytest.mark.asyncio
async def test_index_image_bytes_without_credentials(mocker):
    mocker.patch("src.core.clarifai.settings.clarifai_api_key", None)
    mocker.patch("src.core.clarifai.settings.clarifai_app_id", None)
    mocker.patch("src.core.clarifai.settings.clarifai_user_id", None)
    mocker.patch("src.core.clarifai.httpx.AsyncClient")

    result = await index_image_bytes("test", b"test")

    assert result is None

@pytest.mark.asyncio
async def test_delete_image(mocker):
    mocker.patch("src.core.clarifai.settings.clarifai_api_key", "test")
    mocker.patch("src.core.clarifai.settings.clarifai_app_id", "test")
    mocker.patch("src.core.clarifai.settings.clarifai_user_id", "test")
    mocker.patch("src.core.clarifai.httpx.AsyncClient")

    result = await delete_image("test")

    assert result is None

@pytest.mark.asyncio
async def test_delete_image_without_credentials(mocker):
    mocker.patch("src.core.clarifai.settings.clarifai_api_key", None)
    mocker.patch("src.core.clarifai.settings.clarifai_app_id", None)
    mocker.patch("src.core.clarifai.settings.clarifai_user_id", None)
    mocker.patch("src.core.clarifai.httpx.AsyncClient")

    result = await delete_image("test")

    assert result is None

@pytest.mark.asyncio
async def test_search_similar_images_by_id(mocker):
    mocker.patch("src.core.clarifai.settings.clarifai_api_key", "test")
    mocker.patch("src.core.clarifai.settings.clarifai_app_id", "test")
    mocker.patch("src.core.clarifai.settings.clarifai_user_id", "test")
    mocker.patch("src.core.clarifai.httpx.AsyncClient")

    result = await search_similar_images_by_id("test")

    assert result == []

@pytest.mark.asyncio
async def test_search_similar_images_by_id_without_credentials(mocker):
    mocker.patch("src.core.clarifai.settings.clarifai_api_key", None)
    mocker.patch("src.core.clarifai.settings.clarifai_app_id", None)
    mocker.patch("src.core.clarifai.settings.clarifai_user_id", None)
    mocker.patch("src.core.clarifai.httpx.AsyncClient")

    result = await search_similar_images_by_id("test")

    assert result == []

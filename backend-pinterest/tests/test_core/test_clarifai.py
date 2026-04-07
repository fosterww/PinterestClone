import pytest
from unittest.mock import AsyncMock, MagicMock
from core.infra.clarifai import ClarifaiService


@pytest.fixture
def mock_clarifai_service(mocker):
    mock_service = MagicMock()
    mock_service.index_image_bytes = AsyncMock()
    mock_service.delete_image = AsyncMock()
    mock_service.search_similar_images_by_id = AsyncMock()
    return mock_service


@pytest.mark.asyncio
async def test_index_image_bytes(mocker):
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient")
    service = ClarifaiService("test", "test", "test")
    result = await service.index_image_bytes("test", b"test")
    assert result is None


@pytest.mark.asyncio
async def test_index_image_bytes_without_credentials(mocker):
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient")
    service = ClarifaiService("", "", "")
    result = await service.index_image_bytes("test", b"test")
    assert result is None


@pytest.mark.asyncio
async def test_delete_image(mocker):
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient")
    service = ClarifaiService("test", "test", "test")
    result = await service.delete_image("test")
    assert result is None


@pytest.mark.asyncio
async def test_delete_image_without_credentials(mocker):
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient")
    service = ClarifaiService("", "", "")
    result = await service.delete_image("test")
    assert result is None


@pytest.mark.asyncio
async def test_search_similar_images_by_id(mocker):
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient")
    service = ClarifaiService("test", "test", "test")
    result = await service.search_similar_images_by_id("test")
    assert result == []


@pytest.mark.asyncio
async def test_search_similar_images_by_id_without_credentials(mocker):
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient")
    service = ClarifaiService("", "", "")
    result = await service.search_similar_images_by_id("test")
    assert result == []

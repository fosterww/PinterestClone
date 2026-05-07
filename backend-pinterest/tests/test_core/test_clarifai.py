from unittest.mock import AsyncMock, MagicMock

import pytest

from core.infra.clarifai import ClarifaiService


@pytest.mark.asyncio
async def test_index_image_bytes(mocker):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient", return_value=mock_client)
    service = ClarifaiService("test", "test", "test")
    result = await service.index_image_bytes("test", b"test")
    assert result is None


@pytest.mark.asyncio
async def test_index_image_bytes_without_credentials(mocker):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient", return_value=mock_client)
    service = ClarifaiService("", "", "")
    result = await service.index_image_bytes("test", b"test")
    assert result is None


@pytest.mark.asyncio
async def test_delete_image(mocker):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.delete = AsyncMock(return_value=mock_response)
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient", return_value=mock_client)
    service = ClarifaiService("test", "test", "test")
    result = await service.delete_image("test")
    assert result is None


@pytest.mark.asyncio
async def test_delete_image_without_credentials(mocker):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.delete = AsyncMock(return_value=mock_response)
    mocker.patch("src.core.infra.clarifai.httpx.AsyncClient", return_value=mock_client)
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

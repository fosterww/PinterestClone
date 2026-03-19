import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, UploadFile

from src.core.s3 import upload_image_to_s3


@pytest.fixture
def mock_s3_client():
    mock_s3_client = AsyncMock()
    mock_s3_client.put_object = AsyncMock()
    return mock_s3_client


@pytest.mark.asyncio
async def test_upload_image_to_s3_success(mock_s3_client):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "photo.png"
    mock_file.content_type = "image/png"
    mock_file.read = AsyncMock(return_value=b"fake_image_bytes")

    mock_session_instance = MagicMock()
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=False)
    mock_session_instance.client.return_value = mock_context_manager

    with patch("src.core.s3.aioboto3.Session", return_value=mock_session_instance):
        url = await upload_image_to_s3(mock_file)

    assert url.startswith("http")
    assert "pins/" in url
    assert url.endswith(".png")
    mock_s3_client.put_object.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_image_to_s3_no_extension(mock_s3_client):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "photo_no_ext"
    mock_file.content_type = "image/jpeg"
    mock_file.read = AsyncMock(return_value=b"fake_image_bytes")

    mock_session_instance = MagicMock()
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=False)
    mock_session_instance.client.return_value = mock_context_manager

    with patch("src.core.s3.aioboto3.Session", return_value=mock_session_instance):
        url = await upload_image_to_s3(mock_file)

    assert url.endswith(".jpg")


@pytest.mark.asyncio
async def test_upload_image_to_s3_failure(mock_s3_client):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "photo.png"
    mock_file.content_type = "image/png"
    mock_file.read = AsyncMock(return_value=b"fake_image_bytes")
    mock_s3_client.put_object = AsyncMock(side_effect=Exception("S3 down"))

    mock_session_instance = MagicMock()
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=False)
    mock_session_instance.client.return_value = mock_context_manager

    with patch("src.core.s3.aioboto3.Session", return_value=mock_session_instance):
        with pytest.raises(HTTPException) as excinfo:
            await upload_image_to_s3(mock_file)
        assert excinfo.value.status_code == 500
        assert "S3" in excinfo.value.detail

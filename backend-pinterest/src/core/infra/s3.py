import uuid

import aioboto3
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from fastapi import UploadFile, HTTPException, status

from core.config import settings


class S3Service:
    def __init__(self):
        self.session = aioboto3.Session()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def upload_image_to_s3(self, file: UploadFile) -> str:
        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        object_name = f"pins/{uuid.uuid4()}.{ext}"

        try:
            async with self.session.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                region_name=settings.s3_region,
            ) as s3_client:
                content = await file.read()

                await s3_client.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=object_name,
                    Body=content,
                    ContentType=file.content_type,
                )
                return f"{settings.s3_public_base_url}/{object_name}"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload image to S3: {str(e)}",
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def upload_bytes_to_s3(
        self,
        content: bytes,
        content_type: str = "image/png",
        folder: str = "generated",
        extension: str = "png",
    ) -> str:
        object_name = f"{folder}/{uuid.uuid4()}.{extension}"

        try:
            async with self.session.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                region_name=settings.s3_region,
            ) as s3_client:
                await s3_client.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=object_name,
                    Body=content,
                    ContentType=content_type,
                )
                return f"{settings.s3_public_base_url}/{object_name}"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload generated image to S3: {str(e)}",
            )

    async def download_bytes_from_url(self, url: str) -> bytes:
        if url.startswith(settings.s3_public_base_url):
            object_name = url.removeprefix(f"{settings.s3_public_base_url}/")
            try:
                async with self.session.client(
                    "s3",
                    endpoint_url=settings.s3_endpoint_url,
                    aws_access_key_id=settings.s3_access_key_id,
                    aws_secret_access_key=settings.s3_secret_access_key,
                    region_name=settings.s3_region,
                ) as s3_client:
                    response = await s3_client.get_object(
                        Bucket=settings.s3_bucket_name,
                        Key=object_name,
                    )
                    return await response["Body"].read()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download image from S3: {str(e)}",
                )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to download image: {str(e)}",
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def delete_bytes_from_s3(self, url: str) -> None:
        if url.startswith(settings.s3_public_base_url):
            object_name = url.removeprefix(f"{settings.s3_public_base_url}/")
            try:
                async with self.session.client(
                    "s3",
                    endpoint_url=settings.s3_endpoint_url,
                    aws_access_key_id=settings.s3_access_key_id,
                    aws_secret_access_key=settings.s3_secret_access_key,
                    region_name=settings.s3_region,
                ) as s3_client:
                    await s3_client.delete_object(
                        Bucket=settings.s3_bucket_name,
                        Key=object_name,
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete image from S3: {str(e)}",
                )

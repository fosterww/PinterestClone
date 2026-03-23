import asyncio
import base64

from src.core.celery import celery_app
from src.core.clarifai import get_clarifai_service


async def _index_image(pin_id: str, image_bytes: bytes):
    clarifai_service = await get_clarifai_service()
    try:
        await clarifai_service.index_image_bytes(pin_id, image_bytes)
    finally:
        await clarifai_service.close()

@celery_app.task(name="index_image_task", queue="default")
def index_image_task(pin_id: str, base64_image: str):
    image_bytes = base64.b64decode(base64_image)
    asyncio.run(_index_image(pin_id, image_bytes))

async def _delete_image(pin_id: str):
    clarifai_service = await get_clarifai_service()
    try:
        await clarifai_service.delete_image(pin_id)
    finally:
        await clarifai_service.close()

@celery_app.task(name="delete_image_task", queue="default")
def delete_image_task(pin_id: str):
    asyncio.run(_delete_image(pin_id))

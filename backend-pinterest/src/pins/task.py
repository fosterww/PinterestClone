import asyncio
import base64

from src.core.celery import celery_app
from src.core.clarifai import get_clarifai_service


@celery_app.task(name="index_image_task", queue="default")
def index_image_task(pin_id: str, base64_image: str):
    image_bytes = base64.b64decode(base64_image)
    clarifai_service = get_clarifai_service()
    asyncio.run(clarifai_service.index_image_bytes(pin_id, image_bytes))


@celery_app.task(name="delete_image_task", queue="default")
def delete_image_task(pin_id: str):
    clarifai_service = get_clarifai_service()
    asyncio.run(clarifai_service.delete_image(pin_id))

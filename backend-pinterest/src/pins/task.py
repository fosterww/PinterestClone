import asyncio
import base64

from src.core.celery import celery_app
from src.core.clarifai import index_image_bytes, delete_image


@celery_app.task(name="index_image_task", queue="default")
def index_image_task(pin_id: str, base64_image: str):
    image_bytes = base64.b64decode(base64_image)
    asyncio.run(index_image_bytes(pin_id, image_bytes))


@celery_app.task(name="delete_image_task", queue="default")
def delete_image_task(pin_id: str):
    asyncio.run(delete_image(pin_id))

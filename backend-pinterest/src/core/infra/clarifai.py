import base64
import httpx
from typing import List

from tenacity import retry, stop_after_attempt, wait_exponential
from core.logger import logger
from core.config import settings


class ClarifaiService:
    def __init__(self, api_key: str, app_id: str, user_id: str):
        self.api_key = api_key
        self.app_id = app_id
        self.user_id = user_id
        self.base_url = f"https://api.clarifai.com/v2/users/{user_id}/apps/{app_id}"
        self.headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def index_image_bytes(self, pin_id: str, image_bytes: bytes) -> None:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        url = f"{self.base_url}/inputs"

        payload = {
            "inputs": [{"id": str(pin_id), "data": {"image": {"base64": base64_image}}}]
        }

        try:
            response = await self.client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully indexed pin {pin_id}")
        except Exception as e:
            logger.error(f"Failed to index image in Clarifai: {e}")
            raise

    async def search_similar_images_by_id(self, pin_id: str) -> List[str]:
        url = f"{self.base_url}/annotations/searches"
        payload = {
            "searches": [
                {"query": {"ranks": [{"annotation": {"input_id": str(pin_id)}}]}}
            ]
        }

        try:
            response = await self.client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            hits = data.get("hits", [])
            similar_pin_ids = []
            if not hits:
                return []
            for hit in hits:
                hit_id = hit.get("input", {}).get("id")
                score = hit.get("score", 0)
                if hit_id and hit_id != str(pin_id) and score > 0.6:
                    similar_pin_ids.append(hit_id)
            return similar_pin_ids
        except Exception as e:
            logger.error(f"Failed to search similar images in Clarifai: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def delete_image(self, pin_id: str) -> None:
        url = f"{self.base_url}/inputs/{pin_id}"
        try:
            response = await self.client.delete(url, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Successfully deleted pin {pin_id}")
        except Exception as e:
            logger.error(f"Failed to delete image in Clarifai: {e}")
            raise


async def get_clarifai_service() -> ClarifaiService:
    return ClarifaiService(
        settings.clarifai_api_key, settings.clarifai_app_id, settings.clarifai_user_id
    )

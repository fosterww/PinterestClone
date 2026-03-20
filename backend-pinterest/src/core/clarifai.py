import base64
import httpx

from tenacity import retry, stop_after_attempt, wait_exponential
from src.core.logger import logger
from src.core.config import settings


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def index_image_bytes(pin_id: str, image_bytes: bytes) -> None:
    if not settings.clarifai_api_key or not settings.clarifai_app_id or not settings.clarifai_user_id:
        logger.warning("Clarifai credentials not set. Skipping image indexing.")
        return

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    url = f"https://api.clarifai.com/v2/users/{settings.clarifai_user_id}/apps/{settings.clarifai_app_id}/inputs"
    headers = {
        "Authorization": f"Key {settings.clarifai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": [
            {
                "id": str(pin_id),
                "data": {
                    "image": {
                        "base64": base64_image
                    }
                }
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            logger.info(f"Successfully indexed pin {pin_id} in Clarifai.")
    except Exception as e:
        logger.error(f"Failed to index image in Clarifai: {e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def delete_image(pin_id: str) -> None:
    if not settings.clarifai_api_key or not settings.clarifai_app_id or not settings.clarifai_user_id:
        return

    url = f"https://api.clarifai.com/v2/users/{settings.clarifai_user_id}/apps/{settings.clarifai_app_id}/inputs/{pin_id}"
    headers = {
        "Authorization": f"Key {settings.clarifai_api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers, timeout=10.0)
            if response.status_code != 404:
                response.raise_for_status()
                logger.info(f"Successfully deleted pin {pin_id} from Clarifai.")
    except Exception as e:
        logger.error(f"Failed to delete image in Clarifai: {e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def search_similar_images_by_id(pin_id: str) -> list[str]:
    if not settings.clarifai_api_key or not settings.clarifai_app_id or not settings.clarifai_user_id:
        return []

    url = f"https://api.clarifai.com/v2/users/{settings.clarifai_user_id}/apps/{settings.clarifai_app_id}/searches"
    headers = {
        "Authorization": f"Key {settings.clarifai_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": {
            "ranks": [
                {
                    "annotation": {
                        "data": {
                            "image": {
                                "id": str(pin_id)
                            }
                        }
                    }
                }
            ]
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("hits", [])
            similar_pin_ids = []
            for hit in hits:
                hit_id = hit.get("input", {}).get("id")
                score = hit.get("score", 0)
                if hit_id and hit_id != str(pin_id) and score > 0.6:
                    similar_pin_ids.append(hit_id)
            
            return similar_pin_ids
    except Exception as e:
        logger.error(f"Failed to search similar images in Clarifai: {e}")
        return []

from openai import OpenAI

from core.exception import AppError
from core.logger import logger


class OpenAIClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key, timeout=60.0, max_retries=2)

    def generate_image(self, prompt: str, number_of_images: int = 1):
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=number_of_images,
                size="1024x1024",
            )
            return response.data
        except Exception as exc:
            logger.exception("OpenAI image generation failed")
            raise AppError(detail="Failed to generate image") from exc

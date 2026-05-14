from typing import Literal, TypeAlias

from openai import APITimeoutError, OpenAI
from openai import RateLimitError as OpenAIRateLimitError

from core.exception import AITimeoutError, ProviderError, RateLimitError
from core.logger import logger

OpenAIImageSize: TypeAlias = Literal[
    "1024x1024",
    "1024x1536",
    "1024x1792",
    "1536x1024",
    "1792x1024",
    "256x256",
    "512x512",
]


class OpenAIClient:
    IMAGE_MODEL = "dall-e-3"

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key, timeout=60.0, max_retries=2)

    def generate_image(
        self,
        prompt: str,
        number_of_images: int = 1,
        aspect_ratio: Literal["1:1", "16:9", "9:16"] | None = "1:1",
    ):
        try:
            response = self.client.images.generate(
                model=self.IMAGE_MODEL,
                prompt=prompt,
                n=number_of_images,
                size=self._size_from_aspect_ratio(aspect_ratio),
            )
            return response.data
        except OpenAIRateLimitError as exc:
            logger.exception("OpenAI image generation rate limited")
            raise RateLimitError("AI provider rate limit exceeded") from exc
        except APITimeoutError as exc:
            logger.exception("OpenAI image generation timed out")
            raise AITimeoutError("AI provider request timed out") from exc
        except Exception as exc:
            logger.exception("OpenAI image generation failed")
            raise ProviderError(detail="Failed to generate image") from exc

    def _size_from_aspect_ratio(
        self, aspect_ratio: Literal["1:1", "16:9", "9:16"] | None
    ) -> OpenAIImageSize:
        mapping: dict[str, OpenAIImageSize] = {
            "16:9": "1792x1024",
            "9:16": "1024x1792",
            "1:1": "1024x1024",
        }
        return mapping.get(aspect_ratio or "1:1", "1024x1024")

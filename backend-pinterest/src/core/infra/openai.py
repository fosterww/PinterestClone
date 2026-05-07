from typing import Literal

from openai import APITimeoutError, OpenAI, RateLimitError as OpenAIRateLimitError

from core.exception import AITimeoutError, ProviderError, RateLimitError
from core.logger import logger


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
    ) -> str:
        if aspect_ratio == "16:9":
            return "1792x1024"
        if aspect_ratio == "9:16":
            return "1024x1792"
        return "1024x1024"

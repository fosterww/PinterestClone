from google import genai
from google.genai import types

from ai.prompts import build_description_generation_prompt, build_tag_generation_prompt
from core.config import settings
from core.logger import logger


class GeminiService:
    MODEL = "gemini-2.5-flash-lite"

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def generate_tags(
        self, image_bytes: bytes, title: str, description: str | None
    ) -> list[str] | None:
        prompt = build_tag_generation_prompt(title, description, image_bytes)

        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=prompt.content,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            if response.text is None:
                return None
            tags = response.text.strip()
            if isinstance(tags, list):
                return [str(tag).strip() for tag in tags if str(tag).strip()]
        except Exception:
            logger.exception("Gemini tag generation failed")
        return None

    def generate_description(self, image_bytes: bytes, title: str) -> str | None:
        prompt = build_description_generation_prompt(title, image_bytes)

        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=prompt.content,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain",
                ),
            )
            return response.text.strip() if response.text else None
        except Exception:
            logger.exception("Gemini description generation failed")
        return None

import json
from typing import List

from google import genai
from google.genai import types

from core.config import settings


class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def generate_tags(
        self, image_bytes: bytes, title: str, description: str
    ) -> List[str]:
        desc_text = description if description else "No description"
        prompt_parts = [
            f"Title: {title}",
            f"Description: {desc_text}",
            'Task: Analyze the image based on the title and description provided above. Return ONLY a JSON list of plain 4-5 strings that represent relevant tags or categories for this image. Do not include any nested objects, just a simple list of strings like ["tag1", "tag2"]. Do not include any other text.',
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ]

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt_parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            text = response.text.strip()
            tags = json.loads(text)
            if isinstance(tags, list):
                valid_tags = [str(t).strip() for t in tags if str(t).strip()]
                return valid_tags
        except Exception:
            pass
        return []

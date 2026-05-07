from dataclasses import dataclass
from typing import Any

from google.genai import types

from ai.schemas import GenerateImageRequest


IMAGE_GENERATION_PROMPT_NAME = "image_generation"
IMAGE_GENERATION_PROMPT_VERSION = "image_generation_v1"
TAG_GENERATION_PROMPT_NAME = "tag_generation"
TAG_GENERATION_PROMPT_VERSION = "tag_generation_v1"
DESCRIPTION_GENERATION_PROMPT_NAME = "description_generation"
DESCRIPTION_GENERATION_PROMPT_VERSION = "description_generation_v1"


@dataclass(frozen=True)
class BuiltPrompt:
    name: str
    version: str
    content: str | list[Any]
    input_parameters: dict[str, Any]


def build_image_generation_prompt(data: GenerateImageRequest) -> BuiltPrompt:
    prompt = data.prompt
    requirements: list[str] = []
    if data.style:
        requirements.append(f"Style: {data.style}")
    if data.aspect_ratio:
        requirements.append(f"Target aspect ratio: {data.aspect_ratio}")
    if data.negative_prompt:
        requirements.append(f"Avoid: {data.negative_prompt}")
    if data.seed is not None:
        requirements.append(f"Use seed {data.seed} if supported by the model")

    if requirements:
        formatted_requirements = "\n".join(f"- {item}" for item in requirements)
        prompt = f"{prompt}\n\nAdditional requirements:\n{formatted_requirements}"

    return BuiltPrompt(
        name=IMAGE_GENERATION_PROMPT_NAME,
        version=IMAGE_GENERATION_PROMPT_VERSION,
        content=prompt,
        input_parameters=data.model_dump(mode="json"),
    )


def build_tag_generation_prompt(
    title: str,
    description: str | None,
    image_bytes: bytes,
) -> BuiltPrompt:
    desc_text = description or "No description"
    parts = [
        f"Title: {title}",
        f"Description: {desc_text}",
        (
            "Task: Analyze the image based on the title and description. "
            "Return ONLY a JSON list of 4-5 plain strings that represent relevant "
            'tags or categories, for example ["tag1", "tag2"].'
        ),
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
    ]
    return BuiltPrompt(
        name=TAG_GENERATION_PROMPT_NAME,
        version=TAG_GENERATION_PROMPT_VERSION,
        content=parts,
        input_parameters={
            "title": title,
            "description": description,
            "image_bytes_length": len(image_bytes),
        },
    )


def build_description_generation_prompt(title: str, image_bytes: bytes) -> BuiltPrompt:
    parts = [
        f"Title: {title}",
        (
            "Task: Analyze the image based on the title. Return ONLY a plain text "
            "description of the image in 1-2 sentences. Do not include any other text."
        ),
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
    ]
    return BuiltPrompt(
        name=DESCRIPTION_GENERATION_PROMPT_NAME,
        version=DESCRIPTION_GENERATION_PROMPT_VERSION,
        content=parts,
        input_parameters={
            "title": title,
            "image_bytes_length": len(image_bytes),
        },
    )

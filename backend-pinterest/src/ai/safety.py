from core.exception import BadRequestError

BLOCKED_TERMS = {
    "child sexual",
    "minor nude",
    "graphic gore",
    "terrorist propaganda",
    "suicide",
    "self-harm",
    "hate speech",
    "violence",
    "sexual content",
    "nudity",
    "drugs",
    "alcohol",
}


def validate_image_prompt(prompt: str) -> None:
    normalized = " ".join(prompt.lower().split())

    for term in BLOCKED_TERMS:
        if term in normalized:
            raise BadRequestError(detail="Prompt violates image generation policy")

from fastapi import HTTPException, status

from src.core.config import settings

MAX_INPUT_CHARS = settings.max_input_chars


def sanitize_prompt(prompt: str) -> str:
    """Security layer for protecting the LLM from basic injection and limits."""
    if not prompt or not prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty"
        )

    max_chars = settings.max_input_chars
    if len(prompt) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt exceeds maximum character limit of {max_chars}",
        )

    # Basic sanitization: strip null bytes
    sanitized = prompt.replace("\x00", "")

    return sanitized.strip()

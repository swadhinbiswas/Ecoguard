from fastapi import HTTPException, status

MAX_INPUT_CHARS = 4000


def sanitize_prompt(prompt: str) -> str:
    """Security layer for protecting the LLM from basic injection and limits."""
    if not prompt or not prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty"
        )

    if len(prompt) > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt exceeds maximum character limit of {MAX_INPUT_CHARS}",
        )

    # Basic sanitization: strip null bytes
    sanitized = prompt.replace("\x00", "")

    return sanitized.strip()

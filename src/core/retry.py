import asyncio
import time
from functools import wraps
from typing import Callable, TypeVar
from src.core.config import settings
from src.core.logging import logger

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_retries: int | None = None,
    base_delay: float | None = None,
    **kwargs,
) -> T:
    max_retries = max_retries if max_retries is not None else settings.db_max_retries
    base_delay = base_delay if base_delay is not None else settings.db_retry_base_delay

    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")

    raise last_exception  # type: ignore[misc]


def async_retry(max_retries: int | None = None, base_delay: float | None = None):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func, *args, max_retries=max_retries, base_delay=base_delay, **kwargs
            )

        return wrapper

    return decorator

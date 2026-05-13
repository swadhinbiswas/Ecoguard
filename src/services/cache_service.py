import asyncio
import hashlib
import time
from typing import Optional

from src.core.config import settings
from src.core.logging import logger


class InferenceCache:
    def __init__(self, ttl: int = 300, max_entries: int = 1000):
        self.ttl = ttl
        self.max_entries = max_entries
        self._cache: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _make_key(prompt: str, max_tokens: int, temperature: float) -> str:
        raw = f"{len(prompt)}:{prompt}:{max_tokens}:{temperature:.2f}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> Optional[str]:
        if not settings.cache_enabled:
            return None
        key = self._make_key(prompt, max_tokens, temperature)
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            ts, output = entry
            if time.monotonic() - ts > self.ttl:
                del self._cache[key]
                return None
            logger.debug(f"Cache hit for key {key[:12]}...")
            return output

    async def set(
        self, prompt: str, max_tokens: int, temperature: float, output: str
    ) -> None:
        if not settings.cache_enabled:
            return
        key = self._make_key(prompt, max_tokens, temperature)
        async with self._lock:
            self._cache[key] = (time.monotonic(), output)
            if len(self._cache) > self.max_entries:
                oldest = min(self._cache.items(), key=lambda x: x[1][0])
                del self._cache[oldest[0]]

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


inference_cache = InferenceCache(
    ttl=settings.cache_ttl_seconds,
    max_entries=settings.cache_max_entries,
)

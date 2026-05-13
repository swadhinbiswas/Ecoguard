"""Semantic caching with cosine similarity for prompt deduplication."""

import asyncio
import hashlib
import math
import time
from typing import Optional

from src.core.config import settings
from src.core.logging import logger
from src.services.chat_service import EmbeddingService


class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.92, max_entries: int = 5000):
        self.threshold = similarity_threshold
        self.max_entries = max_entries
        self._cache: dict[str, tuple[float, str, list[float]]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def get(self, prompt: str) -> Optional[str]:
        if not settings.cache_enabled:
            return None

        try:
            embeddings = EmbeddingService.create_embeddings_sync(prompt)
            if not embeddings:
                return None

            async with self._lock:
                best_score = 0.0
                best_output: Optional[str] = None
                now = time.monotonic()

                to_evict: list[str] = []
                for key, (ts, output, cached_emb) in self._cache.items():
                    if now - ts > settings.cache_ttl_seconds:
                        to_evict.append(key)
                        continue
                    score = self._cosine_similarity(embeddings, cached_emb)
                    if score > best_score:
                        best_score = score
                        best_output = output

                for key in to_evict:
                    del self._cache[key]

                if best_score >= self.threshold and best_output is not None:
                    key = hashlib.sha256(prompt.encode()).hexdigest()
                    self._cache[key] = (now, best_output, embeddings)
                    logger.debug(f"Semantic cache hit: {best_score:.3f}")
                    return best_output

        except Exception as e:
            logger.debug(f"Semantic cache lookup failed: {e}")

        return None

    async def set(self, prompt: str, output: str) -> None:
        if not settings.cache_enabled:
            return

        try:
            embeddings = EmbeddingService.create_embeddings_sync(prompt)
            if not embeddings:
                return

            async with self._lock:
                key = hashlib.sha256(prompt.encode()).hexdigest()
                self._cache[key] = (time.monotonic(), output, embeddings)

                if len(self._cache) > self.max_entries:
                    oldest = min(self._cache.items(), key=lambda x: x[1][0])
                    del self._cache[oldest[0]]

        except Exception as e:
            logger.debug(f"Semantic cache store failed: {e}")

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


semantic_cache = SemanticCache()

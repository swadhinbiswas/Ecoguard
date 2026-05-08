import time
import asyncio
from collections import defaultdict
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.config import settings
from src.monitoring.metrics import record_rate_limit


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> tuple[bool, float]:
        now = time.monotonic()
        async with self._lock:
            timestamps = self._buckets[key]
            cutoff = now - self.window_seconds
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)
            if len(timestamps) >= self.max_requests:
                if timestamps:
                    retry_after = timestamps[0] + self.window_seconds - now
                else:
                    retry_after = self.window_seconds
                return False, max(1.0, retry_after)
            timestamps.append(now)
            return True, 0.0

    async def cleanup(self) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds * 2
        async with self._lock:
            expired = [k for k, v in self._buckets.items() if not v or v[-1] < cutoff]
            for k in expired:
                del self._buckets[k]


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowRateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or SlidingWindowRateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        if request.url.path in ("/metrics", "/health", "/api/v1/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = await self.limiter.is_allowed(client_ip)

        if not allowed:
            record_rate_limit()
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Limit": str(self.limiter.max_requests),
                },
            )

        return await call_next(request)


_rate_limiter: SlidingWindowRateLimiter | None = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlidingWindowRateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
    return _rate_limiter

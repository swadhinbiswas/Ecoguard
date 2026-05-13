import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings
from src.monitoring.metrics import record_rate_limit

logger = logging.getLogger(__name__)


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


class RedisRateLimiter:
    LUA_CHECK = """
    local key = KEYS[1]
    local max_requests = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local cutoff = now - window

    redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
    local count = redis.call('ZCARD', key)

    if count >= max_requests then
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = window
        if #oldest > 0 then
            retry_after = tonumber(oldest[2]) + window - now
        end
        return {0, math.max(1, math.ceil(retry_after))}
    end

    redis.call('ZADD', key, now, now .. ':' .. count)
    redis.call('EXPIRE', key, math.ceil(window * 2))
    return {1, 0}
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._sha: str | None = None

    async def _get_redis(self):
        from src.core.redis import get_redis

        return await get_redis()

    async def is_allowed(self, key: str) -> tuple[bool, float]:
        redis = await self._get_redis()
        if redis is None:
            return True, 0.0

        now = time.monotonic()
        try:
            if self._sha is None:
                self._sha = await redis.script_load(self.LUA_CHECK)
            result = await redis.evalsha(
                self._sha,
                1,
                f"ratelimit:{key}",
                self.max_requests,
                self.window_seconds,
                now,
            )
            return bool(result[0]), float(result[1])
        except Exception:
            import logging

            logging.getLogger("eco-guard").warning(
                "Redis rate limiter failed, falling back to in-memory"
            )
            return self._in_memory_check(key)

    async def cleanup(self) -> None:
        pass


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        limiter: SlidingWindowRateLimiter | None = None,
        redis_limiter: RedisRateLimiter | None = None,
    ):
        super().__init__(app)
        self.limiter = limiter or SlidingWindowRateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
        self.redis_limiter = redis_limiter or RedisRateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        if request.url.path in ("/metrics", "/health", "/api/v1/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        from src.core.redis import redis_enabled

        if redis_enabled():
            allowed, retry_after = await self.redis_limiter.is_allowed(client_ip)
        else:
            allowed, retry_after = await self.limiter.is_allowed(client_ip)

        if not allowed:
            record_rate_limit()
            return Response(
                content='{"error":{"code":"RATE_LIMITED","message":"Rate limit exceeded"}}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Limit": str(
                        self.redis_limiter.max_requests
                        if redis_enabled()
                        else self.limiter.max_requests
                    ),
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

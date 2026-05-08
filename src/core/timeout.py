import asyncio
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.config import settings
from src.core.logging import logger


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: int | None = None):
        super().__init__(app)
        self.timeout = timeout_seconds or settings.request_timeout_seconds
        self._skip_paths = {"/metrics", "/api/v1/health", "/api/v1/ready"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self._skip_paths:
            return await call_next(request)

        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"Request timeout after {self.timeout}s: {request.method} {request.url.path}"
            )
            return Response(
                content='{"detail":"Request timeout"}',
                status_code=504,
                media_type="application/json",
            )

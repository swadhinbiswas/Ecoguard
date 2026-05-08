from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings

SAFE_DEMO_POST_PATHS = {
    "/api/v1/auth/login",
}

INFERENCE_PATHS = {
    "/api/v1/predict",
    "/api/v1/predict/stream",
}


class DemoModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.demo_mode or not settings.demo_read_only:
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()

        if method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        if path in SAFE_DEMO_POST_PATHS:
            return await call_next(request)
        if settings.demo_allow_inference and path in INFERENCE_PATHS:
            return await call_next(request)

        return Response(
            content=(
                '{"error":{"code":"DEMO_READ_ONLY",'
                '"message":"This public demo is read-only. Self-host Eco-Guard to make changes."}}'
            ),
            status_code=403,
            media_type="application/json",
        )

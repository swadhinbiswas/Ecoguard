import secrets
import time
import jwt
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.config import settings
from src.core.logging import logger

PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
    "/api/v1/health",
    "/api/v1/ready",
    "/dashboard/login",
    "/static/",
    "/api/v1/auth/login",
    "/api/v1/auth/status",
}


def create_token(sub: str = "admin", role: str = "admin") -> str:
    exp = int(time.time()) + settings.jwt_expire_minutes * 60
    return jwt.encode(
        {"sub": sub, "role": role, "exp": exp, "iat": int(time.time())},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def verify_request(request: Request) -> dict | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return decode_token(auth[7:])

    token = request.cookies.get("eco_guard_token")
    if token:
        return decode_token(token)

    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if api_key and api_key in set(settings.api_keys):
        return {"sub": "api-key", "role": "admin"}

    return None


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, require_auth: bool = True):
        super().__init__(app)
        self.require_auth = require_auth

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if not self.require_auth:
            return await call_next(request)

        for public in PUBLIC_PATHS:
            if path.startswith(public):
                return await call_next(request)

        user = verify_request(request)
        if user is None:
            if path.startswith("/dashboard") and "text/html" in request.headers.get(
                "Accept", ""
            ):
                return RedirectResponse(
                    url="/dashboard/login?redirect=" + path, status_code=302
                )
            return Response(
                content='{"error":{"code":"UNAUTHORIZED","message":"Missing or invalid authentication"}}',
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.user = user
        return await call_next(request)


class APIKeyStore:
    def __init__(self, keys: set[str] | None = None):
        self._keys: set[str] = keys or set()

    def validate(self, key: str) -> bool:
        return key in self._keys

    def add_key(self, key: str) -> None:
        self._keys.add(key)

    def revoke_key(self, key: str) -> None:
        self._keys.discard(key)

    def generate_key(self) -> str:
        key = f"eg-{secrets.token_urlsafe(32)}"
        self._keys.add(key)
        return key

    @property
    def key_count(self) -> int:
        return len(self._keys)


_api_key_store: APIKeyStore | None = None


def get_api_key_store() -> APIKeyStore:
    global _api_key_store
    if _api_key_store is None:
        _api_key_store = APIKeyStore()
    return _api_key_store

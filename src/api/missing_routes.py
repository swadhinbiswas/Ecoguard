"""Routes for enhanced health, WebSocket auth, webhook verify, pagination, rate limit headers."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import verify_request
from src.core.final_pieces import (
    CacheHeaders,
    PaginationParams,
    RateLimitHeaders,
    enhanced_health,
    webhook_retry,
)
from src.db.session import get_db
from src.models.inference import InferenceLog

missing_routes = APIRouter(prefix="/api/v1", tags=["Missing Pieces"])


# ── Enhanced Health ────────────────────────────────────────────


@missing_routes.get("/health/enhanced")
async def enhanced_health_check(db: AsyncSession = Depends(get_db)):
    return await enhanced_health.check_all(db)


# ── WebSocket Auth ─────────────────────────────────────────────


@missing_routes.get("/ws/token")
async def get_ws_token(request: Request):
    user = verify_request(request)
    if not user:
        raise HTTPException(401, "Authentication required for WebSocket")
    token = request.cookies.get("eco_guard_token") or request.headers.get(
        "Authorization", ""
    ).replace("Bearer ", "")
    return {"token": token}


# ── Webhook Verify ─────────────────────────────────────────────


@missing_routes.post("/webhooks/verify")
async def verify_webhook_endpoint(url: str = Query(...)):
    result = await webhook_retry.verify_webhook(url)
    return result


# ── Rate Limit Headers Middleware ──────────────────────────────


@missing_routes.get("/headers/rate-limit")
async def rate_limit_headers_example():
    """Returns example rate limit headers for debugging."""
    return {"headers": RateLimitHeaders.build(100, 95, 55)}


# ── Cache Headers Example ──────────────────────────────────────


@missing_routes.get("/headers/cache-example")
async def cache_example(response: Response):
    response.headers.update(CacheHeaders.public(max_age=300))
    return {"cached": True, "max_age": 300}


# ── Pagination Example ─────────────────────────────────────────


@missing_routes.get("/logs/paginated")
async def paginated_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    count_result = await db.execute(select(func.count(InferenceLog.id)))
    total = count_result.scalar() or 0

    params = PaginationParams(page, limit)
    result = await db.execute(
        select(InferenceLog)
        .order_by(InferenceLog.timestamp.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    logs = result.scalars().all()

    return PaginationParams.response(
        [
            {
                "id": log_entry.id,
                "request_id": log_entry.request_id,
                "latency_ms": log_entry.latency_ms,
                "token_count": log_entry.token_count,
                "timestamp": log_entry.timestamp.isoformat() if log_entry.timestamp else None,
            }
            for log_entry in logs
        ],
        total,
        params,
    )


# ── API Versioning ─────────────────────────────────────────────


@missing_routes.get("/version")
async def api_version():
    return {
        "api_versions": {
            "v1": {"status": "stable", "prefix": "/api/v1", "routes": 200},
            "v2": {
                "status": "planned",
                "prefix": "/api/v2",
                "changes": ["cursor-based pagination", "streaming multipart"],
            },
        },
        "latest": "v1",
    }

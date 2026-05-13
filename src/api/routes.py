from datetime import datetime, timedelta, timezone
from hashlib import scrypt

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import create_token, verify_request
from src.core.backend import get_backend
from src.core.config import settings
from src.core.exceptions import (
    InferenceError,
    ModelNotFoundError,
    ModelNotLoadedError,
)
from src.core.logging import logger
from src.core.security import sanitize_prompt
from src.db.database import check_db_health
from src.db.session import get_db
from src.models.inference import InferenceLog
from src.models.schemas import (
    ErrorResponse,
    HealthResponse,
    LoginRequest,
    MetricsSummaryResponse,
    PredictionRequest,
    PredictionResponse,
    SystemStatusResponse,
)
from src.monitoring.metrics import record_inference
from src.services.cache_service import inference_cache
from src.services.drift_detector import drift_detector
from src.services.inference_service import InferenceService
from src.services.streaming_service import StreamingInferenceService

router = APIRouter(prefix="/api/v1")


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, bytes]:
    salt = salt or __import__("os").urandom(16)
    hashed = scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return hashed.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: bytes) -> bool:
    computed, _ = _hash_password(password, salt)
    return computed == stored_hash


def _setup_required() -> list[str]:
    required: list[str] = []
    if settings.auth_enabled:
        if not settings.admin_username or not settings.admin_password:
            required.append("Set ADMIN_USERNAME and ADMIN_PASSWORD")
        if not settings.jwt_secret or len(settings.jwt_secret) < 32:
            required.append("Set a JWT_SECRET with at least 32 characters")
    if settings.environment == "production" and settings.cors_origins == ["*"]:
        required.append("Restrict CORS_ORIGINS for production")
    if settings.environment == "production" and not settings.database_url.startswith(
        "postgresql+asyncpg://"
    ):
        required.append("Configure a PostgreSQL DATABASE_URL")
    return required


@router.get(
    "/system/status",
    response_model=SystemStatusResponse,
    tags=["System"],
)
async def system_status():
    setup_required = _setup_required()
    return SystemStatusResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        demo_mode=settings.demo_mode,
        demo_read_only=settings.demo_read_only,
        auth_enabled=settings.auth_enabled,
        first_run=bool(setup_required),
        setup_required=setup_required,
    )


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    db_healthy = await check_db_health()
    model_info = get_backend().info
    overall = "healthy" if db_healthy else "degraded"

    return HealthResponse(
        status=overall,
        service="eco-guard",
        version=settings.app_version,
        checks={
            "database": "up" if db_healthy else "down",
            "model": "loaded" if model_info["loaded"] else "not_loaded",
        },
    )


@router.get("/ready", tags=["System"])
async def readiness_check():
    if not get_backend().is_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


@router.post(
    "/predict",
    response_model=PredictionResponse,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["Inference"],
)
async def predict(
    request_data: PredictionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        request_data.prompt = sanitize_prompt(request_data.prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sanitization error: {e}")
        raise HTTPException(status_code=400, detail="Invalid prompt")

    try:
        response = await InferenceService.generate(request_id, request_data, db)
        return response
    except ModelNotLoadedError as e:
        raise HTTPException(status_code=503, detail=str(e.detail).replace('/','')[:200])
    except ModelNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e.detail).replace('/','')[:200])
    except InferenceError as e:
        record_inference(0, 0, success=False)
        raise HTTPException(status_code=500, detail=str(e.detail).replace('/','')[:200])
    except Exception as e:
        record_inference(0, 0, success=False)
        logger.error(f"Unexpected inference error: {e}")
        raise HTTPException(status_code=500, detail="Internal inference error")


@router.post(
    "/predict/stream",
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["Inference"],
)
async def predict_stream(
    request_data: PredictionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        request_data.prompt = sanitize_prompt(request_data.prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sanitization error: {e}")
        raise HTTPException(status_code=400, detail="Invalid prompt")

    try:
        if not get_backend().is_loaded():
            raise HTTPException(status_code=503, detail="Model not loaded")

        return StreamingResponse(
            StreamingInferenceService.generate_stream(request_id, request_data, db),
            media_type="text/event-stream",
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    except ModelNotLoadedError as e:
        raise HTTPException(status_code=503, detail=str(e.detail).replace('/','')[:200])
    except Exception as e:
        logger.error(f"Streaming inference error: {e}")
        raise HTTPException(status_code=500, detail="Internal inference error")


@router.get("/models", tags=["System"])
async def list_models():
    return {"models": get_backend().info, "cache_size": inference_cache.size}


@router.get(
    "/metrics/summary", response_model=MetricsSummaryResponse, tags=["Observability"]
)
async def metrics_summary():
    return MetricsSummaryResponse(
        model_loaded=get_backend().is_loaded(),
        cache_enabled=settings.cache_enabled,
        cache_size=inference_cache.size,
        rate_limit_enabled=settings.rate_limit_enabled,
        drift_samples=len(drift_detector._latency_history),
    )


# --- Admin Endpoints ---


@router.get("/admin/logs", tags=["Admin"])
async def list_inference_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    hours: int = Query(24, ge=1, le=720),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(InferenceLog)
        .where(InferenceLog.timestamp >= cutoff)
        .order_by(desc(InferenceLog.timestamp))
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()

    count_result = await db.execute(
        select(func.count(InferenceLog.id)).where(InferenceLog.timestamp >= cutoff)
    )
    total = count_result.scalar() or 0

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": log.id,
                "request_id": log.request_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "latency_ms": log.latency_ms,
                "token_count": log.token_count,
                "drift_score": log.drift_score,
            }
            for log in logs
        ],
    }


@router.get("/admin/stats", tags=["Admin"])
async def inference_stats(
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=720),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(
            func.count(InferenceLog.id).label("total_requests"),
            func.avg(InferenceLog.latency_ms).label("avg_latency_ms"),
            func.avg(InferenceLog.token_count).label("avg_tokens"),
            func.max(InferenceLog.latency_ms).label("max_latency_ms"),
            func.avg(InferenceLog.drift_score).label("avg_drift"),
        ).where(InferenceLog.timestamp >= cutoff)
    )
    row = result.one_or_none()

    return {
        "period_hours": hours,
        "total_requests": int(row.total_requests) if row and row.total_requests else 0,
        "avg_latency_ms": round(float(row.avg_latency_ms), 2)
        if row and row.avg_latency_ms
        else 0.0,
        "avg_tokens": round(float(row.avg_tokens), 2)
        if row and row.avg_tokens
        else 0.0,
        "max_latency_ms": round(float(row.max_latency_ms), 2)
        if row and row.max_latency_ms
        else 0.0,
        "avg_drift": round(float(row.avg_drift), 4) if row and row.avg_drift else 0.0,
    }


@router.delete("/admin/cache", tags=["Admin"])
async def clear_cache():
    await inference_cache.clear()
    return {"message": "Cache cleared", "cache_size": inference_cache.size}


# ── Auth ────────────────────────────────────────────────────────


_login_attempts: dict[str, list[float]] = {}
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 300


@router.post("/auth/login")
async def login(credentials: LoginRequest, response: Response, request: Request):
    now = datetime.now(timezone.utc).timestamp()

    client_ip = request.client.host if request.client else "unknown"
    if client_ip not in _login_attempts:
        _login_attempts[client_ip] = []
    _login_attempts[client_ip] = [
        t for t in _login_attempts[client_ip] if now - t < _LOGIN_WINDOW_SECONDS
    ]
    if len(_login_attempts[client_ip]) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )

    if (
        settings.demo_mode
        and credentials.username == settings.demo_username
        and credentials.password == settings.demo_password
    ):
        token = create_token(sub=credentials.username, role="viewer")
        return _set_auth_response(token, "viewer", response)

    admin_hash, admin_salt = _hash_password(settings.admin_password)
    if credentials.username == settings.admin_username and _verify_password(
        credentials.password, admin_hash, admin_salt
    ):
        _login_attempts.pop(client_ip, None)
        token = create_token(sub=credentials.username, role="admin")
        return _set_auth_response(token, "admin", response)

    _login_attempts[client_ip].append(now)
    raise HTTPException(status_code=401, detail="Invalid credentials")


def _set_auth_response(token: str, role: str, response: Response) -> dict:
    response.set_cookie(
        key="eco_guard_token",
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return {"access_token": token, "token_type": "bearer", "role": role}


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="eco_guard_token",
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
    )
    return {"message": "Logged out"}


@router.get("/auth/status")
async def auth_status(request: Request):
    user = verify_request(request)
    if user:
        return {
            "authenticated": True,
            "user": user["sub"],
            "role": user.get("role", "viewer"),
        }
    return {"authenticated": False, "user": None}

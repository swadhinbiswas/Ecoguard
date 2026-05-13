import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.advanced_routes import advanced_router
from src.api.dashboard_data_routes import dashboard_data_router
from src.api.enterprise_routes import enterprise_router
from src.api.finals_routes import finals_router
from src.api.gap_routes import final_features_router
from src.api.missing_routes import missing_routes
from src.api.mlops_routes import mlops_router
from src.api.openai_routes import openai_router
from src.api.polish_routes import polish_router
from src.api.production_routes import production_router
from src.api.routes import router
from src.api.toolkit_routes import toolkit_router
from src.api.websocket import metrics_broadcast_loop, ws_router
from src.core.auth import AuthMiddleware, get_api_key_store
from src.core.backend import get_backend, init_backend, shutdown_backend
from src.core.concurrency import inference_limiter
from src.core.config import settings, validate_production_settings
from src.core.demo import DemoModeMiddleware
from src.core.error_codes import ErrorCode
from src.core.logging import logger
from src.core.middleware import RequestLoggingMiddleware
from src.core.rate_limiter import RateLimitMiddleware
from src.core.timeout import TimeoutMiddleware
from src.core.tracing import setup_tracing
from src.db.database import check_db_health, close_db, init_db
from src.mlops.scheduler import scheduler
from src.monitoring.metrics import PrometheusMetricsMiddleware, metrics_endpoint
from src.services.background import background_runner

limiter = Limiter(key_func=get_remote_address)
_shutting_down = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _shutting_down
    validate_production_settings()
    logger.info(
        f"Starting Eco-Guard API v{settings.app_version} [{settings.environment}]"
    )

    if settings.auto_migrate:
        try:
            from alembic.config import Config

            from alembic import command

            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations applied")
        except Exception as e:
            logger.warning(f"Auto-migration skipped: {e}")

    await init_db()

    if settings.auth_enabled and settings.api_keys:
        store = get_api_key_store()
        for key in settings.api_keys:
            store.add_key(key)

    asyncio.create_task(metrics_broadcast_loop())
    asyncio.create_task(scheduler.start())

    try:
        init_backend()
        logger.info(f"Backend initialized: {settings.backend}")
    except Exception as e:
        logger.warning(f"Could not initialize backend: {e}")

    yield

    _shutting_down = True
    logger.info(
        f"Shutting down — draining requests (timeout={settings.shutdown_drain_timeout}s)..."
    )
    await asyncio.sleep(settings.shutdown_drain_timeout)
    await scheduler.stop()
    await background_runner.shutdown(timeout=5.0)
    shutdown_backend()
    await close_db()


app = FastAPI(
    title="Eco-Guard",
    description="Production-grade LLM inference gateway and MLOps platform",
    version=settings.app_version,
    lifespan=lifespan,
    default_response_class=JSONResponse,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "System", "description": "Health, readiness, and system information"},
        {"name": "Inference", "description": "LLM inference and streaming endpoints"},
        {"name": "Observability", "description": "Metrics and monitoring"},
        {
            "name": "Admin",
            "description": "Administrative endpoints for log analysis and cache management",
        },
    ],
)

setup_tracing(app)


@app.middleware("http")
async def shutdown_middleware(request: Request, call_next):
    if _shutting_down:
        return JSONResponse(
            status_code=503,
            content={"detail": "Server is shutting down"},
            headers={"Connection": "close"},
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-Process-Time-Ms",
        "X-RateLimit-Limit",
        "X-API-Key",
    ],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(TimeoutMiddleware, timeout_seconds=settings.request_timeout_seconds)
app.add_middleware(GZipMiddleware, minimum_size=500)

if settings.metrics_enabled:
    app.add_middleware(PrometheusMetricsMiddleware)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware, require_auth=settings.auth_enabled)
app.add_middleware(DemoModeMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)
app.include_router(mlops_router)
app.include_router(openai_router)
app.include_router(enterprise_router)
app.include_router(finals_router)
app.include_router(final_features_router)
app.include_router(missing_routes)
app.include_router(polish_router)
app.include_router(production_router)
app.include_router(toolkit_router)
app.include_router(dashboard_data_router)
app.include_router(advanced_router)
app.include_router(ws_router)
app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return await metrics_endpoint()


@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import HTMLResponse

    html = (
        open("src/templates/landing.html")
        .read()
        .replace("{{ version }}", settings.app_version)
        .replace("{{ environment }}", settings.environment)
    )
    return HTMLResponse(content=html)


@app.get("/api/v1/benchmark", tags=["System"])
async def benchmark():
    from src.core.backend import get_backend

    backend = get_backend()
    if not backend.is_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")

    prompt = "The capital of France is"
    results = []

    for _ in range(3):
        start = __import__("time").perf_counter()
        output = backend.generate(prompt=prompt, max_tokens=10, temperature=0.0)
        latency = (__import__("time").perf_counter() - start) * 1000
        results.append(
            {
                "output": output["choices"][0]["text"].strip(),
                "tokens": output["usage"]["completion_tokens"],
                "latency_ms": round(latency, 2),
            }
        )

    latencies = [r["latency_ms"] for r in results]
    return {
        "model_path": getattr(settings, "model_path", ""),
        "n_ctx": settings.model_n_ctx,
        "n_threads": settings.model_n_threads,
        "concurrency_limit": inference_limiter.max_concurrent,
        "runs": results,
        "avg_latency_ms": round(__import__("statistics").mean(latencies), 2),
        "min_latency_ms": round(min(latencies), 2),
        "max_latency_ms": round(max(latencies), 2),
        "tokens_per_second": round(
            sum(r["tokens"] for r in results) / (sum(latencies) / 1000), 2
        ),
    }


@app.exception_handler(503)
async def service_unavailable_handler(request: Request, exc: Exception):
    db_ok = await check_db_health()
    model_ok = get_backend().is_loaded() if _get_backend_safe() else False
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Service temporarily unavailable",
            "checks": {"database": db_ok, "model": model_ok},
        },
    )


def _get_backend_safe():
    try:
        return get_backend()
    except Exception:
        return None


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": ErrorCode.RATE_LIMITED.value, "message": str(exc)}},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )


if os.path.isdir("frontend/dist"):
    app.mount(
        "/assets", StaticFiles(directory="frontend/dist/assets"), name="vue-assets"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_vue_spa(full_path: str):
        if full_path.startswith(
            ("api/", "docs", "redoc", "openapi.json", "metrics", "ws/")
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Not found"}, status_code=404)
        import os as _os

        path = f"frontend/dist/{full_path}" if full_path else "frontend/dist/index.html"
        if not _os.path.isfile(path):
            path = "frontend/dist/index.html"
        if _os.path.isfile(path):
            from fastapi.responses import FileResponse

            return FileResponse(path)
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Not found"}, status_code=404)

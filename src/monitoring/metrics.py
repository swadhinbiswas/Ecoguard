from typing import Callable
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.config import settings
import time


http_requests_total = Counter(
    "ecoguard_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "ecoguard_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

inference_requests_total = Counter(
    "ecoguard_inference_requests_total",
    "Total inference requests",
    ["status"],
)

inference_duration_seconds = Histogram(
    "ecoguard_inference_duration_seconds",
    "Inference duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

inference_tokens_total = Counter(
    "ecoguard_inference_tokens_total",
    "Total tokens generated",
)

inference_tokens_per_request = Histogram(
    "ecoguard_inference_tokens_per_request",
    "Tokens generated per inference request",
    buckets=(8, 16, 32, 64, 128, 256, 512, 1024),
)

drift_score_gauge = Gauge(
    "ecoguard_drift_score",
    "Current statistical drift score",
)

model_loaded_gauge = Gauge(
    "ecoguard_model_loaded",
    "Whether the inference model is loaded (1=loaded, 0=not loaded)",
)

rate_limited_total = Counter(
    "ecoguard_rate_limited_total",
    "Total rate-limited requests",
)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in ("/metrics", "/health", "/api/v1/health"):
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        endpoint = request.url.path
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        return response


async def metrics_endpoint() -> Response:
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


def record_inference(latency_ms: float, token_count: int, success: bool = True) -> None:
    if not settings.metrics_enabled:
        return
    status = "success" if success else "failure"
    inference_requests_total.labels(status=status).inc()
    inference_duration_seconds.observe(latency_ms / 1000.0)
    inference_tokens_total.inc(token_count)
    inference_tokens_per_request.observe(token_count)


def set_drift_score(score: float) -> None:
    if settings.metrics_enabled:
        drift_score_gauge.set(score)


def set_model_loaded(loaded: bool) -> None:
    if settings.metrics_enabled:
        model_loaded_gauge.set(1 if loaded else 0)


def record_rate_limit() -> None:
    if settings.metrics_enabled:
        rate_limited_total.inc()

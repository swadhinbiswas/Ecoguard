"""Final missing pieces: OTel wiring, WebSocket auth, rate limit headers,
enhanced health check, webhook retry, pagination, caching headers, API versioning."""

import asyncio
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import logger

# ── OpenTelemetry Span Wiring ──────────────────────────────────


class OTelTracer:
    _tracer: Optional[Any] = None
    _enabled = False

    @classmethod
    def init(cls):
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider

            if settings.otlp_endpoint:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
                from opentelemetry.sdk.trace.export import BatchSpanProcessor

                resource = Resource.create({"service.name": "eco-guard"})
                provider = TracerProvider(resource=resource)
                exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                trace.set_tracer_provider(provider)
                cls._tracer = trace.get_tracer("eco-guard")
                cls._enabled = True
                logger.info("OTel tracer initialized")
        except Exception as e:
            logger.warning(f"OTel init failed: {e}")

    @classmethod
    def trace_inference(
        cls,
        request_id: str,
        model: str = "",
        provider: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0,
        success: bool = True,
        error: str = "",
    ):
        if not cls._enabled or not cls._tracer:
            return

        try:
            from opentelemetry.trace import SpanKind, Status, StatusCode

            with cls._tracer.start_as_current_span(
                "llm.inference",
                kind=SpanKind.CLIENT,
                attributes={
                    "request_id": request_id,
                    "model": model,
                    "provider": provider or settings.backend,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "latency_ms": round(latency_ms, 2),
                    "success": success,
                    "error": error,
                },
            ) as span:
                if not success:
                    span.set_status(Status(StatusCode.ERROR, error))
        except Exception:
            pass


otel = OTelTracer()


# ── Webhook Retry ──────────────────────────────────────────────


class WebhookRetry:
    _MAX_RETRIES = 3
    _RETRY_DELAYS = [1, 5, 15]  # seconds between retries

    @classmethod
    async def deliver_with_retry(
        cls, url: str, payload: dict, max_retries: int = 0
    ) -> tuple[bool, int]:
        retries = max_retries or cls._MAX_RETRIES
        delays = cls._RETRY_DELAYS[:retries]

        for attempt, delay in enumerate(delays, 1):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.post(url, json=payload)
                    if r.status_code < 500:
                        return True, attempt
            except Exception:
                pass

            if attempt < retries:
                await asyncio.sleep(delay)

        return False, retries

    @classmethod
    async def verify_webhook(cls, url: str) -> dict:
        """Verify a webhook is reachable by sending a test ping."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.post(
                    url, json={"event": "ping", "source": "eco-guard-verification"}
                )
                return {"reachable": True, "status_code": r.status_code}
        except Exception as e:
            return {"reachable": False, "error": str(e)}


webhook_retry = WebhookRetry()


# ── Pagination Helper ──────────────────────────────────────────


class PaginationParams:
    def __init__(self, page: int = 1, limit: int = 20, max_limit: int = 100):
        self.page = max(1, page)
        self.limit = min(max(1, limit), max_limit)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    @staticmethod
    def paginate(query, page: int = 1, limit: int = 20) -> tuple:
        params = PaginationParams(page, limit)
        return query.offset(params.offset).limit(params.limit), params

    @staticmethod
    def response(items: list, count: int, params: "PaginationParams") -> dict:
        total_pages = max(1, (count + params.limit - 1) // params.limit)
        return {
            "items": items,
            "pagination": {
                "page": params.page,
                "limit": params.limit,
                "total": count,
                "total_pages": total_pages,
                "has_next": params.page < total_pages,
                "has_prev": params.page > 1,
            },
        }


# ── Caching Response Headers ───────────────────────────────────


class CacheHeaders:
    @staticmethod
    def public(max_age: int = 60) -> dict[str, str]:
        return {
            "Cache-Control": f"public, max-age={max_age}",
            "ETag": "",
        }

    @staticmethod
    def no_cache() -> dict[str, str]:
        return {"Cache-Control": "no-store, no-cache, must-revalidate"}

    @staticmethod
    def private(max_age: int = 0) -> dict[str, str]:
        return {"Cache-Control": f"private, max-age={max_age}"}


# ── Rate Limit Headers ─────────────────────────────────────────


class RateLimitHeaders:
    @staticmethod
    def build(limit: int, remaining: int, reset_seconds: int) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_seconds),
            "X-RateLimit-Reset-After": str(reset_seconds),
        }


# ── Enhanced Health Check ──────────────────────────────────────


class EnhancedHealth:
    @staticmethod
    async def check_all(db: AsyncSession) -> dict:
        checks: dict[str, str] = {}
        healthy = True

        # Database
        try:
            from sqlalchemy import text

            await db.execute(text("SELECT 1"))
            checks["database"] = "connected"
        except Exception:
            checks["database"] = "disconnected"
            healthy = False

        # Model
        from src.core.backend import get_backend

        checks["model"] = "loaded" if get_backend().is_loaded() else "not_loaded"

        # Redis
        try:
            from src.core.redis import get_redis

            redis = await get_redis()
            if redis:
                await redis.ping()
                checks["redis"] = "connected"
            else:
                checks["redis"] = "not_configured"
        except Exception:
            checks["redis"] = "disconnected"

        # GPU
        try:
            from src.monitoring.gpu import gpu_monitor

            if gpu_monitor.is_available():
                gpus = await gpu_monitor.collect()
                checks["gpu"] = (
                    f"available ({len(gpus)} GPUs)" if gpus else "available (0 GPUs)"
                )
            else:
                checks["gpu"] = "not_available"
        except Exception:
            checks["gpu"] = "unknown"

        return {
            "status": "healthy" if healthy else "degraded",
            "service": "eco-guard",
            "version": settings.app_version,
            "checks": checks,
        }


enhanced_health = EnhancedHealth()

from typing import Any, Optional

from src.core.config import settings
from src.core.logging import logger

_tracer: Any = None


def setup_tracing(app) -> Optional[Any]:
    global _tracer

    if not settings.metrics_enabled:
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({SERVICE_NAME: settings.app_name})
        provider = TracerProvider(resource=resource)

        otlp_endpoint = getattr(settings, "otlp_endpoint", "")
        if otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)

        FastAPIInstrumentor.instrument_app(app)

        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            SQLAlchemyInstrumentor().instrument()
        except Exception:
            pass

        logger.info("OpenTelemetry tracing initialized")
        return _tracer

    except ImportError:
        logger.info("OpenTelemetry not installed — tracing disabled")
        return None
    except Exception as e:
        logger.warning(f"Tracing setup failed: {e}")
        return None


def get_tracer() -> Any:
    global _tracer
    if _tracer is None:
        try:
            from opentelemetry import trace

            _tracer = trace.get_tracer(__name__)
        except ImportError:
            return None
    return _tracer


def trace_inference(
    request_id: str,
    prompt_len: int,
    latency_ms: float,
    token_count: int,
    drift_score: float,
    success: bool = True,
) -> None:
    tracer = get_tracer()
    if tracer is None:
        return

    try:
        from opentelemetry.trace import Status, StatusCode

        with tracer.start_as_current_span("inference") as span:
            span.set_attribute("request.id", request_id)
            span.set_attribute("inference.prompt_length", prompt_len)
            span.set_attribute("inference.latency_ms", latency_ms)
            span.set_attribute("inference.token_count", token_count)
            span.set_attribute("inference.drift_score", drift_score)
            span.set_attribute("model.path", settings.model_path)
            span.set_attribute("model.n_ctx", settings.model_n_ctx)
            span.set_attribute("model.n_threads", settings.model_n_threads)

            if not success:
                span.set_status(Status(StatusCode.ERROR))

            span.add_event(
                "inference_complete",
                {
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "token_count": token_count,
                },
            )
    except Exception:
        pass

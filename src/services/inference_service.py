import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.concurrency import inference_limiter
from src.core.config import settings
from src.core.logging import log_inference, logger
from src.core.tracing import trace_inference
from src.models.inference import InferenceLog
from src.models.schemas import PredictionRequest, PredictionResponse
from src.monitoring.metrics import record_inference, set_drift_score
from src.services.alerter import get_alerter
from src.services.cache_service import inference_cache
from src.services.drift_detector import drift_detector


class InferenceService:
    @staticmethod
    def _build_model_kwargs(request: PredictionRequest) -> dict:
        kwargs: dict = {
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.top_k is not None:
            kwargs["top_k"] = request.top_k
        if request.repeat_penalty is not None:
            kwargs["repeat_penalty"] = request.repeat_penalty
        return kwargs

    @staticmethod
    async def warmup() -> dict:
        backend = get_backend()
        start = time.perf_counter()
        result = backend.generate(
            prompt=settings.model_warmup_prompt, max_tokens=5, temperature=0.0
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "warmup_completed": True,
            "latency_ms": round(latency_ms, 2),
            "output": result["choices"][0]["text"].strip(),
        }

    @staticmethod
    async def generate(
        request_id: str,
        request: PredictionRequest,
        db: AsyncSession,
    ) -> PredictionResponse:
        from src.core.enterprise import budget_manager
        from src.mlops.quality import anomaly_detector

        is_anomaly, anomaly_details = await anomaly_detector.check(
            request_id, request.prompt
        )
        if (
            is_anomaly
            and anomaly_details
            and anomaly_details.get("type") == "spam_flood"
        ):
            await anomaly_detector.log_anomaly(
                db,
                request_id,
                anomaly_details["type"],
                request.prompt,
                anomaly_details["score"],
                anomaly_details,
                blocked=True,
            )
            raise Exception("Request blocked by anomaly detection")

        allowed, budget_msg = await budget_manager.check_budget(db, 0, 0.0001)
        if not allowed:
            raise Exception(f"Budget exceeded: {budget_msg}")

        if settings.cache_enabled:
            cached = await inference_cache.get(
                request.prompt, request.max_tokens, request.temperature
            )
            if cached is not None:
                return PredictionResponse(
                    request_id=request_id,
                    output=cached,
                    latency_ms=0.0,
                    token_count=0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    drift_score=None,
                )

        async with inference_limiter:
            backend = get_backend()
            kwargs = InferenceService._build_model_kwargs(request)
            start_time = time.perf_counter()
            response_data = await asyncio.to_thread(lambda: backend.generate(**kwargs))
            latency_ms = (time.perf_counter() - start_time) * 1000
            output_text = response_data["choices"][0]["text"]
            token_count = response_data["usage"]["completion_tokens"]

        drift_score = drift_detector.update_and_check(latency_ms, token_count)

        log_inference(
            {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "token_count": token_count,
                "drift_score": drift_score,
            }
        )
        record_inference(latency_ms, token_count, success=True)
        set_drift_score(drift_score)
        trace_inference(
            request_id=request_id,
            prompt_len=len(request.prompt),
            latency_ms=latency_ms,
            token_count=token_count,
            drift_score=drift_score,
            success=True,
        )

        db_log = InferenceLog(
            request_id=request_id,
            input_text=request.prompt,
            prediction_output=output_text,
            latency_ms=latency_ms,
            token_count=token_count,
            confidence_score=None,
            drift_score=drift_score,
        )
        db.add(db_log)

        if drift_score >= settings.drift_alert_threshold:
            alerter = get_alerter(webhook_url=settings.alerting_webhook_url)
            await alerter.send_drift_alert(
                drift_score=drift_score,
                latency_ms=latency_ms,
                token_count=token_count,
                threshold=settings.drift_alert_threshold,
            )
            from src.mlops.pipeline import DriftPipeline

            try:
                await DriftPipeline.check_and_trigger(
                    db=db,
                    drift_score=drift_score,
                    threshold=settings.drift_alert_threshold,
                )
            except Exception as e:
                logger.error(f"Retraining pipeline trigger failed: {e}")  # noqa: F821

        if settings.cache_enabled:
            await inference_cache.set(
                request.prompt, request.max_tokens, request.temperature, output_text
            )

        return PredictionResponse(
            request_id=request_id,
            output=output_text,
            latency_ms=latency_ms,
            token_count=token_count,
            timestamp=datetime.now(timezone.utc).isoformat(),
            drift_score=drift_score,
        )

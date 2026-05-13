import asyncio
import json
import time
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.concurrency import inference_limiter
from src.core.logging import logger
from src.models.inference import InferenceLog
from src.models.schemas import PredictionRequest
from src.monitoring.metrics import record_inference, set_drift_score
from src.services.drift_detector import drift_detector


class StreamingInferenceService:
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
    async def generate_stream(
        request_id: str,
        request: PredictionRequest,
        db: AsyncSession | None = None,
    ) -> AsyncGenerator[str, None]:
        backend = get_backend()
        kwargs = StreamingInferenceService._build_model_kwargs(request)
        start_time = time.perf_counter()
        token_count = 0
        output_parts: list[str] = []

        try:
            async with inference_limiter:
                stream = backend.generate_stream(**kwargs)

                for output in stream:
                    choices = output.get("choices", [])
                    if not choices:
                        continue
                    token_text = choices[0].get("text", "")
                    if not token_text:
                        continue
                    token_count += 1
                    output_parts.append(token_text)

                    data = json.dumps(
                        {
                            "token": token_text,
                            "index": token_count,
                        }
                    )
                    yield f"data: {data}\n\n"
                    await asyncio.sleep(0)

            latency_ms = (time.perf_counter() - start_time) * 1000
            drift_score = drift_detector.update_and_check(latency_ms, token_count)
            record_inference(latency_ms, token_count, success=True)
            set_drift_score(drift_score)

            if db is not None:
                db.add(
                    InferenceLog(
                        request_id=request_id,
                        input_text=request.prompt,
                        prediction_output="".join(output_parts),
                        latency_ms=latency_ms,
                        token_count=token_count,
                        confidence_score=None,
                        drift_score=drift_score,
                    )
                )
                await db.commit()

            done_data = json.dumps(
                {
                    "request_id": request_id,
                    "token_count": token_count,
                    "latency_ms": round(latency_ms, 2),
                    "drift_score": drift_score,
                    "done": True,
                }
            )
            yield f"data: {done_data}\n\n"

        except Exception as e:
            record_inference(0, token_count, success=False)
            logger.error(f"Streaming inference error: {e}")
            error_data = json.dumps({"error": str(e), "done": True})
            yield f"data: {error_data}\n\n"

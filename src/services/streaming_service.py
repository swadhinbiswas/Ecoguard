import asyncio
import json
import time
from typing import AsyncGenerator

from src.core.backend import get_backend
from src.core.logging import logger
from src.core.security import sanitize_prompt
from src.models.schemas import PredictionRequest


class StreamingInferenceService:
    @staticmethod
    def _build_model_kwargs(request: PredictionRequest) -> dict:
        kwargs: dict = {
            "prompt": sanitize_prompt(request.prompt),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
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
    ) -> AsyncGenerator[str, None]:
        backend = get_backend()
        kwargs = StreamingInferenceService._build_model_kwargs(request)
        start_time = time.perf_counter()

        try:
            stream = backend.generate_stream(**kwargs)

            token_count = 0
            for output in stream:
                choices = output.get("choices", [])
                if not choices:
                    continue
                token_text = choices[0].get("text", "")
                if not token_text:
                    continue
                token_count += 1

                data = json.dumps(
                    {
                        "token": token_text,
                        "index": token_count,
                    }
                )
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)

            latency_ms = (time.perf_counter() - start_time) * 1000

            done_data = json.dumps(
                {
                    "request_id": request_id,
                    "token_count": token_count,
                    "latency_ms": round(latency_ms, 2),
                    "done": True,
                }
            )
            yield f"data: {done_data}\n\n"

        except Exception as e:
            logger.error(f"Streaming inference error: {e}")
            error_data = json.dumps({"error": str(e), "done": True})
            yield f"data: {error_data}\n\n"

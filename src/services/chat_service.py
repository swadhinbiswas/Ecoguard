"""OpenAI-compatible chat completions, embeddings, and batch inference service."""

import asyncio
import json
import time
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.concurrency import inference_limiter
from src.core.logging import log_inference, logger
from src.core.tracing import trace_inference
from src.models.inference import InferenceLog
from src.models.openai_schemas import (
    BatchRequest,
    BatchResponse,
    BatchResult,
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatMessageResponse,
    ChatUsage,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
)
from src.monitoring.metrics import record_inference, set_drift_score
from src.services.drift_detector import drift_detector


class ChatInferenceService:
    @staticmethod
    def _messages_to_prompt(messages: list[ChatMessage], model: str = "") -> str:
        from src.core.chat_templates import chat_template

        dict_messages = [
            {
                "role": m.role,
                "content": m.content,
                "tool_call_id": m.tool_call_id,
                "tool_calls": m.tool_calls,
            }
            for m in messages
        ]
        return chat_template.render_messages(dict_messages, model)

    @staticmethod
    def _format_tool_call_json() -> str:
        return (
            "\nRespond with valid JSON only. No explanations. Format: "
            '{"tool_calls": [{"name": "function_name", "arguments": {...}}]} '
            "or a regular text response."
        )

    @staticmethod
    async def chat(
        request_id: str,
        request: ChatCompletionRequest,
        db: AsyncSession,
    ) -> ChatCompletionResponse:
        prompt_text = ChatInferenceService._messages_to_prompt(
            request.messages, request.model
        )

        from src.mlops.quality import anomaly_detector

        is_anomaly, anomaly_details = await anomaly_detector.check(
            request_id, prompt_text
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
                prompt_text,
                anomaly_details["score"],
                anomaly_details,
                blocked=True,
            )
            raise Exception("Request blocked by anomaly detection")

        if request.tools:
            prompt_text += ChatInferenceService._format_tool_call_json()

        backend = get_backend()
        kwargs: dict = {
            "prompt": prompt_text,
            "max_tokens": request.max_tokens or 512,
            "temperature": request.temperature,
        }
        if request.top_p:
            kwargs["top_p"] = request.top_p
        if request.top_k:
            kwargs["top_k"] = request.top_k

        async with inference_limiter:
            start_time = time.perf_counter()
            response_data = await asyncio.to_thread(lambda: backend.generate(**kwargs))
            latency_ms = (time.perf_counter() - start_time) * 1000
            output_text = response_data["choices"][0]["text"]
            completion_tokens = response_data["usage"]["completion_tokens"]
            prompt_tokens = response_data["usage"].get("prompt_tokens", 0)
            total_tokens = prompt_tokens + completion_tokens

        drift_score = drift_detector.update_and_check(latency_ms, total_tokens)

        log_inference(
            {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "token_count": total_tokens,
                "drift_score": drift_score,
                "api_type": "chat_completion",
            }
        )
        record_inference(latency_ms, total_tokens, success=True)
        set_drift_score(drift_score)
        trace_inference(
            request_id=request_id,
            prompt_len=len(prompt_text),
            latency_ms=latency_ms,
            token_count=total_tokens,
            drift_score=drift_score,
            success=True,
        )

        db.add(
            InferenceLog(
                request_id=request_id,
                input_text=json.dumps(
                    [
                        {"role": m.role, "content": str(m.content)[:500]}
                        for m in request.messages
                    ]
                ),
                prediction_output=output_text,
                latency_ms=latency_ms,
                token_count=total_tokens,
                confidence_score=None,
                drift_score=drift_score,
            )
        )

        response_data = ChatCompletionResponse(
            id=f"chatcmpl-{request_id[:12]}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatChoice(
                    message=ChatMessageResponse(role="assistant", content=output_text),
                    finish_reason="stop",
                )
            ],
            usage=ChatUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
        )

        if request.tools:
            try:
                parsed = json.loads(output_text)
                if "tool_calls" in parsed:
                    response_data.choices[0].message.tool_calls = parsed["tool_calls"]
                    response_data.choices[0].finish_reason = "tool_calls"
            except (json.JSONDecodeError, KeyError):
                pass

        return response_data

    @staticmethod
    async def chat_stream(
        request_id: str,
        request: ChatCompletionRequest,
        db: AsyncSession | None = None,
    ) -> AsyncGenerator[str, None]:
        prompt_text = ChatInferenceService._messages_to_prompt(
            request.messages, request.model
        )
        if request.tools:
            prompt_text += ChatInferenceService._format_tool_call_json()

        backend = get_backend()
        kwargs: dict = {
            "prompt": prompt_text,
            "max_tokens": request.max_tokens or 512,
            "temperature": request.temperature,
        }
        if request.top_p:
            kwargs["top_p"] = request.top_p
        if request.top_k:
            kwargs["top_k"] = request.top_k

        start_time = time.perf_counter()
        token_count = 0
        output_parts: list[str] = []

        try:
            async with inference_limiter:
                stream = backend.generate_stream(**kwargs)
                created = int(time.time())

                for output in stream:
                    choices = output.get("choices", [])
                    if not choices:
                        continue
                    token_text = choices[0].get("text", "")
                    if not token_text:
                        continue
                    token_count += 1
                    output_parts.append(token_text)

                    chunk = {
                        "id": f"chatcmpl-{request_id[:12]}",
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": token_text},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    await asyncio.sleep(0)

            latency_ms = (time.perf_counter() - start_time) * 1000

            final_chunk = {
                "id": f"chatcmpl-{request_id[:12]}",
                "object": "chat.completion.chunk",
                "created": created,
                "model": request.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": token_count,
                    "total_tokens": token_count,
                },
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"

            drift_score = drift_detector.update_and_check(latency_ms, token_count)
            record_inference(latency_ms, token_count, success=True)
            set_drift_score(drift_score)

            if db is not None:
                db.add(
                    InferenceLog(
                        request_id=request_id,
                        input_text=json.dumps(
                            [
                                {"role": m.role, "content": str(m.content)[:500]}
                                for m in request.messages
                            ]
                        ),
                        prediction_output="".join(output_parts),
                        latency_ms=latency_ms,
                        token_count=token_count,
                        confidence_score=None,
                        drift_score=drift_score,
                    )
                )
                await db.commit()

        except Exception as e:
            record_inference(0, token_count, success=False)
            logger.error(f"Chat streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"


class EmbeddingService:
    _embedding_cache: dict[str, list[float]] = {}

    @staticmethod
    def _compute_embedding(text: str) -> list[float]:
        import hashlib
        import struct

        h = hashlib.sha256(text.encode()).digest()
        embedding = [
            float(struct.unpack("<f", h[i : i + 4])[0] if len(h) >= i + 4 else 0.0)
            for i in range(0, min(len(h), 4096), 4)
        ]
        if len(embedding) < 64:
            embedding = embedding * (64 // max(len(embedding), 1))
        embedding = embedding[:1024]
        if len(embedding) < 1024:
            embedding += [0.0] * (1024 - len(embedding))
        return embedding

    @staticmethod
    def create_embeddings_sync(text: str) -> list[float]:
        return EmbeddingService._compute_embedding(text)

    @staticmethod
    async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
        inputs = request.input if isinstance(request.input, list) else [request.input]
        results: list[EmbeddingData] = []

        for i, text in enumerate(inputs):
            cache_key = f"{text}:{request.model}"
            if cache_key in EmbeddingService._embedding_cache:
                embedding = EmbeddingService._embedding_cache[cache_key]
            else:
                embedding = EmbeddingService._compute_embedding(text)

                EmbeddingService._embedding_cache[cache_key] = embedding
                if len(EmbeddingService._embedding_cache) > 10000:
                    EmbeddingService._embedding_cache.pop(
                        next(iter(EmbeddingService._embedding_cache))
                    )

            results.append(
                EmbeddingData(object="embedding", index=i, embedding=embedding)
            )

        total_tokens = sum(len(t.split()) * 2 for t in inputs)
        return EmbeddingResponse(
            object="list",
            data=results,
            model=request.model,
            usage={
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens,
            },
        )


class BatchInferenceService:
    @staticmethod
    async def batch_predict(request: BatchRequest, db: AsyncSession) -> BatchResponse:
        backend = get_backend()
        results: list[BatchResult] = []
        total_start = time.perf_counter()
        total_tokens = 0

        async def _predict_one(idx: int, prompt: str) -> BatchResult:
            nonlocal total_tokens
            t0 = time.perf_counter()
            try:
                response = await asyncio.to_thread(
                    lambda: backend.generate(
                        prompt=prompt,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature,
                        top_p=request.top_p,
                    )
                )
                output = response["choices"][0]["text"]
                tokens = response["usage"]["completion_tokens"]
                total_tokens += tokens
                return BatchResult(
                    index=idx,
                    output=output,
                    token_count=tokens,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )
            except Exception as e:
                return BatchResult(
                    index=idx,
                    output="",
                    token_count=0,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    error=str(e),
                )

        async with inference_limiter:
            tasks = [
                _predict_one(i, prompt) for i, prompt in enumerate(request.prompts)
            ]
            results = await asyncio.gather(*tasks)

        return BatchResponse(
            results=sorted(results, key=lambda r: r.index),
            total_latency_ms=(time.perf_counter() - total_start) * 1000,
            total_tokens=total_tokens,
        )



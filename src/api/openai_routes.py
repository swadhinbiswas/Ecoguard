"""OpenAI-compatible endpoints + cost tracking, guardrails, batch, fallback."""

import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import verify_request
from src.core.backend import get_backend
from src.core.config import settings
from src.core.guardrails import get_guardrails
from src.db.session import get_db
from src.models.openai_schemas import (
    BatchRequest,
    ChatCompletionRequest,
    EmbeddingRequest,
    FallbackChainRequest,
    OpenAIModel,
    OpenAIModelList,
)
from src.services.chat_service import (
    BatchInferenceService,
    ChatInferenceService,
    EmbeddingService,
)
from src.services.cost_tracker import cost_tracker

openai_router = APIRouter(prefix="/v1", tags=["OpenAI Compatible"])


# ── Models ────────────────────────────────────────────────────


@openai_router.get("/models")
async def list_models(request: Request):
    backend = get_backend()
    created = int(time.time())
    models = [
        OpenAIModel(id="default", created=created),
        OpenAIModel(id=backend.info.get("path", "llama-cpp"), created=created),
    ]
    return OpenAIModelList(data=models)


# ── Chat Completions ──────────────────────────────────────────


@openai_router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    request_id = str(uuid.uuid4())

    if settings.auth_enabled:
        user = verify_request(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

    prompt_text = ""
    for msg in body.messages:
        content = msg.content
        if isinstance(content, str):
            prompt_text += content + "\n"
        elif isinstance(content, list):
            prompt_text += " ".join(
                p.get("text", "") for p in content if p.get("type") == "text"
            )

    if settings.guardrails_enabled:
        pipeline = get_guardrails()
        sanitized, results = await pipeline.run(prompt_text)
        blocked = any(
            r.get("action") == "block" for r in results if isinstance(r, dict)
        )
        if blocked:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Content blocked by guardrails",
                    "guardrail_results": results,
                },
            )

    if body.stream:

        async def _stream():
            async for chunk in ChatInferenceService.chat_stream(request_id, body, db):
                yield chunk

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            },
        )

    response = await ChatInferenceService.chat(request_id, body, db)
    return response


# ── Embeddings ─────────────────────────────────────────────────


@openai_router.post("/embeddings")
async def create_embeddings(
    body: EmbeddingRequest,
    request: Request,
):
    if settings.auth_enabled:
        user = verify_request(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return await EmbeddingService.create_embeddings(body)


# ── Batch Inference ───────────────────────────────────────────


@openai_router.post("/batch/predict")
async def batch_predict(
    body: BatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if settings.auth_enabled:
        user = verify_request(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

    if not get_backend().is_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")

    return await BatchInferenceService.batch_predict(body, db)


# ── Fallback Chain ─────────────────────────────────────────────


@openai_router.post("/fallback/predict")
async def fallback_predict(
    body: FallbackChainRequest,
    request: Request,
):
    if settings.auth_enabled:
        user = verify_request(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

    last_error: str | None = None
    start_time = time.perf_counter()

    for step in body.steps:
        try:
            kwargs: dict = {
                "prompt": body.prompt,
                "max_tokens": body.max_tokens,
                "temperature": body.temperature,
            }
            if step.backend_url:
                kwargs["backend_url"] = step.backend_url

            response = await asyncio.wait_for(
                asyncio.to_thread(lambda: get_backend().generate(**kwargs)),
                timeout=step.timeout_seconds,
            )
            return {
                "output": response["choices"][0]["text"],
                "model": step.model,
                "attempt": body.steps.index(step) + 1,
                "latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "tokens": response["usage"]["completion_tokens"],
            }
        except Exception as e:
            last_error = str(e)
            continue

    raise HTTPException(
        status_code=503,
        detail={
            "error": "All fallback models failed",
            "last_error": last_error,
            "attempts": len(body.steps),
        },
    )


# ── Cost Tracking ──────────────────────────────────────────────


@openai_router.get("/cost/estimate")
async def cost_estimate(
    input_tokens: int = Query(..., ge=0),
    output_tokens: int = Query(..., ge=0),
    model: str = Query(default="default"),
):
    return cost_tracker.estimate_cost(input_tokens, output_tokens, model)


@openai_router.get("/cost/usage")
async def cost_usage(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    return await cost_tracker.get_usage_summary(db, hours=hours)


@openai_router.get("/cost/pricing")
async def cost_pricing():
    from src.services.cost_tracker import _DEFAULT_PRICING

    return {
        model: {
            "input_cost_per_1k": p.input_cost_per_1k,
            "output_cost_per_1k": p.output_cost_per_1k,
        }
        for model, p in _DEFAULT_PRICING.items()
    }


@openai_router.post("/cost/pricing")
async def set_cost_pricing(
    model: str = Query(...),
    input_per_1k: float = Query(..., ge=0),
    output_per_1k: float = Query(..., ge=0),
):
    cost_tracker.set_pricing(model, input_per_1k, output_per_1k)
    return {
        "model": model,
        "input_cost_per_1k": input_per_1k,
        "output_cost_per_1k": output_per_1k,
    }


# ── Guardrails ─────────────────────────────────────────────────


@openai_router.get("/guardrails")
async def list_guardrails():
    pipeline = get_guardrails()
    return {"active": pipeline.active_guardrails}


@openai_router.post("/guardrails/check")
async def check_guardrails(
    prompt: str = Query(..., min_length=1),
):
    pipeline = get_guardrails()
    _, results = await pipeline.run(prompt)
    return {"prompt": prompt[:200], "results": results}


# ── GPU Monitoring ─────────────────────────────────────────────


@openai_router.get("/gpu")
async def gpu_status():
    from src.monitoring.gpu import gpu_monitor

    available = gpu_monitor.is_available()
    if not available:
        return {"available": False, "gpus": []}

    gpus = await gpu_monitor.collect()
    return {"available": True, "count": len(gpus), "gpus": gpus}

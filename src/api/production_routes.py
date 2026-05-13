"""Routes for agent tracing, multi-modal, load testing, compliance, quantization, cold start, HMAC."""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.agent_tracing import agent_tracer
from src.core.production import (
    LoadTester,
    cold_start,
    compliance,
    dynamic_quantizer,
    hmac_signer,
    multi_modal,
)
from src.db.session import get_db

production_router = APIRouter(prefix="/api/v1", tags=["Production"])


# ── Agent Tracing ──────────────────────────────────────────────


class StartTraceRequest(BaseModel):
    session_id: str | None = None


class StartSpanRequest(BaseModel):
    trace_id: str
    span_type: str  # llm_call, tool_call, retry, chain, agent
    name: str
    parent_span_id: str | None = None
    input_data: dict | None = None
    model: str | None = None


class EndSpanRequest(BaseModel):
    span_id: str
    output_data: dict | None = None
    error: str | None = None
    token_count: int = 0


@production_router.post("/traces/start")
async def start_trace(body: StartTraceRequest, db: AsyncSession = Depends(get_db)):
    trace_id = await agent_tracer.start_trace(db, body.session_id)
    return {"trace_id": trace_id}


@production_router.post("/traces/spans/start")
async def start_span(body: StartSpanRequest, db: AsyncSession = Depends(get_db)):
    span_id = await agent_tracer.start_span(
        db,
        body.trace_id,
        body.span_type,
        body.name,
        body.parent_span_id,
        body.input_data,
        model=body.model,
    )
    return {"span_id": span_id}


@production_router.post("/traces/spans/end")
async def end_span(body: EndSpanRequest, db: AsyncSession = Depends(get_db)):
    await agent_tracer.end_span(
        db, body.span_id, body.output_data, body.error, body.token_count
    )
    return {"span_id": body.span_id, "status": "updated"}


@production_router.get("/traces/{trace_id}/tree")
async def get_trace_tree(trace_id: str, db: AsyncSession = Depends(get_db)):
    tree = await agent_tracer.get_trace_tree(db, trace_id)
    return tree


@production_router.get("/traces")
async def list_traces(
    limit: int = Query(default=20, le=100), db: AsyncSession = Depends(get_db)
):
    traces = await agent_tracer.list_traces(db, limit)
    return {"traces": traces}


# ── Multi-Modal ────────────────────────────────────────────────


class MultiModalRequest(BaseModel):
    text: str
    image_paths: list[str] = []


@production_router.post("/multimodal/encode")
async def encode_images(image_paths: list[str]):
    results = []
    for path in image_paths:
        try:
            uri = multi_modal.encode_image(path)
            results.append({"path": path, "encoded": True, "size_bytes": len(uri)})
        except Exception as e:
            results.append({"path": path, "error": str(e)})
    return {"images": results}


@production_router.post("/multimodal/prompt")
async def build_multimodal_prompt(body: MultiModalRequest):
    prompt = multi_modal.build_multimodal_prompt(body.text, body.image_paths)
    messages = multi_modal.build_vision_messages(body.text, body.image_paths)
    return {"prompt": prompt, "messages": messages}


# ── Load Testing ───────────────────────────────────────────────


class LoadTestRequest(BaseModel):
    endpoint: str = "/api/v1/predict"
    payload: dict | None = None
    concurrent: int = Field(10, ge=1, le=100)
    total_requests: int = Field(100, ge=1, le=5000)
    timeout: float = 30


@production_router.post("/load-test")
async def run_load_test(body: LoadTestRequest, request: Request):
    base_url = str(request.base_url).rstrip("/")
    tester = LoadTester(base_url=base_url)
    return await tester.run_load_test(
        body.endpoint,
        body.payload,
        body.concurrent,
        body.total_requests,
        body.timeout,
    )


# ── Compliance ─────────────────────────────────────────────────


@production_router.get("/compliance/export/{username}")
async def export_user_data(username: str, db: AsyncSession = Depends(get_db)):
    return await compliance.export_user_data(db, username)


@production_router.delete("/compliance/delete/{username}")
async def delete_user_data(username: str, db: AsyncSession = Depends(get_db)):
    return await compliance.delete_user_data(db, username)


@production_router.post("/compliance/purge")
async def purge_old_logs(
    max_days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    return await compliance.enforce_retention(db, max_days)


# ── Dynamic Quantization ───────────────────────────────────────


class QuantizationRequest(BaseModel):
    level: str = "full"  # full, q8, q4
    model_path: str = ""


@production_router.post("/quantization/apply")
async def apply_quantization(body: QuantizationRequest):
    return await dynamic_quantizer.apply_quantization(body.level, body.model_path)


@production_router.get("/quantization/recommend")
async def recommend_quantization(qps: float = Query(default=0)):
    level = dynamic_quantizer.get_recommended_level(qps)
    return {"recommended_level": level, "current_qps": qps}


# ── Cold Start ─────────────────────────────────────────────────


class WarmupRequest(BaseModel):
    model_path: str
    warmup_prompt: str = "Hello"


class PreloadRequest(BaseModel):
    model_paths: list[str]


@production_router.post("/cold-start/warmup")
async def warmup_model(body: WarmupRequest):
    return await cold_start.warmup_model(body.model_path, body.warmup_prompt)


@production_router.post("/cold-start/preload")
async def preload_models(body: PreloadRequest):
    return await cold_start.preload_popular_models(body.model_paths)


@production_router.get("/cold-start/predict-load")
async def predict_load(
    hours: int = Query(default=24), db: AsyncSession = Depends(get_db)
):
    return await cold_start.predict_load(db, hours)


# ── HMAC Signing ───────────────────────────────────────────────


class HMACSignRequest(BaseModel):
    method: str = "POST"
    path: str = "/api/v1/predict"
    body: str = ""
    secret: str
    timestamp: int | None = None


@production_router.post("/hmac/sign")
async def sign_request(body: HMACSignRequest):
    headers = hmac_signer.sign_request(
        body.method, body.path, body.body.encode(), body.secret, body.timestamp
    )
    return {"headers": headers}


class HMACVerifyRequest(BaseModel):
    method: str
    path: str
    body: str = ""
    signature: str
    timestamp: str
    secret: str


@production_router.post("/hmac/verify")
async def verify_request(body: HMACVerifyRequest):
    valid = hmac_signer.verify_signature(
        body.method,
        body.path,
        body.body.encode(),
        body.signature,
        body.timestamp,
        body.secret,
    )
    return {"valid": valid}

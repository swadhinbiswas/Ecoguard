"""Routes for vision/multimodal, async inference, workspace rate limits,
real finetune, DB pool monitor, data residency, secrets loading, model cards."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.gap_closer import (
    async_inference,
    data_residency,
    db_pool_monitor,
    model_card_exporter,
    real_finetuner,
    secrets_loader,
    vision,
    workspace_rate_limiter,
)
from src.db.session import get_db

final_features_router = APIRouter(prefix="/api/v1", tags=["Gap Closure"])


# ── #1 Vision/Multimodal ───────────────────────────────────────


class VisionRequest(BaseModel):
    prompt: str
    image_paths: list[str] = Field(..., min_length=1)
    max_tokens: int = 256
    temperature: float = 0.7


@final_features_router.post("/vision/generate")
async def generate_with_vision(body: VisionRequest):
    return await vision.generate_with_image(
        body.prompt, body.image_paths, body.max_tokens, body.temperature
    )


@final_features_router.post("/vision/encode")
async def encode_image(path: str = Query(...)):
    uri = vision.encode_image_file(path)
    return {"path": path, "encoded": True, "size_bytes": len(uri)}


# ── #2 Async Inference ─────────────────────────────────────────


class AsyncInferRequest(BaseModel):
    prompt: str
    max_tokens: int = 128
    temperature: float = 0.7
    callback_url: str = ""


@final_features_router.post("/inference/async")
async def submit_async_inference(
    body: AsyncInferRequest, db: AsyncSession = Depends(get_db)
):
    job = await async_inference.submit(
        db, body.prompt, body.max_tokens, body.temperature, body.callback_url
    )
    return {"job_id": job.job_id, "status": job.status}


@final_features_router.get("/inference/async/{job_id}")
async def get_async_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await async_inference.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "output": job.output,
        "error": job.error,
        "token_count": job.token_count,
        "latency_ms": job.latency_ms,
    }


@final_features_router.get("/inference/async")
async def list_async_jobs(
    limit: int = Query(default=20), db: AsyncSession = Depends(get_db)
):
    return {"jobs": await async_inference.list_jobs(db, limit)}


# ── #3 Per-Workspace Rate Limits ───────────────────────────────


class WorkspaceRateLimitRequest(BaseModel):
    workspace_id: int
    requests_per_minute: int = 100
    tokens_per_minute: int = 100000
    max_concurrent: int = 10


@final_features_router.post("/rate-limits/workspace")
async def set_workspace_rate_limit(
    body: WorkspaceRateLimitRequest, db: AsyncSession = Depends(get_db)
):
    rl = await workspace_rate_limiter.set_limit(
        db,
        body.workspace_id,
        body.requests_per_minute,
        body.tokens_per_minute,
        body.max_concurrent,
    )
    return {
        "workspace_id": rl.workspace_id,
        "requests_per_min": rl.max_requests_per_minute,
        "tokens_per_min": rl.max_tokens_per_minute,
    }


@final_features_router.post("/rate-limits/check")
async def check_workspace_rate_limit(
    workspace_id: int = Query(...),
    tokens: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
):
    allowed, msg = await workspace_rate_limiter.is_allowed(db, workspace_id, tokens)
    return {"workspace_id": workspace_id, "allowed": allowed, "message": msg}


# ── #4 Real Fine-Tuning ────────────────────────────────────────


class RealFinetuneRequest(BaseModel):
    base_model: str
    dataset_path: str
    output_dir: str = "./models/finetuned"
    method: str = "lora"
    rank: int = 8
    epochs: int = 3
    learning_rate: float = 2e-4


@final_features_router.post("/finetune/real")
async def run_real_finetune(body: RealFinetuneRequest):
    return await real_finetuner.run_llama_factory(
        body.base_model,
        body.dataset_path,
        body.output_dir,
        body.method,
        body.rank,
        body.epochs,
        body.learning_rate,
    )


# ── #5 DB Pool Monitoring ──────────────────────────────────────


@final_features_router.get("/db/pool")
async def get_db_pool_stats(db: AsyncSession = Depends(get_db)):
    stats = db_pool_monitor.get_pool_stats()
    connections = await db_pool_monitor.get_connection_count(db)
    stats["active_connections"] = connections
    return stats


# ── #6 Data Residency ──────────────────────────────────────────


@final_features_router.get("/residency")
async def get_residency_config():
    return data_residency.get_region_config()


@final_features_router.post("/residency/set-region")
async def set_residency_region(region: str = Query(...)):
    if not data_residency.is_region_allowed(region):
        raise HTTPException(400, f"Region '{region}' not in allowed list")
    data_residency.set_region(region)
    return {"region": region}


# ── #7 Secrets Auto-Loading ────────────────────────────────────


class SecretsLoadRequest(BaseModel):
    vault_addr: str = ""
    vault_token: str = ""
    vault_paths: list[str] = []
    aws_secret_name: str = ""


@final_features_router.post("/secrets/load")
async def load_secrets(body: SecretsLoadRequest):
    secrets: dict[str, str] = {}

    if body.vault_addr and body.vault_token and body.vault_paths:
        vault_secrets = await secrets_loader.load_from_vault(
            body.vault_addr, body.vault_token, body.vault_paths
        )
        secrets.update(vault_secrets)

    if body.aws_secret_name:
        aws_secrets = await secrets_loader.load_from_aws(body.aws_secret_name)
        secrets.update(aws_secrets)

    count = await secrets_loader.apply_to_settings(secrets)
    return {"loaded_keys": list(secrets.keys()), "applied_to_settings": count}


# ── #8 Model Card Export ───────────────────────────────────────


@final_features_router.post("/models/card")
async def create_model_card(
    model_name: str = Query(...),
    version: str = Query(...),
    description: str = Query(default=""),
    base_model: str = Query(default=""),
    framework: str = Query(default="llama-cpp"),
    db: AsyncSession = Depends(get_db),
):
    card = await model_card_exporter.create_card(
        db, model_name, version, description, base_model, framework
    )
    return {"id": card.id, "model_name": card.model_name}


@final_features_router.get("/models/card/{model_name}")
async def get_model_card(model_name: str, db: AsyncSession = Depends(get_db)):
    return await model_card_exporter.export_card_json(model_name, db)

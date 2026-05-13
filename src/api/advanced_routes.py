"""Routes for prompt A/B testing, human feedback, semantic log search, fine-tuning, SLA, and seed data."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import verify_request
from src.db.session import get_db
from src.mlops.advanced import (
    ab_test_runner,
    feedback_collector,
    fine_tune_executor,
    semantic_search,
    sla_monitor,
)

advanced_router = APIRouter(prefix="/api/v1", tags=["Advanced"])


# ── Prompt A/B Testing ─────────────────────────────────────────


class ABTestRequest(BaseModel):
    test_name: str
    prompt_a: str
    prompt_b: str
    num_runs: int = Field(5, ge=1, le=20)


@advanced_router.post("/ab-test")
async def run_ab_test(body: ABTestRequest):
    return await ab_test_runner.run_test(
        body.test_name, body.prompt_a, body.prompt_b, body.num_runs
    )


class PromptVersionRequest(BaseModel):
    name: str
    prompt_template: str
    variables: list[str] = []


@advanced_router.post("/prompts/versions")
async def create_prompt_version(
    body: PromptVersionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = verify_request(request)
    from src.mlops.advanced import PromptVersion

    pv = PromptVersion(
        name=body.name,
        prompt_template=body.prompt_template,
        variables=body.variables,
        created_by=user["sub"] if user else "admin",
    )
    db.add(pv)
    await db.flush()
    return {"id": pv.id, "name": pv.name, "version": pv.version}


@advanced_router.get("/prompts/versions")
async def list_prompt_versions(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select as sa_select

    from src.mlops.advanced import PromptVersion

    result = await db.execute(
        sa_select(PromptVersion)
        .where(PromptVersion.is_active)
        .order_by(PromptVersion.id.desc())
    )
    versions = result.scalars().all()
    return [
        {"id": v.id, "name": v.name, "version": v.version, "variables": v.variables}
        for v in versions
    ]


# ── Human Feedback ─────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    request_id: str
    rating: int = Field(..., ge=-1, le=5)
    feedback_text: str = ""
    category: str = ""


@advanced_router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = verify_request(request)
    fb = await feedback_collector.record_feedback(
        db,
        body.request_id,
        body.rating,
        body.feedback_text,
        body.category,
        user["sub"] if user else "",
    )
    return {"id": fb.id, "rating": fb.rating}


@advanced_router.get("/feedback/stats")
async def feedback_stats(
    hours: int = Query(default=168, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    return await feedback_collector.get_feedback_stats(db, hours=hours)


# ── Semantic Log Search ────────────────────────────────────────


@advanced_router.get("/logs/search")
async def search_logs(
    q: str = Query(..., min_length=3),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    results = await semantic_search.search_similar(db, q, limit)
    return {"query": q, "results": results}


# ── Fine-Tuning ───────────────────────────────────────────────


class FineTuneRequest(BaseModel):
    base_model: str
    dataset_path: str
    output_dir: str = "./models/finetuned"
    rank: int = 8
    epochs: int = 3
    learning_rate: float = 2e-4


@advanced_router.post("/finetune")
async def run_finetune(body: FineTuneRequest):
    result = await fine_tune_executor.run_lora_job(
        body.base_model,
        body.dataset_path,
        body.output_dir,
        body.rank,
        body.epochs,
        body.learning_rate,
    )
    return result


# ── SLA Monitoring ─────────────────────────────────────────────


@advanced_router.get("/sla")
async def check_sla(
    minutes: int = Query(default=60, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
):
    return await sla_monitor.check_sla(db, minutes)


# ── Seed Data Generator ────────────────────────────────────────


@advanced_router.post("/seed/generate")
async def generate_seed_data(db: AsyncSession = Depends(get_db)):
    from src.core.config import settings

    if settings.environment == "production":
        raise HTTPException(403, "Seed data generation is disabled in production")
    from datetime import datetime, timedelta, timezone

    from src.mlops.models import (
        Dataset,
        Deployment,
        ExperimentStatus,
        JobStatus,
        ModelRegistry,
        ModelStatus,
        RetrainingTrigger,
        TrainingExperiment,
        TrainingJob,
    )
    from src.models.inference import InferenceLog

    now = datetime.now(timezone.utc)

    # Models
    models_data = [
        {
            "name": "llama-3-8b-instruct",
            "version": "v1.0.0",
            "status": ModelStatus.PRODUCTION,
            "artifact_path": "/app/models/llama-3-8b.gguf",
        },
        {
            "name": "mistral-7b",
            "version": "v0.3.0",
            "status": ModelStatus.REGISTERED,
            "artifact_path": "/app/models/mistral-7b.gguf",
        },
        {
            "name": "tinyllama-1.1b",
            "version": "v1.0.0",
            "status": ModelStatus.ARCHIVED,
            "artifact_path": "/app/models/tinyllama.gguf",
        },
    ]
    model_ids = []
    for m in models_data:
        model = ModelRegistry(**m, framework="llama-cpp", created_by="seed")
        db.add(model)
        await db.flush()
        model_ids.append(model.id)

    # Datasets
    dataset = Dataset(
        name="seed-demo-v1",
        version="1.0",
        format="jsonl",
        file_path="data/seed_demo.jsonl",
        record_count=150,
        source="seed",
        created_by="seed",
    )
    db.add(dataset)
    await db.flush()

    # Training experiments
    for i in range(3):
        exp = TrainingExperiment(
            name=f"seed-experiment-{i + 1}",
            base_model="llama-3-8b",
            hyperparameters={"lr": 2e-4, "epochs": 3 + i},
            status=ExperimentStatus.COMPLETED,
            best_metric="perplexity",
            best_metric_value=12.5 - i * 2,
            total_steps=500 * (i + 1),
            created_by="seed",
            completed_at=now - timedelta(days=i),
        )
        db.add(exp)

    # Training jobs
    for i in range(4):
        statuses = [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.RUNNING,
            JobStatus.QUEUED,
        ]
        job = TrainingJob(
            name=f"seed-job-{i + 1}",
            status=statuses[i],
            config={"lora_rank": 8, "epochs": 3},
            dataset_id=dataset.id,
            trigger_type="manual" if i < 2 else "drift",
            created_by="seed",
            started_at=now - timedelta(hours=i) if i < 2 else None,
            completed_at=now - timedelta(minutes=30) if i == 0 else None,
            error_message="CUDA out of memory" if i == 1 else None,
        )
        db.add(job)

    # Deployments
    for i in range(2):
        dep = Deployment(
            model_id=model_ids[0],
            strategy="direct" if i == 0 else "canary",
            status="active",
            traffic_percent=100 if i == 0 else 30,
            deployed_by="seed",
        )
        db.add(dep)

    # Drift triggers
    for i in range(5):
        trigger = RetrainingTrigger(
            drift_score=0.7 + i * 0.06,
            threshold=0.8,
            acknowledged=i >= 3,
            auto_triggered=i >= 2,
            dataset_id=dataset.id if i >= 2 else None,
        )
        db.add(trigger)

    # Inference logs (30 entries)
    sample_prompts = [
        "What is machine learning?",
        "Explain vector databases",
        "Write a Python function",
        "What is the capital of France?",
        "How does gradient descent work?",
        "Summarize the theory of relativity",
        "Compare BERT vs GPT",
        "What is RAG?",
        "Explain transformer attention",
        "Describe Kubernetes architecture",
    ]
    for i in range(30):
        prompt = sample_prompts[i % len(sample_prompts)]
        log = InferenceLog(
            request_id=f"seed-{uuid.uuid4().hex[:8]}-{i}",
            input_text=prompt,
            prediction_output=f"This is a seed response for: {prompt}",
            latency_ms=50 + i * 5,
            token_count=20 + i % 10,
            drift_score=0.1 + i * 0.02,
            timestamp=now - timedelta(minutes=i * 30),
        )
        db.add(log)

    await db.flush()
    return {
        "message": "Seed data generated",
        "models": len(models_data),
        "inference_logs": 30,
        "jobs": 4,
        "experiments": 3,
        "datasets": 1,
    }

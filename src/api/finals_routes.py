"""Routes for budgets, priority queue, load balancer, auto-scaling, regression, anomaly, benchmarks, cron, audit, disaster recovery, key analytics."""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enterprise import (
    Priority,
    ProviderConfig,
    auto_scaler,
    budget_manager,
    priority_queue,
    provider_lb,
)
from src.db.session import get_db
from src.mlops.gov import (
    ScheduledJob,
    audit_logger,
    disaster_recovery,
    key_analytics,
)
from src.mlops.quality import (
    anomaly_detector,
    benchmark_suite,
    regression_detector,
)

finals_router = APIRouter(prefix="/api/v1", tags=["Enterprise Final"])


# ── Budget Caps ────────────────────────────────────────────────


class BudgetRequest(BaseModel):
    workspace_id: int
    cap_amount: float = Field(..., gt=0)
    period: str = "monthly"
    alert_pct: float = 80.0


@finals_router.post("/budgets")
async def set_budget(body: BudgetRequest, db: AsyncSession = Depends(get_db)):
    budget = await budget_manager.set_budget(
        db, body.workspace_id, body.cap_amount, body.period, body.alert_pct
    )
    return {"id": budget.id, "workspace_id": budget.workspace_id}


@finals_router.get("/budgets/{workspace_id}")
async def get_budget(workspace_id: int, db: AsyncSession = Depends(get_db)):
    return await budget_manager.get_budget_status(db, workspace_id)


# ── Priority Queue ─────────────────────────────────────────────


class EnqueueRequest(BaseModel):
    prompt: str
    max_tokens: int = 128
    temperature: float = 0.7
    priority: str = "medium"


@finals_router.post("/queue/enqueue")
async def enqueue_request(body: EnqueueRequest, request: Request):
    import uuid

    rid = str(uuid.uuid4())
    await priority_queue.enqueue(
        rid, body.prompt, body.max_tokens, body.temperature, Priority(body.priority)
    )
    return {"request_id": rid, "priority": body.priority}


@finals_router.get("/queue/status")
async def queue_status():
    return {"depth": priority_queue.depth}


# ── Provider Load Balancer ─────────────────────────────────────


class ProviderRegisterRequest(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    model: str = "default"
    weight: float = 1.0
    max_concurrent: int = 100


@finals_router.post("/providers")
async def register_provider(body: ProviderRegisterRequest):
    provider_lb.register(ProviderConfig(**body.model_dump()))
    return {"registered": body.name}


@finals_router.get("/providers")
async def list_providers():
    return {"providers": provider_lb.get_status()}


@finals_router.delete("/providers/{name}")
async def deregister_provider(name: str):
    provider_lb.deregister(name)
    return {"deregistered": name}


# ── Auto-Scaling ───────────────────────────────────────────────


class ScalingRuleRequest(BaseModel):
    name: str
    metric: str
    condition: str = "gt"
    threshold: float
    action: str
    action_value: dict | None = None


@finals_router.post("/auto-scale/rules")
async def create_scaling_rule(
    body: ScalingRuleRequest, db: AsyncSession = Depends(get_db)
):
    rule = await auto_scaler.set_rule(
        db,
        body.name,
        body.metric,
        body.condition,
        body.threshold,
        body.action,
        body.action_value,
    )
    return {"id": rule.id, "name": rule.name}


@finals_router.get("/auto-scale/status")
async def auto_scale_status():
    return {"metrics": auto_scaler.get_current_metrics()}


# ── Model Regression Detection ─────────────────────────────────


class RegressionCheckRequest(BaseModel):
    model_id: int
    baseline_model_id: int
    suite_name: str
    metrics: dict[str, float]


@finals_router.post("/regression/check")
async def check_regression(
    body: RegressionCheckRequest, db: AsyncSession = Depends(get_db)
):
    return await regression_detector.check_regression(
        db, body.model_id, body.baseline_model_id, body.suite_name, body.metrics
    )


# ── Prompt Anomaly Detection ───────────────────────────────────


class AnomalyCheckRequest(BaseModel):
    prompt: str


@finals_router.post("/anomaly/check")
async def check_anomaly(body: AnomalyCheckRequest, db: AsyncSession = Depends(get_db)):
    import uuid

    rid = str(uuid.uuid4())
    is_anomaly, details = await anomaly_detector.check(rid, body.prompt)

    if is_anomaly and details:
        await anomaly_detector.log_anomaly(
            db,
            rid,
            details["type"],
            body.prompt,
            details["score"],
            details,
            blocked=True,
        )

    return {"request_id": rid, "is_anomaly": is_anomaly, "details": details}


@finals_router.get("/anomaly/recent")
async def recent_anomalies(
    hours: int = Query(default=24), db: AsyncSession = Depends(get_db)
):
    return {"anomalies": await anomaly_detector.get_recent_anomalies(db, hours)}


# ── Benchmark Suite ────────────────────────────────────────────


@finals_router.get("/benchmarks")
async def list_benchmarks():
    return {"benchmarks": benchmark_suite.list_benchmarks()}


@finals_router.post("/benchmarks/run/{suite}")
async def run_benchmark(suite: str):
    return await benchmark_suite.run_suite(suite)


@finals_router.post("/benchmarks/run-all")
async def run_all_benchmarks():
    return await benchmark_suite.run_all_benchmarks()


# ── Scheduled Inference (Cron) ─────────────────────────────────


class CronJobRequest(BaseModel):
    name: str
    cron_expression: str  # hourly, daily, weekly
    prompt: str
    max_tokens: int = 128
    temperature: float = 0.7
    webhook_url: str = ""


@finals_router.post("/cron/jobs")
async def create_cron_job(body: CronJobRequest, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone

    job = ScheduledJob(**body.model_dump(), next_run_at=datetime.now(timezone.utc))
    db.add(job)
    await db.flush()
    return {"id": job.id, "name": job.name}


@finals_router.get("/cron/jobs")
async def list_cron_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScheduledJob))
    jobs = result.scalars().all()
    return {
        "jobs": [
            {
                "id": j.id,
                "name": j.name,
                "enabled": j.enabled,
                "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
            }
            for j in jobs
        ]
    }


# ── Audit Log ─────────────────────────────────────────────────


@finals_router.post("/audit/log")
async def log_audit(
    action: str = Query(...),
    username: str = Query(default=""),
    resource_type: str = Query(default=""),
    resource_id: int | None = Query(default=None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request and request.client else ""
    entry = await audit_logger.log(db, action, username, resource_type, resource_id, ip)
    return {"id": entry.id}


@finals_router.get("/audit/entries")
async def audit_entries(
    hours: int = Query(default=168),
    action: str = Query(default=""),
    username: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    return {"entries": await audit_logger.query(db, hours, action, username)}


@finals_router.get("/audit/stats")
async def audit_stats(
    hours: int = Query(default=168), db: AsyncSession = Depends(get_db)
):
    return {"action_counts": await audit_logger.get_action_counts(db, hours)}


# ── Disaster Recovery ──────────────────────────────────────────


@finals_router.post("/backup")
async def create_backup(
    include_models: bool = Query(default=False), db: AsyncSession = Depends(get_db)
):
    manifest = await disaster_recovery.create_backup(db, include_models=include_models)
    return manifest


@finals_router.get("/backup/list")
async def list_backups():
    return {"backups": await disaster_recovery.list_backups()}


@finals_router.post("/backup/restore")
async def restore_backup(
    backup_file: str = Query(...), db: AsyncSession = Depends(get_db)
):
    return await disaster_recovery.restore_from_backup(db, backup_file)


# ── API Key Analytics ──────────────────────────────────────────


@finals_router.get("/keys/analytics")
async def key_usage_analytics(
    hours: int = Query(default=168), db: AsyncSession = Depends(get_db)
):
    return await key_analytics.get_key_usage(db, hours)


@finals_router.get("/keys/top")
async def top_keys(db: AsyncSession = Depends(get_db)):
    return {"top": await key_analytics.get_top_keys(db)}

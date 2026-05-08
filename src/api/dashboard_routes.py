from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.config import settings
from src.db.database import check_db_health
from src.db.session import get_db
from src.mlops.dataset import DatasetPipeline
from src.mlops.experiments import ExperimentTracker
from src.mlops.models import (
    Deployment,
    JobStatus,
    ModelRegistry,
    ModelStatus,
    RetrainingTrigger,
    TrainingJob,
)
from src.mlops.pipeline import DriftPipeline
from src.mlops.registry import ModelRegistryService
from src.mlops.training import TrainingOrchestrator
from src.models.inference import InferenceLog
from src.services.cache_service import inference_cache
from src.services.drift_detector import drift_detector

templates = Jinja2Templates(directory="src/templates")

dashboard = APIRouter(prefix="/dashboard", include_in_schema=False)


def _base_context(request: Request) -> dict:
    return {
        "current_page": "dashboard",
        "model_loaded": get_backend().is_loaded(),
        "version": settings.app_version,
    }


# ── Overview ──────────────────────────────────────────────────


@dashboard.get("", response_class=HTMLResponse)
@dashboard.get("/", response_class=HTMLResponse)
async def dashboard_overview(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = _base_context(request)
    ctx["current_page"] = "dashboard"

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(
            func.count(InferenceLog.id).label("total"),
            func.avg(InferenceLog.latency_ms).label("avg_lat"),
            func.avg(InferenceLog.token_count).label("avg_tok"),
            func.sum(InferenceLog.token_count).label("sum_tok"),
            func.avg(InferenceLog.drift_score).label("avg_drift"),
        ).where(InferenceLog.timestamp >= cutoff)
    )
    row = result.one_or_none()

    model_count = await db.execute(select(func.count(ModelRegistry.id)))
    models_total = model_count.scalar() or 0

    prod_count = await db.execute(
        select(func.count(ModelRegistry.id)).where(
            ModelRegistry.status == ModelStatus.PRODUCTION
        )
    )
    models_prod = prod_count.scalar() or 0

    jobs_total_r = await db.execute(select(func.count(TrainingJob.id)))
    jobs_total = jobs_total_r.scalar() or 0

    jobs_active_r = await db.execute(
        select(func.count(TrainingJob.id)).where(
            TrainingJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
        )
    )
    jobs_active = jobs_active_r.scalar() or 0

    ctx["stats"] = {
        "total_requests": int(row.total) if row and row.total else 0,
        "avg_latency_ms": round(float(row.avg_lat), 2) if row and row.avg_lat else 0.0,
        "avg_tokens": round(float(row.avg_tok), 2) if row and row.avg_tok else 0.0,
        "total_tokens": int(row.sum_tok) if row and row.sum_tok else 0,
        "avg_drift": round(float(row.avg_drift), 4) if row and row.avg_drift else 0.0,
        "period_hours": 24,
        "models_registered": int(models_total),
        "models_production": int(models_prod),
        "jobs_total": int(jobs_total),
        "jobs_active": int(jobs_active),
        "db_healthy": await check_db_health(),
        "cache_size": inference_cache.size,
        "max_concurrent": 4,
        "drift_samples": len(drift_detector._latency_history),
    }

    recent_logs_result = await db.execute(
        select(InferenceLog.latency_ms)
        .where(InferenceLog.timestamp >= cutoff)
        .order_by(desc(InferenceLog.timestamp))
        .limit(20)
    )
    ctx["recent_requests"] = [
        round(r.latency_ms, 2) for r in recent_logs_result.scalars().all()
    ]

    drift_values = (
        drift_detector._latency_history[-20:] if drift_detector._latency_history else []
    )
    ctx["recent_drifts"] = [
        round(
            float(
                abs(v - statistics.mean(drift_values))
                / (statistics.stdev(drift_values) + 1e-6)
            )
            / 10,
            4,
        )
        if len(drift_values) > 1
        else 0.0
        for v in drift_values
    ]
    if not ctx["recent_drifts"]:
        ctx["recent_drifts"] = [0.0]
    ctx["recent_drifts"] = [min(1.0, d) for d in ctx["recent_drifts"]]

    ctx["threshold"] = settings.drift_alert_threshold
    ctx["alerts"] = []

    return templates.TemplateResponse(request, "dashboard.html", ctx)


# ── Models ─────────────────────────────────────────────────────


@dashboard.get("/models", response_class=HTMLResponse)
async def models_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = _base_context(request)
    ctx["current_page"] = "models"
    ctx["models"] = await ModelRegistryService.list_models(db=db, limit=100)
    return templates.TemplateResponse(request, "models.html", ctx)


@dashboard.post("/models/register", response_class=HTMLResponse)
async def register_model_action(
    request: Request,
    name: str = Form(...),
    artifact_path: str = Form(...),
    version: str | None = Form(None),
    base_model: str | None = Form(None),
    framework: str = Form("llama-cpp"),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        await ModelRegistryService.register(
            db=db,
            name=name,
            artifact_path=artifact_path,
            version=version,
            base_model=base_model,
            framework=framework,
            description=description,
        )
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/models", status_code=303)


@dashboard.post("/models/{model_id}/deploy", response_class=HTMLResponse)
async def deploy_model_action(model_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await ModelRegistryService.deploy(db=db, model_id=model_id)
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/models", status_code=303)


@dashboard.post("/models/{model_id}/rollback", response_class=HTMLResponse)
async def rollback_model_action(model_id: int, db: AsyncSession = Depends(get_db)):
    model_result = await db.execute(
        select(ModelRegistry).where(ModelRegistry.id == model_id)
    )
    model = model_result.scalar_one_or_none()
    if model:
        try:
            deployments = await db.execute(
                select(Deployment).where(
                    Deployment.model_id == model_id,
                    Deployment.status == "active",
                )
            )
            dep = deployments.scalar_one_or_none()
            if dep:
                await ModelRegistryService.rollback(
                    db, dep.id, "Manual rollback from dashboard"
                )
        except Exception:
            pass
    return RedirectResponse(url="/dashboard/models", status_code=303)


# ── Inference ──────────────────────────────────────────────────


@dashboard.get("/inference", response_class=HTMLResponse)
async def inference_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = _base_context(request)
    ctx["current_page"] = "inference"

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(
            func.count(InferenceLog.id).label("total"),
            func.avg(InferenceLog.latency_ms).label("avg_lat"),
            func.sum(InferenceLog.token_count).label("sum_tok"),
            func.avg(InferenceLog.token_count).label("avg_tok"),
            func.max(InferenceLog.latency_ms).label("max_lat"),
        ).where(InferenceLog.timestamp >= cutoff)
    )
    row = result.one_or_none()
    ctx["stats"] = {
        "total_requests": int(row.total) if row and row.total else 0,
        "avg_latency_ms": round(float(row.avg_lat), 2) if row and row.avg_lat else 0.0,
        "total_tokens": int(row.sum_tok) if row and row.sum_tok else 0,
        "avg_tokens": round(float(row.avg_tok), 2) if row and row.avg_tok else 0.0,
        "max_latency_ms": round(float(row.max_lat), 2) if row and row.max_lat else 0.0,
    }

    logs_result = await db.execute(
        select(InferenceLog).order_by(desc(InferenceLog.timestamp)).limit(20)
    )
    ctx["recent_logs"] = logs_result.scalars().all()

    latencies = []
    for log in ctx["recent_logs"]:
        if log.latency_ms:
            latencies.append(log.latency_ms)
    ctx["latency_buckets"] = [
        sum(1 for lat in latencies if lat < 100),
        sum(1 for lat in latencies if 100 <= lat < 250),
        sum(1 for lat in latencies if 250 <= lat < 500),
        sum(1 for lat in latencies if 500 <= lat < 1000),
        sum(1 for lat in latencies if 1000 <= lat < 2000),
        sum(1 for lat in latencies if lat >= 2000),
    ]

    return templates.TemplateResponse(request, "inference.html", ctx)


@dashboard.get("/inference/recent", response_class=HTMLResponse)
async def inference_recent(request: Request, db: AsyncSession = Depends(get_db)):
    logs_result = await db.execute(
        select(InferenceLog).order_by(desc(InferenceLog.timestamp)).limit(20)
    )
    logs = logs_result.scalars().all()

    rows = ""
    for log in logs:
        color = (
            "#f85149"
            if log.drift_score and log.drift_score > 0.7
            else "#d29922"
            if log.drift_score and log.drift_score > 0.4
            else "#3fb950"
        )
        rows += (
            f'<tr><td><span class="mono" title="{log.request_id}">{log.request_id[:12]}...</span></td>'
            f"<td>{log.latency_ms:.1f}ms</td><td>{log.token_count}</td>"
            f'<td><span style="color:{color}">{log.drift_score:.4f}</span></td>'
            f'<td><span style="color:var(--text2);font-size:12px">{log.timestamp.isoformat()[:19] if log.timestamp else "—"}</span></td></tr>'
        )
    if not logs:
        rows = '<tr><td colspan="5"><div class="empty-state">No inference requests yet</div></td></tr>'
    return HTMLResponse(content=rows)


# ── Drift ──────────────────────────────────────────────────────


@dashboard.get("/drift", response_class=HTMLResponse)
async def drift_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = _base_context(request)
    ctx["current_page"] = "drift"

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(
            func.avg(InferenceLog.drift_score).label("avg_drift"),
            func.avg(InferenceLog.latency_ms).label("avg_lat"),
        ).where(InferenceLog.timestamp >= cutoff)
    )
    row = result.one_or_none()

    triggers = await DriftPipeline.list_triggers(db=db, limit=50)

    total_triggers = await db.execute(select(func.count(RetrainingTrigger.id)))
    unack = await db.execute(
        select(func.count(RetrainingTrigger.id)).where(
            RetrainingTrigger.acknowledged.is_(False)
        )
    )

    ctx["stats"] = {
        "avg_drift": round(float(row.avg_drift), 4) if row and row.avg_drift else 0.0,
        "avg_latency_ms": round(float(row.avg_lat), 2) if row and row.avg_lat else 0.0,
        "drift_samples": len(drift_detector._latency_history),
        "triggers_total": total_triggers.scalar() or 0,
        "triggers_unacknowledged": unack.scalar() or 0,
    }
    ctx["triggers"] = triggers
    ctx["threshold"] = settings.drift_alert_threshold

    latency_hist = drift_detector._latency_history[-50:]
    ctx["drift_timeline_labels"] = [f"t{i}" for i in range(len(latency_hist))]
    ctx["drift_timeline_values"] = []
    for i, v in enumerate(latency_hist):
        if i > 0 and len(latency_hist[:i]) > 1:
            m = statistics.mean(latency_hist[:i])
            s = statistics.stdev(latency_hist[:i]) + 1e-6
            ctx["drift_timeline_values"].append(round(min(1.0, abs(v - m) / s / 10), 4))
        else:
            ctx["drift_timeline_values"].append(0.0)

    return templates.TemplateResponse(request, "drift.html", ctx)


@dashboard.post("/drift/triggers/{trigger_id}/acknowledge", response_class=HTMLResponse)
async def acknowledge_trigger_action(
    trigger_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        await DriftPipeline.acknowledge_trigger(db, trigger_id)
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/drift", status_code=303)


# ── Experiments ────────────────────────────────────────────────


@dashboard.get("/experiments", response_class=HTMLResponse)
async def experiments_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = _base_context(request)
    ctx["current_page"] = "experiments"
    ctx["experiments"] = await ExperimentTracker.list_experiments(db=db, limit=100)
    return templates.TemplateResponse(request, "experiments.html", ctx)


@dashboard.post("/experiments/create", response_class=HTMLResponse)
async def create_experiment_action(
    request: Request,
    name: str = Form(...),
    base_model: str = Form(...),
    hyperparameters: str = Form("{}"),
    dataset_version: str | None = Form(None),
    notes: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        hp = json.loads(hyperparameters)
        await ExperimentTracker.create_experiment(
            db=db,
            name=name,
            base_model=base_model,
            hyperparameters=hp,
            dataset_version=dataset_version,
            notes=notes,
        )
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/experiments", status_code=303)


@dashboard.get("/experiments/compare", response_class=HTMLResponse)
async def compare_experiments_action(
    request: Request,
    ids: str = Query(""),
    metric_name: str = Query("eval_loss"),
    db: AsyncSession = Depends(get_db),
):
    try:
        eids = [int(x.strip()) for x in ids.split(",") if x.strip()]
        data = await ExperimentTracker.compare_experiments(db, eids, metric_name)

        rows = ""
        for eid, v in data.items():
            rows += (
                f'<div class="alert alert-success">'
                f"Experiment {eid}: final <strong>{v['final_value']:.4f}</strong>, "
                f"best <strong>{v['best_value']:.4f}</strong> ({v['steps']} steps)"
                f"</div>"
            )
        return HTMLResponse(
            content=rows or '<div class="alert alert-warning">No data found</div>'
        )
    except Exception:
        return HTMLResponse(
            content='<div class="alert alert-error">Comparison failed</div>'
        )


@dashboard.get("/experiments/{experiment_id}", response_class=HTMLResponse)
async def experiment_detail(
    request: Request, experiment_id: int, db: AsyncSession = Depends(get_db)
):
    ctx = _base_context(request)
    ctx["current_page"] = "experiments"
    exp, metrics = await ExperimentTracker.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(status_code=404)
    ctx["experiment"] = exp
    ctx["metrics"] = metrics
    return templates.TemplateResponse(request, "experiment_detail.html", ctx)


# ── Jobs ───────────────────────────────────────────────────────


@dashboard.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = _base_context(request)
    ctx["current_page"] = "jobs"
    ctx["jobs"] = await TrainingOrchestrator.list_jobs(db=db, limit=100)
    return templates.TemplateResponse(request, "jobs.html", ctx)


@dashboard.post("/jobs/create", response_class=HTMLResponse)
async def create_job_action(
    request: Request,
    name: str = Form(...),
    config: str = Form("{}"),
    base_model_id: int | None = Form(None),
    dataset_id: int | None = Form(None),
    output_model_name: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        cfg = json.loads(config)
        await TrainingOrchestrator.create_job(
            db=db,
            name=name,
            config=cfg,
            base_model_id=base_model_id,
            dataset_id=dataset_id,
            output_model_name=output_model_name,
        )
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/jobs", status_code=303)


@dashboard.post("/jobs/{job_id}/start", response_class=HTMLResponse)
async def start_job_action(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await TrainingOrchestrator.start_job(db, job_id)
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/jobs", status_code=303)


@dashboard.post("/jobs/{job_id}/complete", response_class=HTMLResponse)
async def complete_job_action(
    job_id: int,
    success: bool = Query(True),
    error_message: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        await TrainingOrchestrator.complete_job(
            db=db, job_id=job_id, success=success, error_message=error_message
        )
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/jobs", status_code=303)


@dashboard.post("/jobs/{job_id}/cancel", response_class=HTMLResponse)
async def cancel_job_action(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await TrainingOrchestrator.cancel_job(db, job_id)
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/jobs", status_code=303)


# ── Datasets ───────────────────────────────────────────────────


@dashboard.get("/datasets", response_class=HTMLResponse)
async def datasets_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = _base_context(request)
    ctx["current_page"] = "datasets"
    ctx["ds_stats"] = await DatasetPipeline.get_stats(db)
    ctx["datasets"] = await DatasetPipeline.list_datasets(db=db, limit=100)
    return templates.TemplateResponse(request, "datasets.html", ctx)


@dashboard.post("/datasets/create", response_class=HTMLResponse)
async def create_dataset_action(
    request: Request,
    name: str = Form(...),
    hours: int = Form(168),
    min_tokens: int = Form(1),
    max_drift: float = Form(1.0),
    limit: int = Form(10000),
    db: AsyncSession = Depends(get_db),
):
    try:
        await DatasetPipeline.create_from_inference_logs(
            db=db,
            name=name,
            hours=hours,
            min_tokens=min_tokens,
            max_drift=max_drift,
            limit=limit,
        )
    except Exception:
        pass
    return RedirectResponse(url="/dashboard/datasets", status_code=303)


# ── Auth Pages ──────────────────────────────────────────────────


@dashboard.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})

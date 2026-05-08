from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.mlops.dataset import DatasetPipeline
from src.mlops.experiments import ExperimentTracker
from src.mlops.models import (
    DeploymentStrategy,
    ExperimentStatus,
    JobStatus,
    ModelStatus,
)
from src.mlops.pipeline import DriftPipeline
from src.mlops.registry import ModelRegistryService
from src.mlops.training import TrainingOrchestrator

mlops_router = APIRouter(prefix="/api/v1/mlops", tags=["MLOps"])


# ── Model Registry ────────────────────────────────────────────


@mlops_router.post("/models/register")
async def register_model(
    name: str,
    artifact_path: str,
    version: str | None = None,
    base_model: str | None = None,
    framework: str = "llama-cpp",
    description: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        model = await ModelRegistryService.register(
            db=db,
            name=name,
            artifact_path=artifact_path,
            version=version,
            base_model=base_model,
            framework=framework,
            description=description,
        )
        return {
            "id": model.id,
            "name": model.name,
            "version": model.version,
            "status": model.status.value,
            "artifact_path": model.artifact_path,
            "artifact_checksum": model.artifact_checksum,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@mlops_router.get("/models")
async def list_models(
    status: str | None = Query(None),
    name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    model_status = ModelStatus(status) if status else None
    models = await ModelRegistryService.list_models(
        db=db, status=model_status, name=name, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": m.id,
                "name": m.name,
                "version": m.version,
                "status": m.status.value,
                "artifact_path": m.artifact_path,
                "base_model": m.base_model,
                "metrics": m.metrics,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "deployed_at": m.deployed_at.isoformat() if m.deployed_at else None,
            }
            for m in models
        ]
    }


@mlops_router.post("/models/{model_id}/promote")
async def promote_model(
    model_id: int,
    target_status: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        status = ModelStatus(target_status)
        model = await ModelRegistryService.promote(db, model_id, status)
        return {
            "id": model.id,
            "name": model.name,
            "version": model.version,
            "status": model.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@mlops_router.post("/models/{model_id}/deploy")
async def deploy_model(
    model_id: int,
    strategy: str = "direct",
    traffic_percent: int = 100,
    db: AsyncSession = Depends(get_db),
):
    try:
        dep_strategy = DeploymentStrategy(strategy)
        model, deployment = await ModelRegistryService.deploy(
            db=db,
            model_id=model_id,
            strategy=dep_strategy,
            traffic_percent=traffic_percent,
        )
        return {
            "model": {"id": model.id, "name": model.name, "version": model.version},
            "deployment": {
                "id": deployment.id,
                "strategy": deployment.strategy.value,
                "traffic_percent": deployment.traffic_percent,
                "deployed_at": deployment.deployed_at.isoformat()
                if deployment.deployed_at
                else None,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@mlops_router.post("/deployments/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: int,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        dep = await ModelRegistryService.rollback(db, deployment_id, reason)
        return {"id": dep.id, "status": dep.status, "reason": dep.rollback_reason}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Dataset Pipeline ─────────────────────────────────────────


@mlops_router.post("/datasets/create-from-logs")
async def create_dataset_from_logs(
    name: str,
    hours: int = Query(168, ge=1, le=2160),
    min_tokens: int = Query(1, ge=0),
    max_drift: float = Query(1.0, ge=0.0, le=1.0),
    limit: int = Query(10000, ge=1, le=100000),
    db: AsyncSession = Depends(get_db),
):
    try:
        dataset = await DatasetPipeline.create_from_inference_logs(
            db=db,
            name=name,
            hours=hours,
            min_tokens=min_tokens,
            max_drift=max_drift,
            limit=limit,
        )
        return {
            "id": dataset.id,
            "name": dataset.name,
            "version": dataset.version,
            "record_count": dataset.record_count,
            "file_path": dataset.file_path,
            "quality_score": dataset.quality_score,
            "filters": dataset.filters,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@mlops_router.get("/datasets")
async def list_datasets(
    name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    datasets = await DatasetPipeline.list_datasets(
        db=db, name=name, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": d.id,
                "name": d.name,
                "version": d.version,
                "record_count": d.record_count,
                "quality_score": d.quality_score,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in datasets
        ]
    }


@mlops_router.get("/datasets/stats")
async def dataset_stats(db: AsyncSession = Depends(get_db)):
    return await DatasetPipeline.get_stats(db)


# ── Experiments ──────────────────────────────────────────────


@mlops_router.post("/experiments")
async def create_experiment(
    name: str,
    base_model: str,
    hyperparameters: dict,
    dataset_version: str | None = None,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    exp = await ExperimentTracker.create_experiment(
        db=db,
        name=name,
        base_model=base_model,
        hyperparameters=hyperparameters,
        dataset_version=dataset_version,
        notes=notes,
    )
    return {
        "id": exp.id,
        "name": exp.name,
        "base_model": exp.base_model,
        "hyperparameters": exp.hyperparameters,
        "status": exp.status.value,
        "started_at": exp.started_at.isoformat() if exp.started_at else None,
    }


@mlops_router.post("/experiments/{experiment_id}/metrics")
async def log_experiment_metric(
    experiment_id: int,
    step: int,
    metric_name: str,
    metric_value: float,
    db: AsyncSession = Depends(get_db),
):
    try:
        metric = await ExperimentTracker.log_metric(
            db=db,
            experiment_id=experiment_id,
            step=step,
            metric_name=metric_name,
            metric_value=metric_value,
        )
        return {
            "id": metric.id,
            "step": metric.step,
            "metric_name": metric.metric_name,
            "value": metric.metric_value,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@mlops_router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: int, db: AsyncSession = Depends(get_db)):
    exp, metrics = await ExperimentTracker.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {
        "id": exp.id,
        "name": exp.name,
        "base_model": exp.base_model,
        "hyperparameters": exp.hyperparameters,
        "status": exp.status.value,
        "best_metric": exp.best_metric,
        "best_metric_value": exp.best_metric_value,
        "total_steps": exp.total_steps,
        "metrics": [
            {"step": m.step, "name": m.metric_name, "value": m.metric_value}
            for m in metrics
        ],
    }


@mlops_router.get("/experiments")
async def list_experiments(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    exp_status = ExperimentStatus(status) if status else None
    experiments = await ExperimentTracker.list_experiments(
        db=db, status=exp_status, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": e.id,
                "name": e.name,
                "base_model": e.base_model,
                "status": e.status.value,
                "best_metric": e.best_metric,
                "best_metric_value": e.best_metric_value,
                "started_at": e.started_at.isoformat() if e.started_at else None,
            }
            for e in experiments
        ]
    }


@mlops_router.post("/experiments/compare")
async def compare_experiments(
    experiment_ids: list[int],
    metric_name: str,
    db: AsyncSession = Depends(get_db),
):
    return await ExperimentTracker.compare_experiments(db, experiment_ids, metric_name)


# ── Training Jobs ────────────────────────────────────────────


@mlops_router.post("/jobs")
async def create_training_job(
    name: str,
    config: dict,
    base_model_id: int | None = None,
    dataset_id: int | None = None,
    output_model_name: str | None = None,
    trigger_type: str = "manual",
    db: AsyncSession = Depends(get_db),
):
    job = await TrainingOrchestrator.create_job(
        db=db,
        name=name,
        config=config,
        base_model_id=base_model_id,
        dataset_id=dataset_id,
        output_model_name=output_model_name,
        trigger_type=trigger_type,
    )
    return {
        "id": job.id,
        "name": job.name,
        "status": job.status.value,
        "config": job.config,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@mlops_router.post("/jobs/{job_id}/start")
async def start_training_job(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        job = await TrainingOrchestrator.start_job(db, job_id)
        return {
            "id": job.id,
            "status": job.status.value,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@mlops_router.post("/jobs/{job_id}/complete")
async def complete_training_job(
    job_id: int,
    success: bool = True,
    error_message: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await TrainingOrchestrator.complete_job(
            db=db, job_id=job_id, success=success, error_message=error_message
        )
        return {"id": job.id, "status": job.status.value}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@mlops_router.post("/jobs/{job_id}/cancel")
async def cancel_training_job(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        job = await TrainingOrchestrator.cancel_job(db, job_id)
        return {"id": job.id, "status": job.status.value}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@mlops_router.get("/jobs")
async def list_training_jobs(
    status: str | None = Query(None),
    trigger_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    job_status = JobStatus(status) if status else None
    jobs = await TrainingOrchestrator.list_jobs(
        db=db, status=job_status, trigger_type=trigger_type, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": j.id,
                "name": j.name,
                "status": j.status.value,
                "trigger_type": j.trigger_type,
                "config": j.config,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "error_message": j.error_message,
            }
            for j in jobs
        ]
    }


# ── Drift-triggered Retraining ───────────────────────────────


@mlops_router.get("/drift-triggers")
async def list_drift_triggers(
    acknowledged: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    triggers = await DriftPipeline.list_triggers(
        db=db, acknowledged=acknowledged, limit=limit
    )
    return {
        "items": [
            {
                "id": t.id,
                "drift_score": t.drift_score,
                "threshold": t.threshold,
                "dataset_id": t.dataset_id,
                "training_job_id": t.training_job_id,
                "acknowledged": t.acknowledged,
                "auto_triggered": t.auto_triggered,
                "triggered_at": t.triggered_at.isoformat() if t.triggered_at else None,
            }
            for t in triggers
        ]
    }


@mlops_router.post("/drift-triggers/{trigger_id}/acknowledge")
async def acknowledge_trigger(trigger_id: int, db: AsyncSession = Depends(get_db)):
    try:
        trigger = await DriftPipeline.acknowledge_trigger(db, trigger_id)
        return {"id": trigger.id, "acknowledged": trigger.acknowledged}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Model Evaluation ──────────────────────────────────────────


@mlops_router.post("/evaluate")
async def evaluate_model(
    model_path: str | None = None,
    sample_size: int = Query(20, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.evaluation import ModelEvaluator

    try:
        result = await ModelEvaluator.evaluate_from_logs(db=db, sample_size=sample_size)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@mlops_router.post("/evaluate/custom")
async def evaluate_custom(
    test_cases: list[dict],
    model_path: str | None = None,
):
    from src.mlops.evaluation import ModelEvaluator

    try:
        evaluator = ModelEvaluator(test_cases=test_cases)
        return await evaluator.evaluate(model_path=model_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dataset Export ────────────────────────────────────────────


@mlops_router.get("/datasets/{dataset_id}/export")
async def export_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import FileResponse

    from src.mlops.dataset import DatasetPipeline

    dataset = await DatasetPipeline.get_dataset(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.file_path or not __import__("os").path.exists(dataset.file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found on disk")
    return FileResponse(
        path=dataset.file_path,
        media_type="application/json",
        filename=f"{dataset.name}-{dataset.version}.jsonl",
    )


# ── A/B Testing ───────────────────────────────────────────────


@mlops_router.get("/ab-test/compare")
async def compare_ab_deployments(
    deployment_a_id: int = Query(...),
    deployment_b_id: int = Query(...),
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.ab_testing import ABTestService

    return await ABTestService.get_comparison(
        db, deployment_a_id, deployment_b_id, hours
    )


# ── Usage Analytics ───────────────────────────────────────────


@mlops_router.get("/usage")
async def get_usage(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.usage import APIUsageTracker

    return await APIUsageTracker.get_usage(db, hours=hours)


@mlops_router.get("/usage/timeline")
async def get_usage_timeline(
    hours: int = Query(6, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.usage import APIUsageTracker

    return await APIUsageTracker.get_usage_by_minute(db, hours=hours)


# ── Model Router ──────────────────────────────────────────────


@mlops_router.get("/router/rules")
async def get_router_rules():
    from src.core.router import model_router

    return {"default": model_router._default, "rules": model_router.rules}


@mlops_router.post("/router/rules")
async def add_router_rule(pattern: str, model_path: str):
    from src.core.router import model_router

    model_router.add_rule(pattern, model_path)
    return {"rules": model_router.rules}


@mlops_router.delete("/router/rules")
async def remove_router_rule(pattern: str):
    from src.core.router import model_router

    model_router.remove_rule(pattern)
    return {"rules": model_router.rules}


# ── Audit Log ─────────────────────────────────────────────────


@mlops_router.get("/audit")
async def get_audit_logs(
    action: str | None = Query(None),
    actor: str | None = Query(None),
    resource_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    from src.core.audit import AuditAction, AuditService

    action_enum = AuditAction(action) if action else None
    logs = await AuditService.query(
        db=db,
        action=action_enum,
        actor=actor,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": log.id,
                "action": log.action.value if log.action else None,
                "actor": log.actor,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "detail": log.detail,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ]
    }


# ── Quantization ──────────────────────────────────────────────


@mlops_router.post("/models/{model_id}/quantize")
async def quantize_model(
    model_id: int,
    method: str = Query("q4_k_m"),
    output_name: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.quantization import QuantizationPipeline

    result = await QuantizationPipeline.quantize(
        db=db, source_model_id=model_id, method=method, output_name=output_name
    )
    if result.get("status") == "failed":
        raise HTTPException(
            status_code=400, detail=result.get("error", "Quantization failed")
        )
    return result


# ── Backup & Restore ──────────────────────────────────────────


@mlops_router.post("/backup")
async def create_backup():
    from src.mlops.backup import BackupService

    return await BackupService.create_backup()


@mlops_router.get("/backup")
async def list_backups():
    from src.mlops.backup import BackupService

    return await BackupService.list_backups()


# ── Prompt Templates ──────────────────────────────────────────


@mlops_router.get("/prompts")
async def list_prompt_templates(
    tag: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.prompts import PromptTemplateService

    templates = await PromptTemplateService.list_templates(
        db=db, tag=tag, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "template": t.template,
                "variables": t.variables,
                "tags": t.tags,
                "usage_count": t.usage_count,
            }
            for t in templates
        ]
    }


@mlops_router.post("/prompts")
async def create_prompt_template(
    name: str,
    template: str,
    description: str | None = None,
    variables: list[str] | None = None,
    tags: list[str] | None = None,
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.prompts import PromptTemplateService

    entry = await PromptTemplateService.create(
        db=db,
        name=name,
        template=template,
        description=description,
        variables=variables,
        tags=tags,
    )
    return {"id": entry.id, "name": entry.name}


@mlops_router.post("/prompts/{template_id}/render")
async def render_prompt_template(
    template_id: int,
    variables: dict[str, str],
    db: AsyncSession = Depends(get_db),
):
    from src.mlops.prompts import PromptTemplateService

    result = await PromptTemplateService.render(db, template_id, variables)
    if result is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"rendered": result}

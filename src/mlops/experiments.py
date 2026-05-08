from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import logger
from src.mlops.models import (
    ExperimentMetric,
    ExperimentStatus,
    TrainingExperiment,
)


class ExperimentTracker:
    @staticmethod
    async def create_experiment(
        db: AsyncSession,
        name: str,
        base_model: str,
        hyperparameters: dict,
        dataset_version: str | None = None,
        training_job_id: int | None = None,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> TrainingExperiment:
        experiment = TrainingExperiment(
            name=name,
            training_job_id=training_job_id,
            base_model=base_model,
            dataset_version=dataset_version,
            hyperparameters=hyperparameters,
            notes=notes,
            created_by=created_by,
        )
        db.add(experiment)
        await db.flush()
        logger.info(f"Experiment created: {name}")
        return experiment

    @staticmethod
    async def log_metric(
        db: AsyncSession,
        experiment_id: int,
        step: int,
        metric_name: str,
        metric_value: float,
    ) -> ExperimentMetric:
        metric = ExperimentMetric(
            experiment_id=experiment_id,
            step=step,
            metric_name=metric_name,
            metric_value=metric_value,
        )
        db.add(metric)

        experiment_result = await db.execute(
            select(TrainingExperiment).where(TrainingExperiment.id == experiment_id)
        )
        exp = experiment_result.scalar_one_or_none()
        if exp:
            exp.total_steps = max(exp.total_steps, step)
            if metric_name == "eval_loss":
                if (
                    exp.best_metric_value is None
                    or metric_value < exp.best_metric_value
                ):
                    exp.best_metric = "eval_loss"
                    exp.best_metric_value = metric_value
            elif metric_name == "eval_accuracy":
                if (
                    exp.best_metric_value is None
                    or metric_value > exp.best_metric_value
                ):
                    exp.best_metric = "eval_accuracy"
                    exp.best_metric_value = metric_value

        await db.flush()
        return metric

    @staticmethod
    async def complete_experiment(
        db: AsyncSession,
        experiment_id: int,
        status: ExperimentStatus = ExperimentStatus.COMPLETED,
        artifact_path: str | None = None,
    ) -> TrainingExperiment:
        result = await db.execute(
            select(TrainingExperiment).where(TrainingExperiment.id == experiment_id)
        )
        exp = result.scalar_one_or_none()
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        exp.status = status
        exp.completed_at = datetime.now(timezone.utc)
        if artifact_path:
            exp.artifact_path = artifact_path
        await db.flush()
        logger.info(f"Experiment {exp.name} completed: {status.value}")
        return exp

    @staticmethod
    async def get_experiment(
        db: AsyncSession, experiment_id: int
    ) -> tuple[TrainingExperiment | None, list[ExperimentMetric]]:
        exp_result = await db.execute(
            select(TrainingExperiment).where(TrainingExperiment.id == experiment_id)
        )
        exp = exp_result.scalar_one_or_none()

        metrics_result = await db.execute(
            select(ExperimentMetric)
            .where(ExperimentMetric.experiment_id == experiment_id)
            .order_by(ExperimentMetric.step, ExperimentMetric.metric_name)
        )
        metrics = list(metrics_result.scalars().all())
        return exp, metrics

    @staticmethod
    async def list_experiments(
        db: AsyncSession,
        status: ExperimentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TrainingExperiment]:
        query = select(TrainingExperiment).order_by(desc(TrainingExperiment.started_at))
        if status:
            query = query.where(TrainingExperiment.status == status)
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def compare_experiments(
        db: AsyncSession,
        experiment_ids: list[int],
        metric_name: str,
    ) -> dict:
        data = {}
        for eid in experiment_ids:
            result = await db.execute(
                select(ExperimentMetric)
                .where(
                    ExperimentMetric.experiment_id == eid,
                    ExperimentMetric.metric_name == metric_name,
                )
                .order_by(ExperimentMetric.step)
            )
            metrics = result.scalars().all()
            if metrics:
                best = (
                    min(m.value for m in metrics)
                    if "loss" in metric_name
                    else max(m.value for m in metrics)
                )
                data[str(eid)] = {
                    "final_value": metrics[-1].metric_value,
                    "best_value": best,
                    "steps": len(metrics),
                }
        return data

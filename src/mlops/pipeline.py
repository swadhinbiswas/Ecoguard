from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import logger
from src.mlops.dataset import DatasetPipeline
from src.mlops.models import RetrainingTrigger
from src.mlops.training import TrainingOrchestrator


class DriftPipeline:
    @staticmethod
    async def check_and_trigger(
        db: AsyncSession,
        drift_score: float,
        threshold: float | None = None,
    ) -> RetrainingTrigger | None:
        threshold = threshold or settings.drift_alert_threshold

        if drift_score < threshold:
            return None

        recent_result = await db.execute(
            select(RetrainingTrigger)
            .where(
                RetrainingTrigger.auto_triggered,
            )
            .order_by(RetrainingTrigger.triggered_at.desc())
            .limit(1)
        )
        recent = recent_result.scalar_one_or_none()

        if recent:
            cooldown = (
                datetime.now(timezone.utc) - recent.triggered_at
            ).total_seconds()
            if cooldown < 3600:
                logger.debug(f"Retraining cooldown active ({cooldown:.0f}s remaining)")
                return None

        dataset = await DatasetPipeline.create_from_inference_logs(
            db=db,
            name=f"drift-trigger-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
            hours=168,
            min_tokens=4,
            max_drift=drift_score,
            limit=5000,
            created_by="drift-pipeline",
        )

        job_config = {
            "method": "qlora",
            "base_model": settings.model_path,
            "dataset_id": dataset.id,
            "epochs": 3,
            "learning_rate": 2e-4,
            "lora_r": 8,
            "lora_alpha": 16,
        }

        training_job = await TrainingOrchestrator.create_job(
            db=db,
            name=f"drift-retrain-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
            config=job_config,
            dataset_id=dataset.id,
            output_model_name=f"eco-guard-drift-fix-v{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            trigger_type="drift",
            trigger_detail={
                "drift_score": drift_score,
                "threshold": threshold,
            },
            created_by="drift-pipeline",
        )

        trigger = RetrainingTrigger(
            drift_score=drift_score,
            threshold=threshold,
            dataset_id=dataset.id,
            training_job_id=training_job.id,
            auto_triggered=True,
        )
        db.add(trigger)
        await db.flush()

        logger.warning(
            f"DRIFT-TRIGGERED RETRAINING: score={drift_score:.4f}, "
            f"dataset={dataset.id} ({dataset.record_count} records), "
            f"job={training_job.id}"
        )

        return trigger

    @staticmethod
    async def list_triggers(
        db: AsyncSession,
        acknowledged: bool | None = None,
        limit: int = 50,
    ) -> list[RetrainingTrigger]:
        query = select(RetrainingTrigger).order_by(
            RetrainingTrigger.triggered_at.desc()
        )
        if acknowledged is not None:
            query = query.where(RetrainingTrigger.acknowledged == acknowledged)
        result = await db.execute(query.limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def acknowledge_trigger(
        db: AsyncSession, trigger_id: int
    ) -> RetrainingTrigger:
        result = await db.execute(
            select(RetrainingTrigger).where(RetrainingTrigger.id == trigger_id)
        )
        trigger = result.scalar_one_or_none()
        if not trigger:
            raise ValueError(f"Trigger {trigger_id} not found")

        trigger.acknowledged = True
        trigger.acknowledged_at = datetime.now(timezone.utc)
        await db.flush()
        return trigger

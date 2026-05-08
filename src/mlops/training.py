from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from src.mlops.models import TrainingJob, JobStatus
from src.core.logging import logger


class TrainingOrchestrator:
    @staticmethod
    async def create_job(
        db: AsyncSession,
        name: str,
        config: dict,
        base_model_id: int | None = None,
        dataset_id: int | None = None,
        output_model_name: str | None = None,
        trigger_type: str = "manual",
        trigger_detail: dict | None = None,
        created_by: str | None = None,
    ) -> TrainingJob:
        job = TrainingJob(
            name=name,
            config=config,
            base_model_id=base_model_id,
            dataset_id=dataset_id,
            output_model_name=output_model_name,
            trigger_type=trigger_type,
            trigger_detail=trigger_detail,
            created_by=created_by,
        )
        db.add(job)
        await db.flush()
        logger.info(f"Training job created: {name} (trigger: {trigger_type})")
        return job

    @staticmethod
    async def start_job(db: AsyncSession, job_id: int) -> TrainingJob:
        result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status != JobStatus.QUEUED:
            raise ValueError(f"Job {job_id} is not queued (status: {job.status.value})")

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info(f"Training job started: {job.name}")

        return job

    @staticmethod
    async def complete_job(
        db: AsyncSession,
        job_id: int,
        success: bool = True,
        error_message: str | None = None,
    ) -> TrainingJob:
        result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        if error_message:
            job.error_message = error_message
        await db.flush()
        logger.info(f"Training job {job.name}: {job.status.value}")
        return job

    @staticmethod
    async def cancel_job(db: AsyncSession, job_id: int) -> TrainingJob:
        result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await db.flush()
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: int) -> TrainingJob | None:
        result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        status: JobStatus | None = None,
        trigger_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TrainingJob]:
        query = select(TrainingJob).order_by(desc(TrainingJob.created_at))
        if status:
            query = query.where(TrainingJob.status == status)
        if trigger_type:
            query = query.where(TrainingJob.trigger_type == trigger_type)
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

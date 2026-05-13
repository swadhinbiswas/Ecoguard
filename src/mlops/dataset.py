import json
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import logger
from src.mlops.models import Dataset
from src.models.inference import InferenceLog


class DatasetPipeline:
    @staticmethod
    async def create_from_inference_logs(
        db: AsyncSession,
        name: str,
        hours: int = 168,
        min_tokens: int = 1,
        max_drift: float = 1.0,
        limit: int = 10000,
        created_by: str | None = None,
    ) -> Dataset:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = (
            select(InferenceLog)
            .where(
                InferenceLog.timestamp >= cutoff,
                InferenceLog.token_count >= min_tokens,
            )
            .order_by(desc(InferenceLog.timestamp))
            .limit(limit)
        )
        result = await db.execute(query)
        logs = result.scalars().all()

        records = []
        for log in logs:
            if log.drift_score and log.drift_score > max_drift:
                continue
            if not log.prediction_output or not log.prediction_output.strip():
                continue
            records.append(
                {
                    "input": log.input_text,
                    "output": log.prediction_output,
                    "latency_ms": log.latency_ms,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                }
            )

        version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dataset_dir = os.path.join("datasets", name)
        os.makedirs(dataset_dir, exist_ok=True)
        file_path = os.path.join(dataset_dir, f"{version}.jsonl")

        with open(file_path, "w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

        quality_score = len(records) / max(len(logs), 1)

        dataset = Dataset(
            name=name,
            version=version,
            format="jsonl",
            file_path=file_path,
            record_count=len(records),
            source="inference_logs",
            filters={
                "hours": hours,
                "min_tokens": min_tokens,
                "max_drift": max_drift,
            },
            quality_score=round(quality_score, 4),
            created_by=created_by,
        )
        db.add(dataset)
        await db.flush()
        logger.info(f"Dataset created: {name} v{version} ({len(records)} records)")
        return dataset

    @staticmethod
    async def get_dataset(db: AsyncSession, dataset_id: int) -> Dataset | None:
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_datasets(
        db: AsyncSession,
        name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Dataset]:
        query = select(Dataset).order_by(desc(Dataset.created_at))
        if name:
            query = query.where(Dataset.name == name)
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_stats(db: AsyncSession) -> dict:
        result = await db.execute(
            select(
                func.count(Dataset.id).label("total"),
                func.sum(Dataset.record_count).label("total_records"),
            )
        )
        row = result.one_or_none()
        return {
            "total_datasets": int(row.total) if row and row.total else 0,
            "total_records": int(row.total_records) if row and row.total_records else 0,
        }

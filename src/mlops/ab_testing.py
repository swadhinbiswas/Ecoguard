import random
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.mlops.models import (
    Deployment,
    DeploymentStrategy,
    ModelRegistry,
)
from src.models.inference import InferenceLog


class ABTestService:
    @staticmethod
    async def route_to_model(
        db: AsyncSession,
        request_id: str,
    ) -> tuple[Optional[ModelRegistry], Optional[str]]:
        result = await db.execute(
            select(Deployment)
            .where(Deployment.status == "active")
            .order_by(desc(Deployment.deployed_at))
        )
        deployments = result.scalars().all()

        direct_deps = [
            d for d in deployments if d.strategy == DeploymentStrategy.DIRECT
        ]
        if direct_deps:
            model_result = await db.execute(
                select(ModelRegistry).where(ModelRegistry.id == direct_deps[0].model_id)
            )
            return model_result.scalar_one_or_none(), "direct"

        canary_deps = [
            d for d in deployments if d.strategy == DeploymentStrategy.CANARY
        ]
        if canary_deps:
            dep = canary_deps[0]
            if random.random() * 100 < dep.traffic_percent:
                model_result = await db.execute(
                    select(ModelRegistry).where(ModelRegistry.id == dep.model_id)
                )
                return model_result.scalar_one_or_none(), "canary_new"

            prev_result = await db.execute(
                select(Deployment)
                .where(Deployment.status == "superseded")
                .order_by(desc(Deployment.deployed_at))
                .limit(1)
            )
            prev = prev_result.scalar_one_or_none()
            if prev:
                model_result = await db.execute(
                    select(ModelRegistry).where(ModelRegistry.id == prev.model_id)
                )
                return model_result.scalar_one_or_none(), "canary_baseline"

        ab_deps = [d for d in deployments if d.strategy == DeploymentStrategy.AB_TEST]
        if ab_deps:
            dep = ab_deps[0]
            bucket = hash(request_id) % 100
            if bucket < dep.traffic_percent:
                model_result = await db.execute(
                    select(ModelRegistry).where(ModelRegistry.id == dep.model_id)
                )
                return model_result.scalar_one_or_none(), "ab_variant_a"

            prev_result = await db.execute(
                select(Deployment)
                .where(Deployment.status == "superseded")
                .order_by(desc(Deployment.deployed_at))
                .limit(1)
            )
            prev = prev_result.scalar_one_or_none()
            if prev:
                model_result = await db.execute(
                    select(ModelRegistry).where(ModelRegistry.id == prev.model_id)
                )
                return model_result.scalar_one_or_none(), "ab_variant_b"

        return None, None

    @staticmethod
    async def get_comparison(
        db: AsyncSession,
        deployment_a_id: int,
        deployment_b_id: int,
        hours: int = 24,
    ) -> dict:
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        async def stats_for_deployment(dep_id: int) -> dict:
            dep_result = await db.execute(
                select(Deployment).where(Deployment.id == dep_id)
            )
            dep = dep_result.scalar_one_or_none()
            if not dep:
                return {"error": "not found"}

            model_result = await db.execute(
                select(ModelRegistry).where(ModelRegistry.id == dep.model_id)
            )
            model = model_result.scalar_one_or_none()

            log_result = await db.execute(
                select(
                    func.count(InferenceLog.id).label("total"),
                    func.avg(InferenceLog.latency_ms).label("avg_lat"),
                    func.avg(InferenceLog.token_count).label("avg_tok"),
                    func.avg(InferenceLog.drift_score).label("avg_drift"),
                ).where(InferenceLog.timestamp >= cutoff)
            )
            row = log_result.one_or_none()
            return {
                "model_name": model.name if model else "unknown",
                "model_version": model.version if model else "unknown",
                "total_requests": int(row.total) if row and row.total else 0,
                "avg_latency_ms": round(float(row.avg_lat), 2)
                if row and row.avg_lat
                else 0,
                "avg_tokens": round(float(row.avg_tok), 2)
                if row and row.avg_tok
                else 0,
                "avg_drift": round(float(row.avg_drift), 4)
                if row and row.avg_drift
                else 0,
            }

        return {
            "deployment_a": await stats_for_deployment(deployment_a_id),
            "deployment_b": await stats_for_deployment(deployment_b_id),
        }

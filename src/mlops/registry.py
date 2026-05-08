import hashlib
import os
from datetime import datetime, timezone

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.logging import logger
from src.mlops.models import (
    Deployment,
    DeploymentStrategy,
    ModelRegistry,
    ModelStatus,
)


class ModelRegistryService:
    @staticmethod
    def _compute_checksum(filepath: str) -> str:
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    async def register(
        db: AsyncSession,
        name: str,
        artifact_path: str,
        version: str | None = None,
        base_model: str | None = None,
        framework: str = "llama-cpp",
        parameters: dict | None = None,
        metrics: dict | None = None,
        tags: dict | None = None,
        description: str | None = None,
        created_by: str | None = None,
    ) -> ModelRegistry:
        if version is None:
            version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        checksum = None
        if os.path.exists(artifact_path):
            checksum = ModelRegistryService._compute_checksum(artifact_path)

        entry = ModelRegistry(
            name=name,
            version=version,
            artifact_path=artifact_path,
            artifact_checksum=checksum,
            base_model=base_model,
            framework=framework,
            parameters=parameters,
            metrics=metrics,
            tags=tags,
            description=description,
            created_by=created_by,
        )
        db.add(entry)
        await db.flush()
        logger.info(f"Model registered: {name} v{version}")
        return entry

    @staticmethod
    async def promote(
        db: AsyncSession,
        model_id: int,
        target_status: ModelStatus,
    ) -> ModelRegistry:
        result = await db.execute(
            select(ModelRegistry).where(ModelRegistry.id == model_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Model {model_id} not found")

        if target_status == ModelStatus.PRODUCTION:
            await db.execute(
                update(ModelRegistry)
                .where(
                    ModelRegistry.status == ModelStatus.PRODUCTION,
                    ModelRegistry.name == model.name,
                )
                .values(status=ModelStatus.ARCHIVED)
            )

        model.status = target_status
        if target_status == ModelStatus.PRODUCTION:
            model.deployed_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info(f"Model {model.name} promoted to {target_status.value}")
        return model

    @staticmethod
    async def list_models(
        db: AsyncSession,
        status: ModelStatus | None = None,
        name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ModelRegistry]:
        query = select(ModelRegistry).order_by(desc(ModelRegistry.created_at))
        if status:
            query = query.where(ModelRegistry.status == status)
        if name:
            query = query.where(ModelRegistry.name == name)
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_production_model(
        db: AsyncSession, name: str | None = None
    ) -> ModelRegistry | None:
        query = select(ModelRegistry).where(
            ModelRegistry.status == ModelStatus.PRODUCTION
        )
        if name:
            query = query.where(ModelRegistry.name == name)
        query = query.order_by(desc(ModelRegistry.deployed_at)).limit(1)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def deploy(
        db: AsyncSession,
        model_id: int,
        strategy: DeploymentStrategy = DeploymentStrategy.DIRECT,
        traffic_percent: int = 100,
        config: dict | None = None,
        deployed_by: str | None = None,
    ) -> tuple[ModelRegistry, Deployment]:
        model = await ModelRegistryService.promote(db, model_id, ModelStatus.PRODUCTION)

        if strategy != DeploymentStrategy.DIRECT:
            await db.execute(
                update(Deployment)
                .where(Deployment.status == "active")
                .values(status="superseded")
            )

        deployment = Deployment(
            model_id=model_id,
            strategy=strategy,
            traffic_percent=traffic_percent,
            config=config,
            deployed_by=deployed_by,
        )
        db.add(deployment)
        await db.flush()

        if strategy == DeploymentStrategy.DIRECT and os.path.exists(
            model.artifact_path
        ):
            try:
                get_backend().load(model.artifact_path)
            except Exception as e:
                logger.error(f"Failed to hot-swap model: {e}")

        return model, deployment

    @staticmethod
    async def rollback(
        db: AsyncSession,
        deployment_id: int,
        reason: str | None = None,
    ) -> Deployment:
        result = await db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        dep = result.scalar_one_or_none()
        if not dep:
            raise ValueError(f"Deployment {deployment_id} not found")

        dep.status = "rolled_back"
        dep.rolled_back_at = datetime.now(timezone.utc)
        dep.rollback_reason = reason

        model_result = await db.execute(
            select(ModelRegistry).where(ModelRegistry.id == dep.model_id)
        )
        model = model_result.scalar_one_or_none()
        if model:
            model.status = ModelStatus.ARCHIVED

        # Find previous production model
        prev_result = await db.execute(
            select(ModelRegistry)
            .where(
                ModelRegistry.status == ModelStatus.ARCHIVED,
                ModelRegistry.name == model.name if model else True,
            )
            .order_by(desc(ModelRegistry.deployed_at))
            .limit(1)
        )
        prev = prev_result.scalar_one_or_none()
        if prev:
            prev.status = ModelStatus.PRODUCTION

            if os.path.exists(prev.artifact_path):
                try:
                    get_backend().load(prev.artifact_path)
                except Exception as e:
                    logger.error(f"Failed to rollback model: {e}")

        await db.flush()
        logger.info(f"Deployment {deployment_id} rolled back: {reason}")
        return dep

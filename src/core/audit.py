from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    desc,
    select,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import logger
from src.db.database import Base


class AuditAction(str, Enum):
    MODEL_REGISTERED = "model_registered"
    MODEL_PROMOTED = "model_promoted"
    MODEL_DEPLOYED = "model_deployed"
    MODEL_ROLLBACK = "model_rollback"
    DATASET_CREATED = "dataset_created"
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_CANCELLED = "job_cancelled"
    EXPERIMENT_CREATED = "experiment_created"
    TRIGGER_ACKNOWLEDGED = "trigger_acknowledged"
    CACHE_CLEARED = "cache_cleared"
    INFERENCE_REQUEST = "inference_request"
    DEPLOYMENT_ROLLBACK = "deployment_rollback"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(SAEnum(AuditAction), nullable=False, index=True)
    actor = Column(String, nullable=True, index=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    timestamp = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AuditService:
    @staticmethod
    async def log(
        db: AsyncSession,
        action: AuditAction,
        actor: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        detail: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            actor=actor or "system",
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        await db.flush()
        logger.debug(
            f"Audit: {action.value} by {actor or 'system'} on {resource_type}/{resource_id}"
        )
        return entry

    @staticmethod
    async def query(
        db: AsyncSession,
        action: AuditAction | None = None,
        actor: str | None = None,
        resource_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        q = select(AuditLog).order_by(desc(AuditLog.timestamp))
        if action:
            q = q.where(AuditLog.action == action)
        if actor:
            q = q.where(AuditLog.actor == actor)
        if resource_type:
            q = q.where(AuditLog.resource_type == resource_type)
        result = await db.execute(q.offset(offset).limit(limit))
        return list(result.scalars().all())

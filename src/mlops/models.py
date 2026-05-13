import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)

from src.db.database import Base


class ModelStatus(str, enum.Enum):
    REGISTERED = "registered"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    status = Column(SAEnum(ModelStatus), default=ModelStatus.REGISTERED, nullable=False)
    artifact_path = Column(String, nullable=False)
    artifact_checksum = Column(String, nullable=True)
    base_model = Column(String, nullable=True)
    framework = Column(String, default="llama-cpp")
    parameters = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingJob(Base):
    __tablename__ = "training_jobs"
    __table_args__ = (
        Index("ix_training_jobs_status", "status"),
        Index("ix_training_jobs_trigger_type", "trigger_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    base_model_id = Column(Integer, ForeignKey("model_registry.id"), nullable=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    config = Column(JSON, nullable=False)
    output_model_name = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    trigger_type = Column(String, default="manual")
    trigger_detail = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by = Column(String, nullable=True)


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    format = Column(String, default="jsonl")
    file_path = Column(String, nullable=True)
    record_count = Column(Integer, default=0)
    source = Column(String, nullable=True)
    filters = Column(JSON, nullable=True)
    quality_score = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by = Column(String, nullable=True)


class DeploymentStrategy(str, enum.Enum):
    DIRECT = "direct"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    AB_TEST = "ab_test"


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        Index("ix_deployments_status", "status"),
        Index("ix_deployments_model_id", "model_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("model_registry.id"), nullable=False)
    strategy = Column(
        SAEnum(DeploymentStrategy), default=DeploymentStrategy.DIRECT, nullable=False
    )
    status = Column(String, default="active")
    traffic_percent = Column(Integer, default=100)
    config = Column(JSON, nullable=True)
    deployed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)
    rollback_reason = Column(Text, nullable=True)
    deployed_by = Column(String, nullable=True)


class ExperimentStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingExperiment(Base):
    __tablename__ = "training_experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    training_job_id = Column(Integer, ForeignKey("training_jobs.id"), nullable=True)
    base_model = Column(String, nullable=False)
    dataset_version = Column(String, nullable=True)
    hyperparameters = Column(JSON, nullable=False)
    status = Column(
        SAEnum(ExperimentStatus), default=ExperimentStatus.RUNNING, nullable=False
    )
    best_metric = Column(String, nullable=True)
    best_metric_value = Column(Float, nullable=True)
    total_steps = Column(Integer, default=0)
    artifact_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    started_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)


class ExperimentMetric(Base):
    __tablename__ = "experiment_metrics"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(
        Integer, ForeignKey("training_experiments.id"), index=True, nullable=False
    )
    step = Column(Integer, nullable=False)
    metric_name = Column(String, index=True, nullable=False)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class RetrainingTrigger(Base):
    __tablename__ = "retraining_triggers"
    __table_args__ = (
        Index("ix_retraining_triggers_acknowledged", "acknowledged"),
        Index("ix_retraining_triggers_triggered_at", "triggered_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    drift_score = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    training_job_id = Column(Integer, ForeignKey("training_jobs.id"), nullable=True)
    acknowledged = Column(Boolean, default=False)
    auto_triggered = Column(Boolean, default=False)
    triggered_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

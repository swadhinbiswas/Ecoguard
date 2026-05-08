"""Add MLOps tables: model_registry, datasets, training_jobs, deployments, experiments, triggers

Revision ID: 002
Revises: 001
Create Date: 2024-06-01 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, index=True, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("status", sa.String, default="registered", nullable=False),
        sa.Column("artifact_path", sa.String, nullable=False),
        sa.Column("artifact_checksum", sa.String, nullable=True),
        sa.Column("base_model", sa.String, nullable=True),
        sa.Column("framework", sa.String, default="llama-cpp"),
        sa.Column("parameters", sa.JSON, nullable=True),
        sa.Column("metrics", sa.JSON, nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String, nullable=True),
    )

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, index=True, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("format", sa.String, default="jsonl"),
        sa.Column("file_path", sa.String, nullable=True),
        sa.Column("record_count", sa.Integer, default=0),
        sa.Column("source", sa.String, nullable=True),
        sa.Column("filters", sa.JSON, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String, nullable=True),
    )

    op.create_table(
        "training_jobs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, index=True, nullable=False),
        sa.Column("status", sa.String, default="queued", nullable=False),
        sa.Column(
            "base_model_id",
            sa.Integer,
            sa.ForeignKey("model_registry.id"),
            nullable=True,
        ),
        sa.Column(
            "dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=True
        ),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("output_model_name", sa.String, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("trigger_type", sa.String, default="manual"),
        sa.Column("trigger_detail", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String, nullable=True),
    )

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "model_id", sa.Integer, sa.ForeignKey("model_registry.id"), nullable=False
        ),
        sa.Column("strategy", sa.String, default="direct", nullable=False),
        sa.Column("status", sa.String, default="active"),
        sa.Column("traffic_percent", sa.Integer, default=100),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True)),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_reason", sa.Text, nullable=True),
        sa.Column("deployed_by", sa.String, nullable=True),
    )

    op.create_table(
        "training_experiments",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, index=True, nullable=False),
        sa.Column(
            "training_job_id",
            sa.Integer,
            sa.ForeignKey("training_jobs.id"),
            nullable=True,
        ),
        sa.Column("base_model", sa.String, nullable=False),
        sa.Column("dataset_version", sa.String, nullable=True),
        sa.Column("hyperparameters", sa.JSON, nullable=False),
        sa.Column("status", sa.String, default="running", nullable=False),
        sa.Column("best_metric", sa.String, nullable=True),
        sa.Column("best_metric_value", sa.Float, nullable=True),
        sa.Column("total_steps", sa.Integer, default=0),
        sa.Column("artifact_path", sa.String, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String, nullable=True),
    )

    op.create_table(
        "experiment_metrics",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "experiment_id",
            sa.Integer,
            sa.ForeignKey("training_experiments.id"),
            index=True,
            nullable=False,
        ),
        sa.Column("step", sa.Integer, nullable=False),
        sa.Column("metric_name", sa.String, index=True, nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "retraining_triggers",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("drift_score", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column(
            "dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=True
        ),
        sa.Column(
            "training_job_id",
            sa.Integer,
            sa.ForeignKey("training_jobs.id"),
            nullable=True,
        ),
        sa.Column("acknowledged", sa.Boolean, default=False),
        sa.Column("auto_triggered", sa.Boolean, default=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("retraining_triggers")
    op.drop_table("experiment_metrics")
    op.drop_table("training_experiments")
    op.drop_table("deployments")
    op.drop_table("training_jobs")
    op.drop_table("datasets")
    op.drop_table("model_registry")

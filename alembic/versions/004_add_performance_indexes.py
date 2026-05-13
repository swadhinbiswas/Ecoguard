"""Add performance indexes for production workloads

Revision ID: 004
Revises: 003
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_inference_logs_timestamp", "inference_logs", ["timestamp"])
    op.create_index("ix_training_jobs_status", "training_jobs", ["status"])
    op.create_index("ix_training_jobs_trigger_type", "training_jobs", ["trigger_type"])
    op.create_index(
        "ix_retraining_triggers_acknowledged",
        "retraining_triggers",
        ["acknowledged"],
    )
    op.create_index(
        "ix_retraining_triggers_triggered_at",
        "retraining_triggers",
        ["triggered_at"],
    )
    op.create_index("ix_deployments_status", "deployments", ["status"])
    op.create_index("ix_deployments_model_id", "deployments", ["model_id"])


def downgrade() -> None:
    op.drop_index("ix_deployments_model_id", "deployments")
    op.drop_index("ix_deployments_status", "deployments")
    op.drop_index("ix_retraining_triggers_triggered_at", "retraining_triggers")
    op.drop_index("ix_retraining_triggers_acknowledged", "retraining_triggers")
    op.drop_index("ix_training_jobs_trigger_type", "training_jobs")
    op.drop_index("ix_training_jobs_status", "training_jobs")
    op.drop_index("ix_inference_logs_timestamp", "inference_logs")

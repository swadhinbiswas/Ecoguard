"""Add budgets, scaling_rules, regression_checks, anomaly_logs, scheduled_jobs, scheduled_job_runs, audit_entries

Revision ID: 010
Revises: 009
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("workspace_id", sa.Integer, index=True, nullable=False),
        sa.Column("period", sa.String(16), default="monthly"),
        sa.Column("cap_amount_usd", sa.Float, nullable=False),
        sa.Column("current_spend", sa.Float, default=0.0),
        sa.Column("alert_threshold_pct", sa.Float, default=80.0),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_alert_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
    )

    op.create_table(
        "scaling_rules",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(128), index=True, nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("condition", sa.String(8), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("action_value", sa.JSON, nullable=True),
        sa.Column("cooldown_minutes", sa.Integer, default=5),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean, default=True),
    )

    op.create_table(
        "regression_checks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("model_id", sa.Integer, index=True, nullable=False),
        sa.Column("baseline_model_id", sa.Integer, nullable=False),
        sa.Column("test_suite_name", sa.String(128), nullable=False),
        sa.Column("baseline_score", sa.Float, nullable=False),
        sa.Column("new_score", sa.Float, nullable=False),
        sa.Column("score_delta", sa.Float, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("max_allowed_degradation", sa.Float, default=0.05),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("details", sa.JSON, nullable=True),
    )

    op.create_table(
        "anomaly_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("request_id", sa.String(64), index=True),
        sa.Column("anomaly_type", sa.String(32), nullable=False),
        sa.Column("prompt_preview", sa.Text),
        sa.Column("score", sa.Float),
        sa.Column("details", sa.JSON),
        sa.Column("detected_at", sa.DateTime(timezone=True)),
        sa.Column("blocked", sa.Boolean, default=False),
    )

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(128), index=True, nullable=False),
        sa.Column("cron_expression", sa.String(64), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("max_tokens", sa.Integer, default=128),
        sa.Column("temperature", sa.Float, default=0.7),
        sa.Column("webhook_url", sa.String(512), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "scheduled_job_runs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("job_id", sa.Integer, index=True, nullable=False),
        sa.Column("status", sa.String(16), default="running"),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("action", sa.String(64), index=True, nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.Integer, nullable=True),
        sa.Column("username", sa.String(128), index=True, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_entries")
    op.drop_table("scheduled_job_runs")
    op.drop_table("scheduled_jobs")
    op.drop_table("anomaly_logs")
    op.drop_table("regression_checks")
    op.drop_table("scaling_rules")
    op.drop_table("budgets")

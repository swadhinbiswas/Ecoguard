"""Add prompt_templates and alert_rules tables

Revision ID: 009
Revises: 008
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(128), index=True, nullable=False),
        sa.Column("category", sa.String(64), index=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("variables", sa.JSON, default=[]),
        sa.Column("tags", sa.JSON, default=[]),
        sa.Column("usage_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String, nullable=True),
    )

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(128), index=True, nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("condition", sa.String(8), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("window_minutes", sa.Integer, default=15),
        sa.Column("cooldown_minutes", sa.Integer, default=30),
        sa.Column("webhook_url", sa.String(512), nullable=True),
        sa.Column("email_alert", sa.Boolean, default=False),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("alert_rules")
    op.drop_table("prompt_templates")

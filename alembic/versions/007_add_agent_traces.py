"""Add agent_traces table for tree-based agent tracing

Revision ID: 007
Revises: 006
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_traces",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("trace_id", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("session_id", sa.String(64), index=True, nullable=True),
        sa.Column("parent_span_id", sa.String(64), nullable=True),
        sa.Column("span_id", sa.String(64), nullable=False, index=True),
        sa.Column("span_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("input_data", sa.JSON, nullable=True),
        sa.Column("output_data", sa.JSON, nullable=True),
        sa.Column("status", sa.String(16), default="running"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("metadata_info", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_traces")

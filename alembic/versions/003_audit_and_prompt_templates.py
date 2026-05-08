"""Add audit log and prompt template tables

Revision ID: 003
Revises: 002
Create Date: 2026-05-08 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("action", sa.String, nullable=False, index=True),
        sa.Column("actor", sa.String, nullable=True, index=True),
        sa.Column("resource_type", sa.String, nullable=True),
        sa.Column("resource_id", sa.String, nullable=True),
        sa.Column("detail", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("user_agent", sa.String, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, unique=True, index=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("variables", sa.JSON, nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("usage_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("prompt_templates")
    op.drop_table("audit_logs")

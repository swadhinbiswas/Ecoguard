"""Add prompt_versions, ab_test_results, and user_feedback tables

Revision ID: 006
Revises: 005
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(128), index=True, nullable=False),
        sa.Column("version", sa.Integer, default=1, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("variables", sa.JSON, default=[]),
        sa.Column("metadata_info", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
    )

    op.create_table(
        "ab_test_results",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("test_name", sa.String(128), index=True, nullable=False),
        sa.Column("variant", sa.String(8), nullable=False),
        sa.Column("prompt_version_id", sa.Integer, nullable=True),
        sa.Column("output", sa.Text, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("feedback_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("request_id", sa.String, index=True, nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("feedback_text", sa.Text, nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_feedback")
    op.drop_table("ab_test_results")
    op.drop_table("prompt_versions")

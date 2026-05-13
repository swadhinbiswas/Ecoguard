"""Add workspaces, workspace members, API keys with scopes, and token quotas

Revision ID: 005
Revises: 004
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(128), unique=True, index=True, nullable=False),
        sa.Column("slug", sa.String(128), unique=True, index=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String, nullable=True),
        sa.Column("settings", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "workspace_id",
            sa.Integer,
            sa.ForeignKey("workspaces.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("username", sa.String(128), nullable=False, index=True),
        sa.Column("role", sa.String(32), default="member", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "workspace_api_keys",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "workspace_id",
            sa.Integer,
            sa.ForeignKey("workspaces.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("key_hash", sa.String(128), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("scopes", sa.JSON, default=[]),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
    )

    op.create_table(
        "token_quotas",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "workspace_id",
            sa.Integer,
            sa.ForeignKey("workspaces.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("period", sa.String(16), default="monthly"),
        sa.Column("max_tokens", sa.Integer, nullable=False),
        sa.Column("current_tokens", sa.Integer, default=0),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("token_quotas")
    op.drop_table("workspace_api_keys")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")

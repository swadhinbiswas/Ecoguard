"""Add documents and document_chunks tables for RAG pipeline

Revision ID: 008
Revises: 007
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(256), index=True, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source", sa.String(256), nullable=True),
        sa.Column("content_hash", sa.String(64), index=True),
        sa.Column("chunk_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_info", sa.JSON, nullable=True),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("document_id", sa.Integer, index=True, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.JSON, nullable=True),
        sa.Column("token_count", sa.Integer, default=0),
    )
    op.create_index("ix_chunks_doc_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_doc_id", "document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("documents")

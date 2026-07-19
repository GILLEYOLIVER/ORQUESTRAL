"""Estabiliza embeddings com pgvector.

Revision ID: 20260718_0013
Revises: 20260718_0012
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0013"
down_revision: str | None = "20260718_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("DELETE FROM knowledge_chunks")
    op.execute(
        """
        UPDATE knowledge_documents
        SET status = 'uploaded',
            error_summary = 'Reindexacao vetorial pendente',
            processed_at = NULL
        WHERE status IN ('ready', 'processing')
        """
    )
    op.drop_column("knowledge_chunks", "embedding")
    op.add_column(
        "knowledge_chunks",
        sa.Column("embedding", Vector(384), nullable=False),
    )
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.execute("DELETE FROM knowledge_chunks")
    op.execute(
        """
        UPDATE knowledge_documents
        SET status = 'uploaded',
            error_summary = 'Reindexacao de compatibilidade pendente',
            processed_at = NULL
        WHERE status IN ('ready', 'processing')
        """
    )
    op.drop_column("knowledge_chunks", "embedding")
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "embedding",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

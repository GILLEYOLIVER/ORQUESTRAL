"""Habilita extensões PostgreSQL fundamentais.

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16
"""

from alembic import op

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')


def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "citext"')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')

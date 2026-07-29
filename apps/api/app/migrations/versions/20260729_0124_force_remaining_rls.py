"""force remaining tenant RLS policies

Revision ID: 20260729_0124
Revises: 20260729_0123
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260729_0124"
down_revision: str | None = "20260729_0123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "customer_cdc_checkpoint_history",
    "customer_cdc_counters",
    "customer_cdc_retention_runs",
    "customer_cdc_subscriptions",
    "customer_change_events",
    "customer_privacy_request_events",
    "customer_privacy_requests",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')

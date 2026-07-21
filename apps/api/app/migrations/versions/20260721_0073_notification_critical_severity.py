"""Allow critical operational notifications.

Revision ID: 20260721_0073
Revises: 20260721_0072
Create Date: 2026-07-21 16:20:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_0073"
down_revision: str | None = "20260721_0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_notifications_severity", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_severity",
        "notifications",
        "severity IN ('info', 'success', 'warning', 'error', 'critical')",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM notifications WHERE severity = 'critical') THEN
                RAISE EXCEPTION
                    'cannot downgrade while critical notifications are stored';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint("ck_notifications_severity", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_severity",
        "notifications",
        "severity IN ('info', 'success', 'warning', 'error')",
    )

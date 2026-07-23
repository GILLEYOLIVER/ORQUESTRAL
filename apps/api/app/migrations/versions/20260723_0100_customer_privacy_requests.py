"""Add governed customer privacy requests.

Revision ID: 20260723_0100
Revises: 20260723_0099
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0100"
down_revision: str | None = "20260723_0099"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table_name: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (
                company_id = NULLIF(
                    current_setting('app.current_company_id', true),
                    ''
                )::uuid
            )
            WITH CHECK (
                company_id = NULLIF(
                    current_setting('app.current_company_id', true),
                    ''
                )::uuid
            )
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "customer_privacy_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("profile_reference_hash", sa.String(length=64), nullable=False),
        sa.Column("request_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("request_reference_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scope",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("legal_hold", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("legal_hold_reason", sa.String(length=24), nullable=True),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "verified_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "executed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "legal_hold_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_hold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.CheckConstraint(
            "request_type IN ('anonymization', 'deletion')",
            name="ck_customer_privacy_request_type",
        ),
        sa.CheckConstraint(
            """
            status IN (
                'received',
                'identity_verified',
                'approved',
                'rejected',
                'completed'
            )
            """,
            name="ck_customer_privacy_request_status",
        ),
        sa.CheckConstraint(
            """
            reason_code IN (
                'data_subject_request',
                'contract_ended',
                'duplicate_record',
                'legal_obligation'
            )
            """,
            name="ck_customer_privacy_reason",
        ),
        sa.CheckConstraint(
            """
            legal_hold_reason IS NULL OR legal_hold_reason IN (
                'contractual',
                'regulatory',
                'litigation',
                'fraud_prevention'
            )
            """,
            name="ck_customer_privacy_hold_reason",
        ),
        sa.CheckConstraint(
            "(legal_hold AND legal_hold_reason IS NOT NULL) OR NOT legal_hold",
            name="ck_customer_privacy_hold_consistency",
        ),
        sa.UniqueConstraint(
            "company_id",
            "request_reference_hash",
            name="uq_customer_privacy_request_reference",
        ),
    )
    op.create_index(
        "ix_customer_privacy_company_status_due",
        "customer_privacy_requests",
        ["company_id", "status", "due_at"],
    )
    op.create_table(
        "customer_privacy_request_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_privacy_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("previous_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_customer_privacy_events_request",
        "customer_privacy_request_events",
        ["company_id", "request_id", "occurred_at"],
    )
    _enable_rls("customer_privacy_requests")
    _enable_rls("customer_privacy_request_events")


def downgrade() -> None:
    for table_name in (
        "customer_privacy_request_events",
        "customer_privacy_requests",
    ):
        op.execute(
            sa.text(
                f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}"
            )
        )
    op.drop_index(
        "ix_customer_privacy_events_request",
        table_name="customer_privacy_request_events",
    )
    op.drop_table("customer_privacy_request_events")
    op.drop_index(
        "ix_customer_privacy_company_status_due",
        table_name="customer_privacy_requests",
    )
    op.drop_table("customer_privacy_requests")


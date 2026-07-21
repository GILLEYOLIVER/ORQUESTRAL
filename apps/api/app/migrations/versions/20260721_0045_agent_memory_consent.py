"""Add personal-memory ownership and consent revocation.

Revision ID: 20260721_0045
Revises: 20260721_0044
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0045"
down_revision: str | None = "20260721_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_memory_entries", sa.Column("subject_user_id", sa.Uuid()))
    op.add_column("agent_memory_entries", sa.Column("subject_membership_id", sa.Uuid()))
    op.add_column("agent_memory_entries", sa.Column("consent_fingerprint", sa.String(length=64)))
    op.execute(
        """
        UPDATE agent_memory_entries AS memory
        SET subject_user_id = memory.created_by_user_id,
            subject_membership_id = membership.id,
            expires_at = LEAST(memory.expires_at, now())
        FROM company_users AS membership
        WHERE memory.scope = 'user'
          AND membership.company_id = memory.company_id
          AND membership.user_id = memory.created_by_user_id
        """
    )
    op.drop_constraint("ck_agent_memory_user_consent", "agent_memory_entries", type_="check")
    op.drop_column("agent_memory_entries", "consent_reference")
    op.create_index(
        "ix_agent_memory_entries_subject_user_id",
        "agent_memory_entries",
        ["subject_user_id"],
    )
    op.create_index(
        "ix_agent_memory_entries_consent_fingerprint",
        "agent_memory_entries",
        ["consent_fingerprint"],
    )
    op.create_index(
        "ix_agent_memory_entries_subject_membership_id",
        "agent_memory_entries",
        ["subject_membership_id"],
    )
    op.create_foreign_key(
        "fk_agent_memory_subject_user",
        "agent_memory_entries",
        "users",
        ["subject_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_agent_memory_subject_membership",
        "agent_memory_entries",
        "company_users",
        ["subject_membership_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_agent_memory_user_subject",
        "agent_memory_entries",
        "scope <> 'user' OR (subject_user_id IS NOT NULL AND subject_membership_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_agent_memory_non_user_subject",
        "agent_memory_entries",
        "scope = 'user' OR (subject_user_id IS NULL AND subject_membership_id IS NULL AND consent_fingerprint IS NULL)",
    )
    op.create_table(
        "agent_memory_consent_revocations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("subject_membership_id", sa.Uuid(), nullable=False),
        sa.Column("consent_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subject_membership_id"], ["company_users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "agent_id",
            "subject_user_id",
            "consent_fingerprint",
            name="uq_agent_memory_consent_revocation",
        ),
    )
    for column in (
        "company_id",
        "agent_id",
        "subject_user_id",
        "subject_membership_id",
        "consent_fingerprint",
        "revoked_by_user_id",
        "revoked_at",
    ):
        op.create_index(
            f"ix_agent_memory_consent_revocations_{column}",
            "agent_memory_consent_revocations",
            [column],
        )
    op.drop_constraint("ck_agent_security_event_category", "agent_security_events", type_="check")
    op.create_check_constraint(
        "ck_agent_security_event_category",
        "agent_security_events",
        "category IN ('prompt_injection', 'data_egress', 'sensitive_data', 'memory_access')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_security_event_category", "agent_security_events", type_="check")
    op.create_check_constraint(
        "ck_agent_security_event_category",
        "agent_security_events",
        "category IN ('prompt_injection', 'data_egress', 'sensitive_data')",
    )
    op.drop_table("agent_memory_consent_revocations")
    op.drop_constraint("ck_agent_memory_non_user_subject", "agent_memory_entries", type_="check")
    op.drop_constraint("ck_agent_memory_user_subject", "agent_memory_entries", type_="check")
    op.drop_constraint(
        "fk_agent_memory_subject_membership", "agent_memory_entries", type_="foreignkey"
    )
    op.drop_constraint("fk_agent_memory_subject_user", "agent_memory_entries", type_="foreignkey")
    op.drop_index("ix_agent_memory_entries_consent_fingerprint", table_name="agent_memory_entries")
    op.drop_index("ix_agent_memory_entries_subject_user_id", table_name="agent_memory_entries")
    op.drop_index(
        "ix_agent_memory_entries_subject_membership_id", table_name="agent_memory_entries"
    )
    op.add_column("agent_memory_entries", sa.Column("consent_reference", sa.String(length=160)))
    op.execute(
        """
        UPDATE agent_memory_entries
        SET consent_reference = 'legacy-redacted'
        WHERE scope = 'user'
        """
    )
    op.drop_column("agent_memory_entries", "consent_fingerprint")
    op.drop_column("agent_memory_entries", "subject_membership_id")
    op.drop_column("agent_memory_entries", "subject_user_id")
    op.create_check_constraint(
        "ck_agent_memory_user_consent",
        "agent_memory_entries",
        "scope <> 'user' OR consent_reference IS NOT NULL",
    )

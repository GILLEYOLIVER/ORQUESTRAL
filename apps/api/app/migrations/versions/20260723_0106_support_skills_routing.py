"""support skills, capacity and deterministic routing

Revision ID: 20260723_0106
Revises: 20260723_0105
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0106"
down_revision: str | None = "20260723_0105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON "{table}"
        USING (
          company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid
        )
        WITH CHECK (
          company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid
        )
        """
    )


def upgrade() -> None:
    op.create_table(
        "support_skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "key",
            name="uq_support_skills_company_key",
        ),
    )
    op.create_index(
        "ix_support_skills_company_active",
        "support_skills",
        ["company_id", "is_active"],
    )
    op.create_index(
        "ix_support_skills_created_by_user_id",
        "support_skills",
        ["created_by_user_id"],
    )

    op.add_column(
        "support_tickets",
        sa.Column(
            "required_skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("support_skills.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "support_tickets",
        sa.Column("language_code", sa.String(12), nullable=True),
    )
    op.create_index(
        "ix_support_tickets_required_skill_id",
        "support_tickets",
        ["required_skill_id"],
    )

    op.create_table(
        "support_agent_capacities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "queue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("support_queues.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), server_default="offline", nullable=False),
        sa.Column(
            "max_active_tickets",
            sa.Integer(),
            server_default="5",
            nullable=False,
        ),
        sa.Column(
            "languages",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "accepted_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('offline', 'available', 'busy', 'away')",
            name="ck_support_agent_capacities_status",
        ),
        sa.CheckConstraint(
            "max_active_tickets >= 1 AND max_active_tickets <= 100",
            name="ck_support_agent_capacities_max_active",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "user_id",
            name="uq_support_agent_capacities_company_user",
        ),
    )
    op.create_index(
        "ix_support_agent_capacities_company_status",
        "support_agent_capacities",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_support_agent_capacities_user_id",
        "support_agent_capacities",
        ["user_id"],
    )
    op.create_index(
        "ix_support_agent_capacities_queue_id",
        "support_agent_capacities",
        ["queue_id"],
    )
    op.create_index(
        "ix_support_agent_capacities_updated_by_user_id",
        "support_agent_capacities",
        ["updated_by_user_id"],
    )

    op.create_table(
        "support_agent_skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("support_skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proficiency", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "proficiency >= 1 AND proficiency <= 5",
            name="ck_support_agent_skills_proficiency",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "user_id",
            "skill_id",
            name="uq_support_agent_skills_company_user_skill",
        ),
    )
    op.create_index(
        "ix_support_agent_skills_company_user",
        "support_agent_skills",
        ["company_id", "user_id"],
    )
    op.create_index(
        "ix_support_agent_skills_skill_id",
        "support_agent_skills",
        ["skill_id"],
    )

    op.create_table(
        "support_queue_skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "queue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("support_queues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("support_skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "queue_id",
            "skill_id",
            name="uq_support_queue_skills_company_queue_skill",
        ),
    )
    op.create_index(
        "ix_support_queue_skills_company_queue",
        "support_queue_skills",
        ["company_id", "queue_id"],
    )
    op.create_index(
        "ix_support_queue_skills_skill_id",
        "support_queue_skills",
        ["skill_id"],
    )

    op.drop_constraint(
        "ck_support_ticket_events_type",
        "support_ticket_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_support_ticket_events_type",
        "support_ticket_events",
        "event_type IN ('created', 'assigned', 'queue_changed', "
        "'priority_changed', 'status_changed', 'first_response', "
        "'sla_breached', 'satisfaction_received', 'routed')",
    )

    for table in (
        "support_skills",
        "support_agent_capacities",
        "support_agent_skills",
        "support_queue_skills",
    ):
        _rls(table)


def downgrade() -> None:
    op.drop_constraint(
        "ck_support_ticket_events_type",
        "support_ticket_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_support_ticket_events_type",
        "support_ticket_events",
        "event_type IN ('created', 'assigned', 'queue_changed', "
        "'priority_changed', 'status_changed', 'first_response', "
        "'sla_breached', 'satisfaction_received')",
    )
    op.drop_table("support_queue_skills")
    op.drop_table("support_agent_skills")
    op.drop_table("support_agent_capacities")
    op.drop_index(
        "ix_support_tickets_required_skill_id",
        table_name="support_tickets",
    )
    op.drop_column("support_tickets", "language_code")
    op.drop_column("support_tickets", "required_skill_id")
    op.drop_table("support_skills")

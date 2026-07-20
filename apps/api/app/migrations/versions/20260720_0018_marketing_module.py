"""Instala campanhas, audiencias e jornadas de marketing.

Revision ID: 20260720_0018
Revises: 20260720_0017
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0018"
down_revision: str | None = "20260720_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("marketing.view", "marketing", "view", "Visualizar marketing"),
    ("marketing.create", "marketing", "create", "Criar campanhas"),
    ("marketing.update", "marketing", "update", "Atualizar campanhas"),
    ("marketing.delete", "marketing", "delete", "Arquivar campanhas"),
    ("marketing.audience.manage", "marketing", "audience.manage", "Gerenciar publicos"),
    ("marketing.journeys.manage", "marketing", "journeys.manage", "Gerenciar jornadas"),
)


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    permission_table = sa.table(
        "permissions",
        sa.column("code", sa.String()),
        sa.column("module_code", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [
            {"code": code, "module_code": module, "action": action, "description": description}
            for code, module, action, description in PERMISSIONS
        ],
    )
    op.execute(
        sa.text("""
        INSERT INTO modules_catalog (code, name, description, version, category, is_core, status)
        VALUES ('marketing', 'Marketing', 'Campanhas e jornadas de marketing.', '1.0.0', 'Comercial', false, 'installed')
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description,
            version = EXCLUDED.version, category = EXCLUDED.category, status = 'installed', updated_at = now()
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id FROM roles
        JOIN permissions ON permissions.module_code = 'marketing'
        WHERE roles.is_system_role = true AND roles.name IN ('Proprietário', 'Proprietario')
        ON CONFLICT DO NOTHING
    """)
    )
    op.create_table(
        "marketing_campaigns",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective", sa.String(length=500), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("spent_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "channel IN ('email', 'whatsapp', 'sms', 'social', 'multi_channel')",
            name="ck_marketing_campaigns_channel",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'scheduled', 'active', 'paused', 'completed', 'cancelled')",
            name="ck_marketing_campaigns_status",
        ),
        sa.CheckConstraint(
            "budget_cents >= 0 AND spent_cents >= 0", name="ck_marketing_campaigns_money"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "created_by_user_id",
        "name",
        "channel",
        "status",
        "start_at",
        "end_at",
        "archived_at",
        "created_at",
    ):
        op.create_index(f"ix_marketing_campaigns_{column}", "marketing_campaigns", [column])
    op.create_index(
        "ix_marketing_campaigns_company_status", "marketing_campaigns", ["company_id", "status"]
    )
    op.create_table(
        "marketing_campaign_contacts",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="planned", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('planned', 'sent', 'delivered', 'engaged', 'converted', 'failed', 'unsubscribed')",
            name="ck_marketing_campaign_contacts_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["crm_contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id", "contact_id", name="uq_marketing_campaign_contacts_campaign_contact"
        ),
    )
    for column in ("company_id", "campaign_id", "contact_id", "status", "created_at"):
        op.create_index(
            f"ix_marketing_campaign_contacts_{column}", "marketing_campaign_contacts", [column]
        )
    op.create_index(
        "ix_marketing_campaign_contacts_campaign_status",
        "marketing_campaign_contacts",
        ["campaign_id", "status"],
    )
    op.create_table(
        "marketing_journeys",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(length=30), server_default="manual", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "trigger_type IN ('manual', 'contact_created', 'contact_tagged', 'scheduled')",
            name="ck_marketing_journeys_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'archived')",
            name="ck_marketing_journeys_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "created_by_user_id",
        "name",
        "trigger_type",
        "status",
        "archived_at",
        "created_at",
    ):
        op.create_index(f"ix_marketing_journeys_{column}", "marketing_journeys", [column])
    op.create_index(
        "ix_marketing_journeys_company_status", "marketing_journeys", ["company_id", "status"]
    )
    op.create_table(
        "marketing_journey_steps",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journey_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "configuration",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "action_type IN ('wait', 'email', 'whatsapp', 'task', 'webhook')",
            name="ck_marketing_journey_steps_action_type",
        ),
        sa.CheckConstraint("position >= 0", name="ck_marketing_journey_steps_position"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journey_id"], ["marketing_journeys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "journey_id", "position", name="uq_marketing_journey_steps_journey_position"
        ),
    )
    for column in ("company_id", "journey_id", "action_type"):
        op.create_index(f"ix_marketing_journey_steps_{column}", "marketing_journey_steps", [column])


def downgrade() -> None:
    op.drop_table("marketing_journey_steps")
    op.drop_table("marketing_journeys")
    op.drop_table("marketing_campaign_contacts")
    op.drop_table("marketing_campaigns")
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE module_code = 'marketing')"
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE module_code = 'marketing'"))
    op.execute(
        sa.text(
            "UPDATE modules_catalog SET status = 'planned', updated_at = now() WHERE code = 'marketing'"
        )
    )

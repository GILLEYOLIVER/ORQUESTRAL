"""Instala o modulo de suporte e seus chamados.

Revision ID: 20260720_0016
Revises: 20260719_0015
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0016"
down_revision: str | None = "20260719_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("support.tickets.view", "support", "tickets.view", "Visualizar chamados de suporte"),
    ("support.tickets.create", "support", "tickets.create", "Criar chamados de suporte"),
    ("support.tickets.update", "support", "tickets.update", "Atualizar chamados de suporte"),
    (
        "support.tickets.comment",
        "support",
        "tickets.comment",
        "Registrar interacoes em chamados",
    ),
)


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
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
        sa.text(
            """
            INSERT INTO modules_catalog
                (code, name, description, version, category, is_core, status)
            VALUES
                ('support', 'Suporte', 'Atendimento e suporte ao cliente.',
                 '1.0.0', 'Operacoes', false, 'installed')
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                version = EXCLUDED.version,
                category = EXCLUDED.category,
                status = 'installed',
                updated_at = now()
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT roles.id, permissions.id
              FROM roles
             JOIN permissions ON permissions.module_code = 'support'
             WHERE roles.is_system_role = true
               AND roles.name IN ('Proprietário', 'Proprietario')
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.create_table(
        "support_tickets",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="normal", nullable=False),
        sa.Column("channel", sa.String(length=20), server_default="web", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'waiting', 'resolved', 'closed')",
            name="ck_support_tickets_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_support_tickets_priority",
        ),
        sa.CheckConstraint(
            "channel IN ('web', 'email', 'phone', 'whatsapp', 'other')",
            name="ck_support_tickets_channel",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_contact_id"], ["crm_contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "requester_contact_id",
        "assignee_user_id",
        "created_by_user_id",
        "subject",
        "status",
        "priority",
        "channel",
        "due_at",
        "resolved_at",
        "created_at",
    ):
        op.create_index(f"ix_support_tickets_{column}", "support_tickets", [column])
    op.create_index(
        "ix_support_tickets_company_status_created",
        "support_tickets",
        ["company_id", "status", "created_at"],
    )

    op.create_table(
        "support_interactions",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("company_id", "ticket_id", "author_user_id", "created_at"):
        op.create_index(f"ix_support_interactions_{column}", "support_interactions", [column])
    op.create_index(
        "ix_support_interactions_company_ticket_created",
        "support_interactions",
        ["company_id", "ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("support_interactions")
    op.drop_table("support_tickets")
    op.execute(sa.text("UPDATE modules_catalog SET status = 'planned' WHERE code = 'support'"))
    for code, *_ in PERMISSIONS:
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))

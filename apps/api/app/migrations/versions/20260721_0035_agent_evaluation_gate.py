"""Add agent evaluation suites and publication gate.

Revision ID: 20260721_0035
Revises: 20260721_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0035"
down_revision: str | None = "20260721_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    op.add_column(
        "agent_data_policies",
        sa.Column(
            "require_evaluation_for_publish",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.create_table(
        "agent_evaluation_suites",
        _id(),
        _uuid("company_id"),
        _uuid("agent_id"),
        _uuid("agent_version_id"),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("minimum_score", sa.Integer(), server_default="100", nullable=False),
        _uuid("created_by_user_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("minimum_score BETWEEN 0 AND 100", name="ck_agent_eval_suite_score"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_version_id", name="uq_agent_evaluation_suite_version"),
    )
    for column in (
        "company_id",
        "agent_id",
        "agent_version_id",
        "created_by_user_id",
        "created_at",
    ):
        op.create_index(f"ix_agent_evaluation_suites_{column}", "agent_evaluation_suites", [column])
    op.create_table(
        "agent_evaluation_cases",
        _id(),
        _uuid("company_id"),
        _uuid("suite_id"),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("expected_blocked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "expected_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "forbidden_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suite_id"], ["agent_evaluation_suites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("suite_id", "name", name="uq_agent_eval_case_name"),
    )
    for column in ("company_id", "suite_id"):
        op.create_index(f"ix_agent_evaluation_cases_{column}", "agent_evaluation_cases", [column])
    op.create_table(
        "agent_evaluation_runs",
        _id(),
        _uuid("company_id"),
        _uuid("agent_id"),
        _uuid("agent_version_id"),
        _uuid("suite_id"),
        sa.Column("status", sa.String(length=16), server_default="running", nullable=False),
        sa.Column("total_cases", sa.Integer(), server_default="0", nullable=False),
        sa.Column("passed_cases", sa.Integer(), server_default="0", nullable=False),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        _uuid("created_by_user_id"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'passed', 'failed')", name="ck_agent_eval_run_status"
        ),
        sa.CheckConstraint(
            "total_cases >= 0 AND passed_cases >= 0 AND score BETWEEN 0 AND 100",
            name="ck_agent_eval_run_metrics",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suite_id"], ["agent_evaluation_suites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "agent_id",
        "agent_version_id",
        "suite_id",
        "status",
        "created_by_user_id",
        "started_at",
    ):
        op.create_index(f"ix_agent_evaluation_runs_{column}", "agent_evaluation_runs", [column])
    op.create_table(
        "agent_evaluation_results",
        _id(),
        _uuid("company_id"),
        _uuid("run_id"),
        _uuid("case_id"),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("actual_blocked", sa.Boolean(), nullable=False),
        sa.Column(
            "planned_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "failure_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["agent_evaluation_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "case_id", name="uq_agent_eval_result_case"),
    )
    for column in ("company_id", "run_id", "case_id", "passed"):
        op.create_index(
            f"ix_agent_evaluation_results_{column}", "agent_evaluation_results", [column]
        )


def downgrade() -> None:
    for column in ("passed", "case_id", "run_id", "company_id"):
        op.drop_index(
            f"ix_agent_evaluation_results_{column}", table_name="agent_evaluation_results"
        )
    op.drop_table("agent_evaluation_results")
    for column in reversed(
        (
            "company_id",
            "agent_id",
            "agent_version_id",
            "suite_id",
            "status",
            "created_by_user_id",
            "started_at",
        )
    ):
        op.drop_index(f"ix_agent_evaluation_runs_{column}", table_name="agent_evaluation_runs")
    op.drop_table("agent_evaluation_runs")
    for column in ("suite_id", "company_id"):
        op.drop_index(f"ix_agent_evaluation_cases_{column}", table_name="agent_evaluation_cases")
    op.drop_table("agent_evaluation_cases")
    for column in reversed(
        ("company_id", "agent_id", "agent_version_id", "created_by_user_id", "created_at")
    ):
        op.drop_index(f"ix_agent_evaluation_suites_{column}", table_name="agent_evaluation_suites")
    op.drop_table("agent_evaluation_suites")
    op.drop_column("agent_data_policies", "require_evaluation_for_publish")

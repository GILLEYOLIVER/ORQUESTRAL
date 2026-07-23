"""Enforce tenant RLS with runtime and read-only database roles.

Revision ID: 20260722_0089
Revises: 20260722_0088
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260722_0089"
down_revision: str | None = "20260722_0088"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "orkestral_tenant_runtime"
READ_ONLY_ROLE = "orkestral_tenant_read_only"
TENANT_POLICY = "orkestral_company_access"
TENANT_GUARD_POLICY = "orkestral_company_guard"
SYSTEM_POLICY = "orkestral_system_access"

PARENT_SCOPED_POLICIES = {
    "crm_contact_tags": (
        "EXISTS (SELECT 1 FROM public.crm_contacts parent "
        "WHERE parent.id = contact_id AND parent.company_id = "
        "NULLIF(current_setting('app.current_company_id', true), '')::uuid)"
    ),
    "role_permissions": (
        "EXISTS (SELECT 1 FROM public.roles parent "
        "WHERE parent.id = role_id AND parent.company_id = "
        "NULLIF(current_setting('app.current_company_id', true), '')::uuid)"
    ),
}


def _quote_table(table_name: str) -> str:
    bind = op.get_bind()
    preparer = bind.dialect.identifier_preparer
    return f"{preparer.quote('public')}.{preparer.quote(table_name)}"


def _company_scoped_tables() -> list[str]:
    inspector = sa.inspect(op.get_bind())
    return sorted(
        table_name
        for table_name in inspector.get_table_names(schema="public")
        if any(
            column["name"] == "company_id"
            for column in inspector.get_columns(table_name, schema="public")
        )
    )


def _create_role(role: str) -> None:
    role_sql = f"""
        DO $role$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                    NOINHERIT NOREPLICATION NOBYPASSRLS;
            END IF;
        END
        $role$;
        """  # noqa: S608 - role is selected from module constants only.
    op.execute(
        sa.text(role_sql)
    )
    op.execute(sa.text(f"GRANT {role} TO CURRENT_USER"))
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))


def _create_policy(table_name: str, expression: str, system_role: str) -> None:
    table = _quote_table(table_name)
    roles = f"{RUNTIME_ROLE}, {READ_ONLY_ROLE}"
    quoted_system_role = op.get_bind().dialect.identifier_preparer.quote(system_role)
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS {TENANT_POLICY} ON {table}"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS {TENANT_GUARD_POLICY} ON {table}"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS {SYSTEM_POLICY} ON {table}"))
    op.execute(
        sa.text(
            f"CREATE POLICY {TENANT_POLICY} ON {table} FOR ALL TO {roles} "
            f"USING ({expression}) WITH CHECK ({expression})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {SYSTEM_POLICY} ON {table} FOR ALL TO {quoted_system_role} "
            "USING (true) WITH CHECK (true)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {TENANT_GUARD_POLICY} ON {table} AS RESTRICTIVE "
            f"FOR ALL TO {roles} USING ({expression}) WITH CHECK ({expression})"
        )
    )


def upgrade() -> None:
    system_role = str(op.get_bind().scalar(sa.text("SELECT current_user")))
    _create_role(RUNTIME_ROLE)
    _create_role(READ_ONLY_ROLE)

    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            f"TO {RUNTIME_ROLE}"
        )
    )
    op.execute(
        sa.text(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {RUNTIME_ROLE}")
    )
    op.execute(sa.text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {READ_ONLY_ROLE}"))
    op.execute(
        sa.text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {RUNTIME_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {RUNTIME_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES "
            f"TO {READ_ONLY_ROLE}"
        )
    )
    for role in (RUNTIME_ROLE, READ_ONLY_ROLE):
        op.execute(
            sa.text(
                f"REVOKE ALL PRIVILEGES ON TABLE public.auth_attempts, "
                f"public.password_reset_tokens FROM {role}"
            )
        )

    tenant_expression = (
        "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
    )
    for table_name in _company_scoped_tables():
        _create_policy(table_name, tenant_expression, system_role)
    for table_name, expression in PARENT_SCOPED_POLICIES.items():
        _create_policy(table_name, expression, system_role)


def downgrade() -> None:
    for table_name in (*_company_scoped_tables(), *PARENT_SCOPED_POLICIES):
        table = _quote_table(table_name)
        op.execute(sa.text(f"DROP POLICY IF EXISTS {SYSTEM_POLICY} ON {table}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS {TENANT_GUARD_POLICY} ON {table}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS {TENANT_POLICY} ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    op.execute(
        sa.text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE "
            f"ON TABLES FROM {RUNTIME_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT, UPDATE "
            f"ON SEQUENCES FROM {RUNTIME_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES "  # noqa: S608
            f"FROM {READ_ONLY_ROLE}"
        )
    )
    for role in (RUNTIME_ROLE, READ_ONLY_ROLE):
        op.execute(sa.text(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role}"))
        op.execute(sa.text(f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {role}"))
        op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {role}"))
        op.execute(sa.text(f"REVOKE {role} FROM CURRENT_USER"))
        op.execute(sa.text(f"DROP ROLE IF EXISTS {role}"))

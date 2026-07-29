from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import get_settings

PUBLIC_TENANT_LOCATOR_TABLES = frozenset({"marketing_public_page_registry"})


@dataclass(frozen=True, slots=True)
class RLSFinding:
    table: str
    rls_enabled: bool
    rls_forced: bool


async def tenant_rls_findings(engine: AsyncEngine) -> list[RLSFinding]:
    query = text(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND EXISTS (
            SELECT 1
            FROM information_schema.columns AS column_info
            WHERE column_info.table_schema = 'public'
              AND column_info.table_name = c.relname
              AND column_info.column_name = 'company_id'
          )
        ORDER BY c.relname
        """
    )
    async with engine.connect() as connection:
        rows = (await connection.execute(query)).all()
    return [
        RLSFinding(table=str(row[0]), rls_enabled=bool(row[1]), rls_forced=bool(row[2]))
        for row in rows
        if str(row[0]) not in PUBLIC_TENANT_LOCATOR_TABLES
    ]


async def main_async() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url_for("migration"), pool_pre_ping=True)
    try:
        findings = await tenant_rls_findings(engine)
    finally:
        await engine.dispose()
    failures = [row for row in findings if not row.rls_enabled or not row.rls_forced]
    if failures:
        for row in failures:
            print(
                f"RLS inválido: {row.table} enabled={row.rls_enabled} forced={row.rls_forced}"
            )
        return 1
    print(f"RLS habilitado e forçado em {len(findings)} tabelas tenant.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()

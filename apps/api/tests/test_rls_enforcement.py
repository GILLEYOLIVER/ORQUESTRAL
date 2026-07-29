from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.scripts.check_tenant_rls import tenant_rls_findings


async def test_every_internal_tenant_table_has_forced_rls() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url_for("migration"), pool_pre_ping=True)
    try:
        findings = await tenant_rls_findings(engine)
    finally:
        await engine.dispose()
    assert findings
    assert all(row.rls_enabled and row.rls_forced for row in findings), [
        row for row in findings if not row.rls_enabled or not row.rls_forced
    ]


async def test_runtime_role_cannot_read_a_record_after_tenant_swap() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url_for("migration"), pool_pre_ping=True)
    async with engine.connect() as connection:
        source = (
            await connection.execute(
                text("SELECT id, company_id FROM roles ORDER BY created_at LIMIT 1")
            )
        ).first()
        assert source is not None, "Bootstrap deve criar ao menos um papel empresarial."
        role_id, company_id = source
        forged_company_id = uuid4()
        await connection.execute(text("SET LOCAL ROLE orkestral_tenant_runtime"))
        await connection.execute(
            text("SELECT set_config('app.current_company_id', :company_id, true)"),
            {"company_id": str(forged_company_id)},
        )
        leaked = await connection.scalar(
            text("SELECT id FROM roles WHERE id = :role_id"), {"role_id": role_id}
        )
        assert leaked is None
        await connection.execute(
            text("SELECT set_config('app.current_company_id', :company_id, true)"),
            {"company_id": str(company_id)},
        )
        visible = await connection.scalar(
            text("SELECT id FROM roles WHERE id = :role_id"), {"role_id": role_id}
        )
        assert visible == role_id
    await engine.dispose()

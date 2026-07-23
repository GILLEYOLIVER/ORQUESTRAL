from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session

TenantDatabaseAccessMode = Literal["standard", "read_only"]

_TENANT_COMPANY_INFO_KEY = "orkestral_company_id"
_TENANT_ROLE_INFO_KEY = "orkestral_database_role"
_TENANT_RUNTIME_ROLE = "orkestral_tenant_runtime"
_TENANT_READ_ONLY_ROLE = "orkestral_tenant_read_only"


class Base(DeclarativeBase):
    """Base dos futuros modelos SQLAlchemy."""


def _apply_tenant_database_settings(session: Session, connection: Connection) -> None:
    company_id = session.info.get(_TENANT_COMPANY_INFO_KEY)
    database_role = session.info.get(_TENANT_ROLE_INFO_KEY)
    if not company_id or database_role not in {
        _TENANT_RUNTIME_ROLE,
        _TENANT_READ_ONLY_ROLE,
    }:
        return
    if connection.dialect.name != "postgresql":
        return

    connection.execute(text(f"SET LOCAL ROLE {database_role}"))
    connection.execute(
        text("SELECT set_config('app.current_company_id', :company_id, true)"),
        {"company_id": str(company_id)},
    )


@event.listens_for(Session, "after_begin")
def _restore_tenant_database_settings(
    session: Session,
    _transaction: object,
    connection: Connection,
) -> None:
    """Reaplica RLS depois de commit/rollback abrir uma nova transacao."""

    _apply_tenant_database_settings(session, connection)


async def apply_tenant_database_context(
    session: AsyncSession,
    *,
    company_id: UUID,
    access_mode: TenantDatabaseAccessMode,
) -> None:
    """Ativa o papel de menor privilegio e o tenant da transacao atual."""

    database_role = (
        _TENANT_READ_ONLY_ROLE if access_mode == "read_only" else _TENANT_RUNTIME_ROLE
    )
    sync_session = session.sync_session
    sync_session.info[_TENANT_COMPANY_INFO_KEY] = str(company_id)
    sync_session.info[_TENANT_ROLE_INFO_KEY] = database_role

    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if session.in_transaction():
        await session.execute(text(f"SET LOCAL ROLE {database_role}"))
        await session.execute(
            text("SELECT set_config('app.current_company_id', :company_id, true)"),
            {"company_id": str(company_id)},
        )
        return

    # Inicia uma transacao; o listener after_begin aplica papel e tenant antes
    # de esta primeira consulta chegar ao PostgreSQL.
    await session.execute(text("SELECT 1"))


def create_database_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1_800,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

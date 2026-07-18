from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


@dataclass(frozen=True, slots=True)
class AuditFilters:
    action: str | None = None
    resource_type: str | None = None
    actor_user_id: UUID | None = None
    created_from: datetime | None = None
    created_until: datetime | None = None


class AuditRepository:
    def __init__(self, database: AsyncSession) -> None:
        self.database = database

    async def create(self, event: AuditEvent) -> AuditEvent:
        self.database.add(event)
        await self.database.flush()
        return event

    async def list_for_company(
        self,
        *,
        company_id: UUID,
        filters: AuditFilters,
        offset: int,
        limit: int,
    ) -> tuple[list[AuditEvent], int]:
        conditions = [AuditEvent.company_id == company_id]
        if filters.action:
            conditions.append(AuditEvent.action == filters.action)
        if filters.resource_type:
            conditions.append(AuditEvent.resource_type == filters.resource_type)
        if filters.actor_user_id:
            conditions.append(AuditEvent.actor_user_id == filters.actor_user_id)
        if filters.created_from:
            conditions.append(AuditEvent.created_at >= filters.created_from)
        if filters.created_until:
            conditions.append(AuditEvent.created_at <= filters.created_until)

        total = int(
            await self.database.scalar(select(func.count(AuditEvent.id)).where(*conditions)) or 0
        )
        events = list(
            await self.database.scalars(
                select(AuditEvent)
                .where(*conditions)
                .order_by(AuditEvent.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return events, total

    async def purge_before(self, *, company_id: UUID, before: datetime) -> int:
        ids = list(
            await self.database.scalars(
                select(AuditEvent.id).where(
                    AuditEvent.company_id == company_id,
                    AuditEvent.created_at < before,
                )
            )
        )
        if ids:
            await self.database.execute(delete(AuditEvent).where(AuditEvent.id.in_(ids)))
        return len(ids)

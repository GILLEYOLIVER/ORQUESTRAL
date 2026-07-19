from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redaction import redact_sensitive_data
from app.core.security import utc_now
from app.modules.audit.models import AuditEvent
from app.modules.audit.repository import AuditFilters, AuditRepository


class AuditRetentionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AuditEventInput:
    company_id: UUID | None
    actor_user_id: UUID | None
    actor_type: str
    action: str
    resource_type: str
    resource_id: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    request_id: str


class AuditService:
    def __init__(self, database: AsyncSession) -> None:
        self.database = database
        self.repository = AuditRepository(database)

    async def record(self, payload: AuditEventInput) -> AuditEvent:
        before_data = redact_sensitive_data(payload.before_data) if payload.before_data else None
        after_data = redact_sensitive_data(payload.after_data) if payload.after_data else None
        return await self.repository.create(
            AuditEvent(
                company_id=payload.company_id,
                actor_user_id=payload.actor_user_id,
                actor_type=payload.actor_type,
                action=payload.action[:120],
                resource_type=payload.resource_type[:120],
                resource_id=payload.resource_id[:120] if payload.resource_id else None,
                before_data=before_data,
                after_data=after_data,
                ip_address=payload.ip_address[:64] if payload.ip_address else None,
                user_agent=payload.user_agent[:512] if payload.user_agent else None,
                request_id=payload.request_id[:128],
            )
        )

    async def list_events(
        self,
        *,
        company_id: UUID,
        filters: AuditFilters,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditEvent], int]:
        return await self.repository.list_for_company(
            company_id=company_id,
            filters=filters,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def purge(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID,
        before: datetime,
        reason: str,
        retention_days: int,
        request_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> int:
        latest_allowed = utc_now() - timedelta(days=retention_days)
        if before > latest_allowed:
            raise AuditRetentionError(f"A retenção mínima configurada é de {retention_days} dias.")
        purged = await self.repository.purge_before(company_id=company_id, before=before)
        await self.record(
            AuditEventInput(
                company_id=company_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="security.audit.purge",
                resource_type="audit_events",
                resource_id=None,
                before_data={"before": before.isoformat()},
                after_data={"purged": purged, "reason": reason},
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            )
        )
        return purged

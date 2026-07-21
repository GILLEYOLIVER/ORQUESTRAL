from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.core.config import Settings
from app.core.resources import create_resources
from app.core.security import hash_password
from app.modules.authorization.service import (
    ensure_company_system_roles,
    record_authorization_audit,
)
from app.modules.companies.models import Company
from app.modules.events.models import OutboxEvent
from app.modules.events.repository import register_event_consumption
from app.modules.events.schemas import DomainEventEnvelope
from app.modules.events.service import dispatch_outbox_batch
from app.modules.users.models import CompanyUser, User


@dataclass(slots=True)
class CapturingTransport:
    events: list[DomainEventEnvelope] = field(default_factory=list)

    async def publish(self, event: DomainEventEnvelope) -> str:
        self.events.append(event)
        return f"captured-{event.event_id}"


async def _exercise(settings: Settings) -> None:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    company_id: UUID | None = None
    user_email = f"event-owner-{suffix}@example.com"
    try:
        async with resources.sessions() as database:
            company = Company(
                legal_name=f"Eventos {suffix} Ltda.",
                trade_name=f"Eventos {suffix}",
                document_number=f"EVT{suffix}",
                slug=f"eventos-{suffix}",
                status="active",
            )
            user = User(
                name="Proprietario de Eventos",
                email=user_email,
                password_hash=hash_password("Event-Outbox-2026!"),
                status="active",
            )
            database.add_all((company, user))
            await database.flush()
            company_id = company.id
            owner, _ = await ensure_company_system_roles(database, company.id)
            database.add(
                CompanyUser(
                    company_id=company.id,
                    user_id=user.id,
                    role_id=owner.id,
                    status="active",
                    is_owner=True,
                )
            )
            record_authorization_audit(
                database,
                company_id=company.id,
                actor_user_id=user.id,
                action="contact.created",
                target_type="crm_contact",
                target_id=uuid4(),
                details={"ignored_sensitive_business_detail": "not-copied"},
            )
            await database.commit()

        async with resources.sessions() as database:
            pending = await database.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.company_id == company_id,
                    OutboxEvent.event_type == "contact.created",
                )
            )
            assert pending is not None
            assert pending.status == "pending"
            assert "ignored_sensitive_business_detail" not in pending.payload
            assert pending.payload["target_type"] == "crm_contact"

            transport = CapturingTransport()
            result = await dispatch_outbox_batch(
                database, transport, worker_id="integration-test", limit=10
            )
            assert result.published == 1
            assert result.failed == 0
            assert len(transport.events) == 1

        async with resources.sessions() as database:
            published = await database.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.company_id == company_id,
                    OutboxEvent.event_type == "contact.created",
                )
            )
            assert published is not None
            assert published.status == "published"
            assert published.external_id == f"captured-{published.id}"

            first = await register_event_consumption(
                database,
                event_id=published.id,
                company_id=published.company_id,
                consumer_name="integration.crm-projection",
            )
            second = await register_event_consumption(
                database,
                event_id=published.id,
                company_id=published.company_id,
                consumer_name="integration.crm-projection",
            )
            await database.commit()
            assert first is True
            assert second is False
    finally:
        if company_id is not None:
            async with resources.sessions() as database:
                await database.execute(delete(Company).where(Company.id == company_id))
                await database.execute(delete(User).where(User.email == user_email))
                await database.commit()
        await resources.close()


@pytest.mark.integration
def test_authorized_action_is_published_once_from_the_transactional_outbox() -> None:
    asyncio.run(_exercise(Settings(app_env="testing")))

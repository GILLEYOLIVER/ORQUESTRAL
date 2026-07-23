from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import Settings
from app.core.resources import create_resources
from app.core.security import hash_password
from app.main import create_app
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.events.models import EventConsumption
from app.modules.events.operations_service import (
    EventConsumerRegistry,
    LedgerEventConsumer,
    process_delivery_batch,
)
from app.modules.events.schemas import DomainEventCreate, DomainEventEnvelope
from app.modules.events.service import dispatch_outbox_batch, enqueue_domain_event
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class EventIdentity:
    company_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


class CapturingTransport:
    def __init__(self) -> None:
        self.events: list[DomainEventEnvelope] = []

    async def publish(self, event: DomainEventEnvelope) -> str:
        self.events.append(event)
        return f"captured-{len(self.events)}"


async def _seed(settings: Settings) -> EventIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Events-Platform-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Event Platform {label} {suffix} Ltda.",
                    trade_name=f"Event Platform {label} {suffix}",
                    document_number=f"EVENT{label}{suffix}",
                    slug=f"event-platform-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Administrador Event {label}",
                    email=f"event-{label.lower()}-{suffix}@example.com",
                    password_hash=hash_password(password),
                    status="active",
                )
                for label in ("A", "B")
            ]
            database.add_all((*companies, *users))
            await database.flush()
            for company, user in zip(companies, users, strict=True):
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
            await database.commit()
            return EventIdentity(
                company_ids=(companies[0].id, companies[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: EventIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(delete(Company).where(Company.id.in_(identity.company_ids)))
            await database.execute(delete(User).where(User.email.in_(identity.emails)))
            await database.commit()
    finally:
        await resources.close()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _enqueue(settings: Settings, company_id: UUID, payload: dict[str, object]) -> UUID:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            event = enqueue_domain_event(
                database,
                DomainEventCreate(
                    event_type="contact.created",
                    event_version=1,
                    company_id=company_id,
                    classification="internal",
                    payload=payload,
                ),
            )
            await database.commit()
            return event.id
    finally:
        await resources.close()


async def _dispatch(settings: Settings, transport: CapturingTransport) -> dict[str, int]:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            result = await dispatch_outbox_batch(database, transport, worker_id="integration")
            return {
                "published": result.published,
                "dead_lettered": result.dead_lettered,
            }
    finally:
        await resources.close()


async def _consume(settings: Settings, *, registered: bool) -> dict[str, int]:
    resources = create_resources(settings)
    registry = EventConsumerRegistry()
    if registered:
        registry.register("ledger", LedgerEventConsumer())
    try:
        async with resources.sessions() as database:
            return await process_delivery_batch(
                database, registry=registry, worker_id="integration-consumer"
            )
    finally:
        await resources.close()


async def _consumption_count(settings: Settings, event_id: UUID) -> int:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            return len(
                list(
                    await database.scalars(
                        select(EventConsumption).where(EventConsumption.event_id == event_id)
                    )
                )
            )
    finally:
        await resources.close()


@pytest.mark.integration
def test_event_contract_delivery_replay_and_tenant_boundaries() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)
            contract = client.post(
                "/events/contracts",
                headers=headers_a,
                json={
                    "event_type": "contact.created",
                    "version": 1,
                    "classification": "internal",
                    "compatibility_mode": "backward",
                    "payload_schema": {
                        "type": "object",
                        "properties": {"record_id": {"type": "string"}},
                        "required": ["record_id"],
                        "additionalProperties": False,
                    },
                },
            )
            assert contract.status_code == 201
            contract_id = contract.json()["id"]
            assert (
                client.post(
                    f"/events/contracts/{contract_id}/publish", headers=headers_a
                ).status_code
                == 200
            )
            subscription = client.post(
                "/events/subscriptions",
                headers=headers_a,
                json={
                    "name": "Historico de contatos",
                    "consumer_name": "crm.contact-ledger",
                    "event_type": "contact.created",
                    "min_version": 1,
                    "delivery_mode": "ledger",
                    "max_attempts": 1,
                },
            )
            assert subscription.status_code == 201

            valid_event_id = asyncio.run(
                _enqueue(settings, identity.company_ids[0], {"record_id": str(uuid4())})
            )
            captured = CapturingTransport()
            dispatched = asyncio.run(_dispatch(settings, captured))
            assert dispatched["published"] >= 1
            consumed = asyncio.run(_consume(settings, registered=True))
            assert consumed["succeeded"] == 1
            assert asyncio.run(_consumption_count(settings, valid_event_id)) == 1
            assert asyncio.run(_consume(settings, registered=True))["claimed"] == 0

            failing_event_id = asyncio.run(
                _enqueue(settings, identity.company_ids[0], {"record_id": str(uuid4())})
            )
            asyncio.run(_dispatch(settings, captured))
            failed = asyncio.run(_consume(settings, registered=False))
            assert failed["dead_letter"] == 1
            deliveries = client.get("/events/deliveries?status=dead_letter", headers=headers_a)
            assert deliveries.status_code == 200
            delivery = next(
                item for item in deliveries.json() if item["event_id"] == str(failing_event_id)
            )
            assert (
                client.post(
                    f"/events/deliveries/{delivery['id']}/replay", headers=headers_b
                ).status_code
                == 404
            )
            replayed_delivery = client.post(
                f"/events/deliveries/{delivery['id']}/replay", headers=headers_a
            )
            assert replayed_delivery.status_code == 200
            assert replayed_delivery.json()["status"] == "pending"

            invalid_event_id = asyncio.run(
                _enqueue(settings, identity.company_ids[0], {"wrong": "field"})
            )
            invalid_dispatch = asyncio.run(_dispatch(settings, captured))
            assert invalid_dispatch["dead_lettered"] >= 1
            outbox = client.get("/events/outbox?status=dead_letter", headers=headers_a)
            assert outbox.status_code == 200
            invalid = next(item for item in outbox.json() if item["id"] == str(invalid_event_id))
            assert invalid["last_error_code"] == "event_contract_invalid_payload"
            assert (
                client.post(
                    f"/events/outbox/{invalid_event_id}/replay", headers=headers_b
                ).status_code
                == 404
            )
            replayed = client.post(f"/events/outbox/{invalid_event_id}/replay", headers=headers_a)
            assert replayed.status_code == 201
            assert replayed.json()["source_id"] == str(invalid_event_id)
    finally:
        asyncio.run(_remove(settings, identity))

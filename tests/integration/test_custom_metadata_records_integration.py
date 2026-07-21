from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.config import Settings
from app.core.resources import create_resources
from app.core.security import hash_password
from app.main import create_app
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.events.models import OutboxEvent
from app.modules.metadata.models import MetadataRecord, MetadataRecordRevision
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class RecordIdentity:
    company_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> RecordIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Custom-Record-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Custom Record {label} {suffix} Ltda.",
                    trade_name=f"Custom Record {label} {suffix}",
                    document_number=f"REC{label}{suffix}",
                    slug=f"record-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Administrador Record {label}",
                    email=f"record-{label.lower()}-{suffix}@example.com",
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
            return RecordIdentity(
                company_ids=(companies[0].id, companies[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: RecordIdentity) -> None:
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


async def _assert_erased(settings: Settings, company_id: UUID, record_id: UUID) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            records = int(
                await database.scalar(
                    select(func.count())
                    .select_from(MetadataRecord)
                    .where(MetadataRecord.id == record_id)
                )
                or 0
            )
            revisions = int(
                await database.scalar(
                    select(func.count())
                    .select_from(MetadataRecordRevision)
                    .where(MetadataRecordRevision.record_id == record_id)
                )
                or 0
            )
            events = list(
                await database.scalars(
                    select(OutboxEvent).where(OutboxEvent.company_id == company_id)
                )
            )
            assert records == 0
            assert revisions == 0
            assert all("Cliente Secreto" not in str(event.payload) for event in events)
    finally:
        await resources.close()


@pytest.mark.integration
def test_custom_records_are_validated_idempotent_isolated_and_erased() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)
            definition = client.post(
                "/metadata/entities",
                headers=headers_b,
                json={
                    "key": "customer_asset",
                    "label": "Ativo do cliente",
                    "plural_label": "Ativos do cliente",
                    "fields": [
                        {
                            "key": "name",
                            "label": "Nome",
                            "data_type": "text",
                            "required": True,
                            "unique_values": True,
                            "position": 0,
                        },
                        {
                            "key": "amount",
                            "label": "Valor",
                            "data_type": "decimal",
                            "position": 1,
                        },
                    ],
                },
            )
            assert definition.status_code == 201
            definition_id = definition.json()["id"]
            assert (
                client.post(
                    f"/metadata/entities/{definition_id}/validate", headers=headers_b
                ).status_code
                == 200
            )
            assert (
                client.post(
                    f"/metadata/entities/{definition_id}/publish", headers=headers_b
                ).status_code
                == 200
            )

            idempotency_key = str(uuid4())
            create_payload = {
                "idempotency_key": idempotency_key,
                "values": {"name": "Cliente Secreto", "amount": "19.90"},
            }
            created = client.post(
                f"/metadata/entities/{definition_id}/records",
                headers=headers_b,
                json=create_payload,
            )
            assert created.status_code == 201
            record_id = created.json()["id"]
            repeated = client.post(
                f"/metadata/entities/{definition_id}/records",
                headers=headers_b,
                json=create_payload,
            )
            assert repeated.status_code == 201
            assert repeated.json()["id"] == record_id

            assert (
                client.get(
                    f"/metadata/entities/{definition_id}/records/{record_id}", headers=headers_a
                ).status_code
                == 404
            )
            listed = client.get(f"/metadata/entities/{definition_id}/records", headers=headers_b)
            assert listed.status_code == 200 and listed.json()["total"] == 1
            updated = client.put(
                f"/metadata/entities/{definition_id}/records/{record_id}",
                headers=headers_b,
                json={"values": {"amount": "29.90"}, "expected_version": 1},
            )
            assert updated.status_code == 200
            assert updated.json()["record_version"] == 2
            stale = client.put(
                f"/metadata/entities/{definition_id}/records/{record_id}",
                headers=headers_b,
                json={"values": {"amount": "39.90"}, "expected_version": 1},
            )
            assert stale.status_code == 409
            deleted = client.delete(
                f"/metadata/entities/{definition_id}/records/{record_id}",
                headers=headers_b,
                params={"expected_version": 2},
            )
            assert deleted.status_code == 204
            assert (
                client.get(
                    f"/metadata/entities/{definition_id}/records/{record_id}", headers=headers_b
                ).status_code
                == 404
            )
        asyncio.run(_assert_erased(settings, identity.company_ids[1], UUID(record_id)))
    finally:
        asyncio.run(_remove(settings, identity))

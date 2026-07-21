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
from app.modules.authorization.policy_models import PolicyDecisionRecord
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.events.models import OutboxEvent
from app.modules.metadata.models import (
    MetadataEntityDefinition,
    MetadataEntityVersion,
    MetadataFieldDefinition,
    MetadataLayoutDefinition,
    MetadataValidationRule,
    MetadataViewDefinition,
)
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class MetadataIdentity:
    company_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> MetadataIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Metadata-Contract-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Metadata {label} {suffix} Ltda.",
                    trade_name=f"Metadata {label} {suffix}",
                    document_number=f"META{label}{suffix}",
                    slug=f"metadata-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Administrador Metadata {label}",
                    email=f"metadata-{label.lower()}-{suffix}@example.com",
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
            return MetadataIdentity(
                company_ids=(companies[0].id, companies[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: MetadataIdentity) -> None:
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


async def _assert_persistence(settings: Settings, company_id: UUID, definition_id: UUID) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            entity = await database.scalar(
                select(MetadataEntityDefinition).where(
                    MetadataEntityDefinition.company_id == company_id,
                    MetadataEntityDefinition.id == definition_id,
                )
            )
            assert entity is not None
            assert entity.current_version == 2
            assert entity.published_version == 2
            assert entity.status == "published"
            versions = int(
                await database.scalar(
                    select(func.count())
                    .select_from(MetadataEntityVersion)
                    .where(
                        MetadataEntityVersion.company_id == company_id,
                        MetadataEntityVersion.definition_id == definition_id,
                    )
                )
                or 0
            )
            fields = int(
                await database.scalar(
                    select(func.count())
                    .select_from(MetadataFieldDefinition)
                    .where(MetadataFieldDefinition.company_id == company_id)
                )
                or 0
            )
            decisions = int(
                await database.scalar(
                    select(func.count())
                    .select_from(PolicyDecisionRecord)
                    .where(
                        PolicyDecisionRecord.company_id == company_id,
                        PolicyDecisionRecord.resource_type == "metadata_entity_definition",
                    )
                )
                or 0
            )
            events = int(
                await database.scalar(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(
                        OutboxEvent.company_id == company_id,
                        OutboxEvent.event_type == "metadata.definition.published",
                    )
                )
                or 0
            )
            layouts = int(
                await database.scalar(
                    select(func.count())
                    .select_from(MetadataLayoutDefinition)
                    .where(MetadataLayoutDefinition.company_id == company_id)
                )
                or 0
            )
            views = int(
                await database.scalar(
                    select(func.count())
                    .select_from(MetadataViewDefinition)
                    .where(MetadataViewDefinition.company_id == company_id)
                )
                or 0
            )
            rules = int(
                await database.scalar(
                    select(func.count())
                    .select_from(MetadataValidationRule)
                    .where(MetadataValidationRule.company_id == company_id)
                )
                or 0
            )
            assert versions == 2
            assert fields == 4
            assert decisions >= 7
            assert events == 2
            assert layouts == 2
            assert views == 2
            assert rules == 2
    finally:
        await resources.close()


@pytest.mark.integration
def test_metadata_lifecycle_is_versioned_audited_and_tenant_isolated() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)
            payload = {
                "key": "service_contract",
                "label": "Contrato de servico",
                "plural_label": "Contratos de servico",
                "fields": [
                    {"key": "name", "label": "Nome", "data_type": "text", "position": 0},
                    {"key": "amount", "label": "Valor", "data_type": "decimal", "position": 1},
                ],
            }
            created = client.post("/metadata/entities", headers=headers_b, json=payload)
            assert created.status_code == 201
            definition_id = created.json()["id"]

            assert (
                client.get(f"/metadata/entities/{definition_id}", headers=headers_a).status_code
                == 404
            )
            assert (
                client.get(f"/metadata/entities/{definition_id}", headers=headers_b).status_code
                == 200
            )
            assert (
                client.get(
                    f"/metadata/entities/{definition_id}/design", headers=headers_a
                ).status_code
                == 404
            )
            design = {
                "layouts": [
                    {
                        "key": "default_layout",
                        "label": "Formulario comercial",
                        "is_default": True,
                        "sections": [
                            {
                                "key": "main_section",
                                "label": "Dados principais",
                                "fields": ["name", "amount"],
                                "columns": 2,
                            }
                        ],
                    }
                ],
                "views": [
                    {
                        "key": "default_view",
                        "label": "Lista comercial",
                        "columns": ["name", "amount"],
                        "filters": [],
                        "sorting": [{"field_key": "name", "direction": "asc"}],
                        "is_default": True,
                    }
                ],
                "validation_rules": [
                    {
                        "key": "minimum_amount",
                        "label": "Valor minimo",
                        "field_key": "amount",
                        "operator": "greater_than",
                        "comparison_value": "10",
                        "message": "O valor precisa ser maior que 10.",
                        "active": True,
                    }
                ],
            }
            configured = client.put(
                f"/metadata/entities/{definition_id}/design",
                headers=headers_b,
                json=design,
            )
            assert configured.status_code == 200
            assert configured.json()["validation_rules"][0]["key"] == "minimum_amount"

            validated = client.post(
                f"/metadata/entities/{definition_id}/validate", headers=headers_b
            )
            assert validated.status_code == 200
            assert validated.json()["valid"] is True
            published = client.post(
                f"/metadata/entities/{definition_id}/publish", headers=headers_b
            )
            assert published.status_code == 200
            assert published.json()["published_version"] == 1
            rejected_record = client.post(
                f"/metadata/entities/{definition_id}/records",
                headers=headers_b,
                json={"values": {"name": "Invalido", "amount": "5.00"}},
            )
            assert rejected_record.status_code == 422
            assert rejected_record.json()["detail"] == "O valor precisa ser maior que 10."

            draft = client.post(f"/metadata/entities/{definition_id}/versions", headers=headers_b)
            assert draft.status_code == 201
            assert draft.json()["version"]["version"] == 2
            copied_design = client.get(
                f"/metadata/entities/{definition_id}/design", headers=headers_b
            )
            assert copied_design.status_code == 200
            assert copied_design.json()["validation_rules"][0]["key"] == "minimum_amount"
            updated = client.put(
                f"/metadata/entities/{definition_id}/draft",
                headers=headers_b,
                json={
                    "label": "Contrato empresarial",
                    "fields": payload["fields"],
                },
            )
            assert updated.status_code == 200
            assert updated.json()["label"] == "Contrato empresarial"
            assert (
                client.post(
                    f"/metadata/entities/{definition_id}/validate", headers=headers_b
                ).status_code
                == 200
            )
            republished = client.post(
                f"/metadata/entities/{definition_id}/publish", headers=headers_b
            )
            assert republished.status_code == 200
            assert republished.json()["published_version"] == 2

            listed_a = client.get("/metadata/entities", headers=headers_a)
            listed_b = client.get("/metadata/entities", headers=headers_b)
            assert listed_a.status_code == 200 and listed_a.json() == []
            assert listed_b.status_code == 200 and len(listed_b.json()) == 1

        asyncio.run(_assert_persistence(settings, identity.company_ids[1], UUID(definition_id)))
    finally:
        asyncio.run(_remove(settings, identity))

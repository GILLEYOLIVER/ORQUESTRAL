from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import Settings
from app.core.resources import create_resources
from app.core.security import hash_password
from app.main import create_app
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class CRMIdentity:
    company_a_id: UUID
    company_b_id: UUID
    user_a_email: str
    user_b_email: str
    password: str


async def seed_crm_identities(settings: Settings) -> CRMIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "CRM-Seguro-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            company_a = Company(
                legal_name=f"CRM Ativo {suffix} Ltda.",
                trade_name=f"CRM Ativo {suffix}",
                document_number=f"CRMA{suffix}",
                slug=f"crm-ativo-{suffix}",
                status="active",
            )
            company_b = Company(
                legal_name=f"CRM Inativo {suffix} Ltda.",
                trade_name=f"CRM Inativo {suffix}",
                document_number=f"CRMI{suffix}",
                slug=f"crm-inativo-{suffix}",
                status="active",
            )
            user_a = User(
                name="Responsável CRM A",
                email=f"crm-a-{suffix}@example.com",
                password_hash=hash_password(password),
                status="active",
            )
            user_b = User(
                name="Responsável CRM B",
                email=f"crm-b-{suffix}@example.com",
                password_hash=hash_password(password),
                status="active",
            )
            database.add_all((company_a, company_b, user_a, user_b))
            await database.flush()
            owner_a, _ = await ensure_company_system_roles(database, company_a.id)
            owner_b, _ = await ensure_company_system_roles(database, company_b.id)
            database.add_all(
                (
                    CompanyUser(
                        company_id=company_a.id,
                        user_id=user_a.id,
                        role_id=owner_a.id,
                        status="active",
                        is_owner=True,
                    ),
                    CompanyUser(
                        company_id=company_b.id,
                        user_id=user_b.id,
                        role_id=owner_b.id,
                        status="active",
                        is_owner=True,
                    ),
                )
            )
            await database.commit()
            return CRMIdentity(
                company_a_id=company_a.id,
                company_b_id=company_b.id,
                user_a_email=user_a.email,
                user_b_email=user_b.email,
                password=password,
            )
    finally:
        await resources.close()


async def remove_crm_identities(settings: Settings, identity: CRMIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(
                delete(Company).where(
                    Company.id.in_((identity.company_a_id, identity.company_b_id))
                )
            )
            await database.execute(
                delete(User).where(User.email.in_((identity.user_a_email, identity.user_b_email)))
            )
            await database.commit()
    finally:
        await resources.close()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_module_activation_crm_crud_and_tenant_isolation() -> None:
    settings = Settings(app_env="testing", development_expose_tokens=True)
    identity = asyncio.run(seed_crm_identities(settings))
    app = create_app(settings)

    try:
        with TestClient(app) as client:
            headers_a = _login(client, identity.user_a_email, identity.password)
            modules = client.get("/modules", headers=headers_a)
            assert modules.status_code == 200
            crm = next(module for module in modules.json() if module["code"] == "crm")
            assert crm["installed"] is True
            assert crm["company_status"] == "inactive"
            assert client.get("/crm/contacts", headers=headers_a).status_code == 403

            activation = client.patch(
                "/modules/crm",
                headers=headers_a,
                json={"status": "active", "configuration": {}},
            )
            assert activation.status_code == 200
            assert activation.json()["company_status"] == "active"

            tag = client.post("/crm/tags", headers=headers_a, json={"name": "Prioritário"})
            assert tag.status_code == 201
            tag_id = tag.json()["id"]
            contact = client.post(
                "/crm/contacts",
                headers=headers_a,
                json={
                    "name": "Contato modular",
                    "email": "modular@example.com",
                    "phone": "+55 11 99999-0000",
                    "company_name": "Empresa Modular",
                    "job_title": "Diretoria",
                    "source": "indicação",
                    "status": "lead",
                    "tag_ids": [tag_id],
                },
            )
            assert contact.status_code == 201
            contact_id = contact.json()["id"]
            assert contact.json()["tags"][0]["name"] == "Prioritário"
            customer_360 = client.get(
                f"/crm/contacts/{contact_id}/customer-360",
                headers=headers_a,
            )
            assert customer_360.status_code == 200, customer_360.text
            profile_id = customer_360.json()["profile_id"]
            assert customer_360.json()["quality_score"] >= 80
            assert {item["identity_type"] for item in customer_360.json()["identities"]} == {
                "email",
                "phone",
            }
            assert all(
                item["display_hint"] not in {"modular@example.com", "+55 11 99999-0000"}
                for item in customer_360.json()["identities"]
            )
            consent = client.post(
                f"/crm/contacts/{contact_id}/consents",
                headers=headers_a,
                json={
                    "purpose": "service",
                    "channel": "whatsapp",
                    "status": "granted",
                    "lawful_basis": "consentimento",
                    "evidence_reference": "FORM-CRM-001",
                },
            )
            assert consent.status_code == 201, consent.text
            assert consent.json()["status"] == "granted"
            duplicate = client.post(
                "/crm/contacts",
                headers=headers_a,
                json={
                    "name": "Contato modular duplicado",
                    "email": "MODULAR@example.com",
                    "status": "prospect",
                },
            )
            assert duplicate.status_code == 201
            duplicate_360 = client.get(
                f"/crm/contacts/{duplicate.json()['id']}/customer-360",
                headers=headers_a,
            )
            assert duplicate_360.status_code == 200
            assert duplicate_360.json()["profile_id"] == profile_id
            assert len(duplicate_360.json()["linked_contact_ids"]) == 2

            filtered = client.get(
                "/crm/contacts",
                headers=headers_a,
                params={
                    "search": "modular",
                    "status": "lead",
                    "tag_id": tag_id,
                    "sort_by": "name",
                    "sort_order": "asc",
                    "page": 1,
                    "page_size": 1,
                },
            )
            assert filtered.status_code == 200
            assert filtered.json()["total"] == 1
            assert filtered.json()["pages"] == 1

            updated = client.patch(
                f"/crm/contacts/{contact_id}",
                headers=headers_a,
                json={"status": "customer", "job_title": "Cliente"},
            )
            assert updated.status_code == 200
            assert updated.json()["status"] == "customer"

            headers_b = _login(client, identity.user_b_email, identity.password)
            assert client.get("/crm/contacts", headers=headers_b).status_code == 403
            assert (
                client.patch(
                    "/modules/crm", headers=headers_b, json={"status": "active"}
                ).status_code
                == 200
            )
            assert client.get(f"/crm/contacts/{contact_id}", headers=headers_b).status_code == 404
            assert (
                client.get(
                    f"/crm/contacts/{contact_id}/customer-360",
                    headers=headers_b,
                ).status_code
                == 404
            )

            deleted = client.delete(f"/crm/contacts/{contact_id}", headers=headers_a)
            assert deleted.status_code == 204
            assert client.get(f"/crm/contacts/{contact_id}", headers=headers_a).status_code == 404
            assert (
                client.delete(
                    f"/crm/contacts/{duplicate.json()['id']}",
                    headers=headers_a,
                ).status_code
                == 204
            )
            assert client.get("/crm/contacts", headers=headers_a).json()["total"] == 0

            audit = client.get("/authorization/audit-events", headers=headers_a)
            actions = {event["action"] for event in audit.json()}
            assert {
                "module.activated",
                "crm.contact.created",
                "crm.contact.updated",
                "crm.contact.deleted",
                "crm.customer_consent.recorded",
            } <= actions
    finally:
        asyncio.run(remove_crm_identities(settings, identity))

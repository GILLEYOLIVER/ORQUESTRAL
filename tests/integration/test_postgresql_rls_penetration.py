from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings
from app.core.database import Base, apply_tenant_database_context
from app.core.resources import create_resources
from app.core.security import hash_password
from app.main import create_app
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.crm.models import CRMContact
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class SecurityProbeIdentity:
    company_ids: tuple[UUID, UUID]
    contact_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> SecurityProbeIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Synthetic-RLS-Probe-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Sonda RLS {label} {suffix} Ltda.",
                    trade_name=f"Sonda RLS {label} {suffix}",
                    document_number=f"RLS{label}{suffix}",
                    slug=f"rls-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Operador RLS {label}",
                    email=f"rls-{label.lower()}-{suffix}@example.com",
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
            contacts = [
                CRMContact(company_id=company.id, name=f"Contato protegido {label}")
                for company, label in zip(companies, ("A", "B"), strict=True)
            ]
            database.add_all(contacts)
            await database.commit()
            return SecurityProbeIdentity(
                company_ids=(companies[0].id, companies[1].id),
                contact_ids=(contacts[0].id, contacts[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: SecurityProbeIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(delete(Company).where(Company.id.in_(identity.company_ids)))
            await database.execute(delete(User).where(User.email.in_(identity.emails)))
            await database.commit()
    finally:
        await resources.close()


async def _assert_database_rls(settings: Settings, identity: SecurityProbeIdentity) -> None:
    resources = create_resources(settings)
    try:
        expected_tables = {
            table.name for table in Base.metadata.tables.values() if "company_id" in table.c
        } | {"crm_contact_tags", "role_permissions"}
        async with resources.sessions() as database:
            protected_tables = set(
                await database.scalars(
                    text(
                        """
                        SELECT c.relname
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                          AND c.relrowsecurity
                          AND c.relforcerowsecurity
                        """
                    )
                )
            )
            assert expected_tables <= protected_tables

        async with resources.sessions() as database:
            await apply_tenant_database_context(
                database,
                company_id=identity.company_ids[0],
                access_mode="standard",
            )
            assert await database.get(CRMContact, identity.contact_ids[0]) is not None
            assert await database.get(CRMContact, identity.contact_ids[1]) is None

            database.add(
                CRMContact(
                    company_id=identity.company_ids[1],
                    name="Tentativa de escrita cruzada",
                )
            )
            with pytest.raises(DBAPIError):
                await database.flush()
            await database.rollback()
            assert await database.get(CRMContact, identity.contact_ids[0]) is not None

        async with resources.sessions() as database:
            await apply_tenant_database_context(
                database,
                company_id=identity.company_ids[0],
                access_mode="read_only",
            )
            own_contact = await database.get(CRMContact, identity.contact_ids[0])
            assert own_contact is not None
            own_contact.name = "Escrita proibida"
            with pytest.raises(DBAPIError):
                await database.flush()
            await database.rollback()
    finally:
        await resources.close()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_rls_blocks_cross_tenant_sql_and_read_only_writes() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        asyncio.run(_assert_database_rls(settings, identity))
    finally:
        asyncio.run(_remove(settings, identity))


@pytest.mark.integration
def test_api_rejects_tenant_forgery_mass_assignment_and_sql_injection() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            activate = client.patch("/modules/crm", headers=headers_a, json={"status": "active"})
            assert activate.status_code == 200

            forged_headers = {
                **headers_a,
                "X-Company-ID": str(identity.company_ids[1]),
            }
            cross_tenant = client.get(
                f"/crm/contacts/{identity.contact_ids[1]}",
                headers=forged_headers,
            )
            assert cross_tenant.status_code == 404

            mass_assignment = client.post(
                "/crm/contacts",
                headers=headers_a,
                json={
                    "name": "Tentativa de troca de empresa",
                    "company_id": str(identity.company_ids[1]),
                },
            )
            assert mass_assignment.status_code == 422

            injection = client.get(
                "/crm/contacts",
                headers=headers_a,
                params={"search": "%' OR 1=1; DROP TABLE companies; --"},
            )
            assert injection.status_code == 200
            returned_ids = {item["id"] for item in injection.json()["items"]}
            assert str(identity.contact_ids[1]) not in returned_ids

            profile = client.get("/auth/me", headers=headers_a)
            assert profile.status_code == 200
            serialized = profile.text.lower()
            for forbidden in (
                "password_hash",
                "refresh_token",
                "token_hash",
                "client_secret",
                "encrypted_credentials",
            ):
                assert forbidden not in serialized
    finally:
        asyncio.run(_remove(settings, identity))

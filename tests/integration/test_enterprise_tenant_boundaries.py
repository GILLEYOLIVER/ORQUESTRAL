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
class TenantBoundaryIdentity:
    company_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> TenantBoundaryIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Tenant-Contract-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Contrato Tenant {label} {suffix} Ltda.",
                    trade_name=f"Tenant {label} {suffix}",
                    document_number=f"TEN{label}{suffix}",
                    slug=f"tenant-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Proprietario {label}",
                    email=f"tenant-{label.lower()}-{suffix}@example.com",
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
            return TenantBoundaryIdentity(
                company_ids=(companies[0].id, companies[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: TenantBoundaryIdentity) -> None:
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


def _activate_modules(client: TestClient, headers: dict[str, str]) -> None:
    for module_code in ("crm", "marketing", "projects"):
        response = client.patch(
            f"/modules/{module_code}", headers=headers, json={"status": "active"}
        )
        assert response.status_code == 200


@pytest.mark.integration
def test_expanded_modules_hide_records_from_other_tenants() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)
            _activate_modules(client, headers_a)
            _activate_modules(client, headers_b)

            pipeline = client.post(
                "/crm/pipelines",
                headers=headers_b,
                json={
                    "name": "Pipeline Empresa B",
                    "stages": [
                        {"name": "Entrada", "position": 0, "probability": 10},
                        {"name": "Fechamento", "position": 1, "probability": 90},
                    ],
                },
            )
            assert pipeline.status_code == 201
            pipeline_data = pipeline.json()
            opportunity = client.post(
                "/crm/opportunities",
                headers=headers_b,
                json={
                    "title": "Negocio exclusivo B",
                    "pipeline_id": pipeline_data["id"],
                    "stage_id": pipeline_data["stages"][0]["id"],
                },
            )
            assert opportunity.status_code == 201

            campaign = client.post(
                "/marketing/campaigns",
                headers=headers_b,
                json={"name": "Campanha exclusiva B", "channel": "email"},
            )
            assert campaign.status_code == 201

            project = client.post(
                "/projects",
                headers=headers_b,
                json={"name": "Projeto exclusivo B"},
            )
            assert project.status_code == 201

            agent = client.post(
                "/agents",
                headers=headers_b,
                json={
                    "name": "Agente exclusivo B",
                    "instructions": "Atue somente nos dados autorizados da Empresa B.",
                },
            )
            assert agent.status_code == 201

            protected_records = (
                (f"/crm/opportunities/{opportunity.json()['id']}", "crm"),
                (f"/marketing/campaigns/{campaign.json()['id']}", "marketing"),
                (f"/projects/{project.json()['id']}", "projects"),
                (f"/agents/{agent.json()['id']}", "agents"),
            )
            for path, domain in protected_records:
                assert client.get(path, headers=headers_a).status_code == 404, domain
                assert client.delete(path, headers=headers_a).status_code == 404, domain
                assert client.get(path, headers=headers_b).status_code == 200, domain
    finally:
        asyncio.run(_remove(settings, identity))

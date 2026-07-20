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
class SupportIdentity:
    company_a_id: UUID
    company_b_id: UUID
    email_a: str
    email_b: str
    password: str


async def _seed(settings: Settings) -> SupportIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Support-Seguro-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Suporte {label} {suffix} Ltda.",
                    trade_name=f"Suporte {label} {suffix}",
                    document_number=f"SUP{label}{suffix}",
                    slug=f"suporte-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Atendente {label}",
                    email=f"suporte-{label.lower()}-{suffix}@example.com",
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
            return SupportIdentity(
                company_a_id=companies[0].id,
                company_b_id=companies[1].id,
                email_a=users[0].email,
                email_b=users[1].email,
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: SupportIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(
                delete(Company).where(
                    Company.id.in_((identity.company_a_id, identity.company_b_id))
                )
            )
            await database.execute(
                delete(User).where(User.email.in_((identity.email_a, identity.email_b)))
            )
            await database.commit()
    finally:
        await resources.close()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_support_lifecycle_audit_and_tenant_isolation() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            headers_a = _login(client, identity.email_a, identity.password)
            modules = client.get("/modules", headers=headers_a)
            support = next(item for item in modules.json() if item["code"] == "support")
            assert support["installed"] is True
            assert client.get("/support/tickets", headers=headers_a).status_code == 403
            assert (
                client.patch(
                    "/modules/support", headers=headers_a, json={"status": "active"}
                ).status_code
                == 200
            )

            created = client.post(
                "/support/tickets",
                headers=headers_a,
                json={
                    "subject": "Falha no acesso",
                    "description": "Cliente nao consegue acessar o painel.",
                    "priority": "urgent",
                    "channel": "whatsapp",
                },
            )
            assert created.status_code == 201
            ticket_id = created.json()["id"]
            assert created.json()["status"] == "open"

            interaction = client.post(
                f"/support/tickets/{ticket_id}/interactions",
                headers=headers_a,
                json={"message": "Acesso do cliente validado.", "is_internal": True},
            )
            assert interaction.status_code == 201
            assert (
                client.get(f"/support/tickets/{ticket_id}/interactions", headers=headers_a).json()[
                    0
                ]["message"]
                == "Acesso do cliente validado."
            )

            resolved = client.patch(
                f"/support/tickets/{ticket_id}",
                headers=headers_a,
                json={"status": "resolved"},
            )
            assert resolved.status_code == 200
            assert resolved.json()["resolved_at"] is not None

            headers_b = _login(client, identity.email_b, identity.password)
            client.patch("/modules/support", headers=headers_b, json={"status": "active"})
            assert client.get(f"/support/tickets/{ticket_id}", headers=headers_b).status_code == 404
            assert (
                client.get(
                    f"/support/tickets/{ticket_id}/interactions", headers=headers_b
                ).status_code
                == 404
            )

            actions = {
                event["action"]
                for event in client.get("/authorization/audit-events", headers=headers_a).json()
            }
            assert {
                "support.ticket.created",
                "support.ticket.updated",
                "support.interaction.created",
            } <= actions
    finally:
        asyncio.run(_remove(settings, identity))

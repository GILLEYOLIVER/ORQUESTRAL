from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import Settings
from app.core.resources import create_resources
from app.core.security import hash_password, utc_now
from app.main import create_app
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.billing.models import Plan, Subscription
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class BillingIdentity:
    company_id: UUID
    user_id: UUID
    plan_id: UUID
    email: str
    password: str


async def seed_billing_identity(settings: Settings) -> BillingIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Billing-Seguro-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            company = Company(
                legal_name=f"Empresa Limites {suffix} Ltda.",
                trade_name=f"Empresa Limites {suffix}",
                document_number=f"BIL{suffix}",
                slug=f"limites-{suffix}",
                status="active",
            )
            user = User(
                name="Responsável pelos limites",
                email=f"billing-{suffix}@example.com",
                password_hash=hash_password(password),
                status="active",
            )
            plan = Plan(
                name=f"Plano teste de limite {suffix}",
                description="Plano efêmero do teste automatizado.",
                price=Decimal("0.00"),
                billing_cycle="monthly",
                limits={"agents": 1},
                status="active",
            )
            database.add_all((company, user, plan))
            await database.flush()
            owner_role, _ = await ensure_company_system_roles(database, company.id)
            now = utc_now()
            database.add_all(
                (
                    CompanyUser(
                        company_id=company.id,
                        user_id=user.id,
                        role_id=owner_role.id,
                        status="active",
                        is_owner=True,
                    ),
                    Subscription(
                        company_id=company.id,
                        plan_id=plan.id,
                        status="active",
                        started_at=now,
                        current_period_start=now,
                        current_period_end=now + timedelta(days=30),
                    ),
                )
            )
            await database.commit()
            return BillingIdentity(
                company_id=company.id,
                user_id=user.id,
                plan_id=plan.id,
                email=user.email,
                password=password,
            )
    finally:
        await resources.close()


async def remove_billing_identity(settings: Settings, identity: BillingIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(delete(Company).where(Company.id == identity.company_id))
            await database.execute(delete(User).where(User.id == identity.user_id))
            await database.execute(delete(Plan).where(Plan.id == identity.plan_id))
            await database.commit()
    finally:
        await resources.close()


@pytest.mark.integration
def test_agent_creation_is_blocked_after_plan_limit() -> None:
    settings = Settings(app_env="testing", billing_enforcement_enabled=True)
    identity = asyncio.run(seed_billing_identity(settings))
    payload = {
        "name": "Agente permitido",
        "instructions": "Atenda solicitações empresariais de forma segura.",
        "provider": "local",
        "model": "orkestral-local",
    }
    try:
        with TestClient(create_app(settings)) as client:
            login = client.post(
                "/auth/login", json={"email": identity.email, "password": identity.password}
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            overview = client.get("/billing/overview", headers=headers)
            assert overview.status_code == 200
            agent_limit = next(
                item for item in overview.json()["limits"] if item["metric"] == "agents"
            )
            assert agent_limit == {
                "metric": "agents",
                "label": "Agentes",
                "used": 0,
                "limit": 1,
                "remaining": 1,
                "percentage": 0.0,
                "exceeded": False,
            }

            first = client.post("/agents", headers=headers, json=payload)
            assert first.status_code == 201

            second = client.post(
                "/agents",
                headers=headers,
                json={**payload, "name": "Agente bloqueado"},
            )
            assert second.status_code == 402
            assert "limite de agentes" in second.json()["detail"].lower()
    finally:
        asyncio.run(remove_billing_identity(settings, identity))

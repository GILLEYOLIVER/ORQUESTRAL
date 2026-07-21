from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.core.config import Settings
from app.core.resources import create_resources
from app.core.security import hash_password
from app.modules.authorization.policy_models import PolicyDecisionRecord
from app.modules.authorization.policy_schemas import (
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from app.modules.authorization.policy_service import evaluate_and_record_policy
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.events.models import OutboxEvent
from app.modules.users.models import CompanyUser, User


async def _exercise(settings: Settings) -> None:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    company_id: UUID | None = None
    user_email = f"policy-owner-{suffix}@example.com"
    correlation_id = uuid4()
    try:
        async with resources.sessions() as database:
            company = Company(
                legal_name=f"Policy {suffix} Ltda.",
                trade_name=f"Policy {suffix}",
                document_number=f"POL{suffix}",
                slug=f"policy-{suffix}",
                status="active",
            )
            user = User(
                name="Proprietario Policy",
                email=user_email,
                password_hash=hash_password("Policy-Ledger-2026!"),
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
            request = PolicyRequest(
                subject=PolicySubject(
                    user_id=user.id,
                    company_id=company.id,
                    permissions=frozenset({"crm.contacts.view"}),
                ),
                resource=PolicyResource(
                    company_id=uuid4(),
                    resource_type="crm.contact",
                    resource_id=str(uuid4()),
                ),
                action="view",
                required_permission="crm.contacts.view",
                requested_fields=("name", "email"),
                correlation_id=correlation_id,
            )
            decision = await evaluate_and_record_policy(database, request)
            assert decision.reason_code == "tenant_mismatch"
            await database.commit()

        async with resources.sessions() as database:
            record = await database.scalar(
                select(PolicyDecisionRecord).where(
                    PolicyDecisionRecord.company_id == company_id,
                    PolicyDecisionRecord.correlation_id == correlation_id,
                )
            )
            assert record is not None
            assert record.outcome == "deny"
            assert record.reason_code == "tenant_mismatch"

            event = await database.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.company_id == company_id,
                    OutboxEvent.correlation_id == correlation_id,
                    OutboxEvent.event_type == "security.policy.evaluated",
                )
            )
            assert event is not None
            assert event.payload["outcome"] == "deny"
            assert "resource_id" not in event.payload
    finally:
        if company_id is not None:
            async with resources.sessions() as database:
                await database.execute(delete(Company).where(Company.id == company_id))
                await database.execute(delete(User).where(User.email == user_email))
                await database.commit()
        await resources.close()


@pytest.mark.integration
def test_policy_decision_and_event_are_committed_together() -> None:
    asyncio.run(_exercise(Settings(app_env="testing")))

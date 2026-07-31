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
from app.modules.authentication.models import ReadOnlyAccessLink
from app.modules.authorization.models import AuthorizationAuditEvent
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class LinkIdentity:
    company_id: UUID
    foreign_company_id: UUID
    owner_id: UUID
    target_id: UUID
    foreign_target_id: UUID
    owner_email: str
    target_email: str
    password: str


async def _seed(settings: Settings) -> LinkIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Link-Seguro-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            company = Company(
                legal_name=f"Empresa Link {suffix} Ltda.",
                trade_name=f"Empresa Link {suffix}",
                document_number=f"LNK{suffix}",
                slug=f"empresa-link-{suffix}",
                status="active",
            )
            foreign = Company(
                legal_name=f"Empresa Estranha {suffix} Ltda.",
                trade_name=f"Empresa Estranha {suffix}",
                document_number=f"FRN{suffix}",
                slug=f"empresa-estranha-link-{suffix}",
                status="active",
            )
            owner = User(
                name="Administrador do link",
                email=f"owner-link-{suffix}@example.com",
                password_hash=hash_password(password),
                status="active",
            )
            target = User(
                name="Sócio observador",
                email=f"socio-link-{suffix}@example.com",
                password_hash=hash_password(password),
                status="active",
            )
            foreign_target = User(
                name="Usuário de outra empresa",
                email=f"foreign-link-{suffix}@example.com",
                password_hash=hash_password(password),
                status="active",
            )
            database.add_all((company, foreign, owner, target, foreign_target))
            await database.flush()
            owner_role, member_role = await ensure_company_system_roles(database, company.id)
            foreign_owner, _ = await ensure_company_system_roles(database, foreign.id)
            database.add_all(
                (
                    CompanyUser(
                        company_id=company.id,
                        user_id=owner.id,
                        role_id=owner_role.id,
                        status="active",
                        is_owner=True,
                    ),
                    CompanyUser(
                        company_id=company.id,
                        user_id=target.id,
                        role_id=member_role.id,
                        status="active",
                    ),
                    CompanyUser(
                        company_id=foreign.id,
                        user_id=foreign_target.id,
                        role_id=foreign_owner.id,
                        status="active",
                        is_owner=True,
                    ),
                )
            )
            await database.commit()
            return LinkIdentity(
                company_id=company.id,
                foreign_company_id=foreign.id,
                owner_id=owner.id,
                target_id=target.id,
                foreign_target_id=foreign_target.id,
                owner_email=owner.email,
                target_email=target.email,
                password=password,
            )
    finally:
        await resources.close()


async def _cleanup(settings: Settings, identity: LinkIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(
                delete(Company).where(
                    Company.id.in_((identity.company_id, identity.foreign_company_id))
                )
            )
            await database.execute(
                delete(User).where(
                    User.id.in_((identity.owner_id, identity.target_id, identity.foreign_target_id))
                )
            )
            await database.commit()
    finally:
        await resources.close()


async def _assert_persistence(
    settings: Settings, identity: LinkIdentity, link_id: UUID, raw_token: str
) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            link = await database.get(ReadOnlyAccessLink, link_id)
            assert link is not None
            assert link.token_hash != raw_token
            assert len(link.token_hash) == 64
            assert link.usage_count == 1
            actions = set(
                await database.scalars(
                    select(AuthorizationAuditEvent.action).where(
                        AuthorizationAuditEvent.company_id == identity.company_id,
                        AuthorizationAuditEvent.target_id == str(link_id),
                    )
                )
            )
            assert actions == {
                "read_only_access_link.created",
                "read_only_access_link.used",
            }
    finally:
        await resources.close()


@pytest.mark.integration
def test_secure_read_only_link_blocks_every_mutation_and_audits_usage() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            denied = client.post(
                "/auth/read-only-links/authorize",
                json={"email": identity.target_email, "password": identity.password},
            )
            assert denied.status_code == 403
            authorization = client.post(
                "/auth/read-only-links/authorize",
                json={"email": identity.owner_email, "password": identity.password},
            )
            assert authorization.status_code == 200
            body = authorization.json()
            assert {item["user_id"] for item in body["candidates"]} == {
                str(identity.owner_id),
                str(identity.target_id),
            }
            assert str(identity.foreign_target_id) not in str(body["candidates"])
            created = client.post(
                "/auth/read-only-links",
                headers={"X-Read-Only-Link-Authorization": body["authorization_token"]},
                json={
                    "company_id": str(identity.company_id),
                    "target_user_id": str(identity.target_id),
                    "expiration_minutes": 60,
                },
            )
            assert created.status_code == 201
            assert body["authorization_token"] not in created.text
            raw_token = created.json()["token"]
            replay = client.post(
                "/auth/read-only-links",
                headers={"X-Read-Only-Link-Authorization": body["authorization_token"]},
                json={
                    "company_id": str(identity.company_id),
                    "target_user_id": str(identity.target_id),
                    "expiration_minutes": 60,
                },
            )
            assert replay.status_code == 401

            exchanged = client.post("/auth/read-only-links/exchange", json={"token": raw_token})
            assert exchanged.status_code == 200
            headers = {"Authorization": f"Bearer {exchanged.json()['access_token']}"}
            profile = client.get("/auth/me", headers=headers)
            assert profile.status_code == 200
            assert profile.json()["access_mode"] == "read_only"
            assert profile.json()["access_profile"] == "Administrador Somente Leitura"
            assert profile.json()["current_company"]["id"] == str(identity.company_id)
            assert "users.update" in profile.json()["permissions"]
            assert "platform.companies.view" not in profile.json()["permissions"]
            assert client.get("/company/users", headers=headers).status_code == 200
            blocked = client.post(
                "/auth/select-company",
                headers=headers,
                json={"company_id": str(identity.company_id)},
            )
            assert blocked.status_code == 403
            assert blocked.headers["content-type"].startswith("application/problem+json")
            assert blocked.json()["detail"].startswith("Este acesso permite visualizar")
            assert client.post("/auth/logout").status_code == 204
            asyncio.run(
                _assert_persistence(
                    settings,
                    identity,
                    UUID(created.json()["id"]),
                    raw_token,
                )
            )
    finally:
        asyncio.run(_cleanup(settings, identity))

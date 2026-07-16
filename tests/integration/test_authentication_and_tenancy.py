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
class SeededIdentity:
    email: str
    password: str
    user_id: UUID
    company_id: UUID
    foreign_company_id: UUID
    member_role_id: UUID


async def seed_identity(settings: Settings) -> SeededIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Teste-Seguro-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            company = Company(
                legal_name=f"Empresa Autorizada {suffix} Ltda.",
                trade_name=f"Empresa Autorizada {suffix}",
                document_number=f"AUT{suffix}",
                slug=f"autorizada-{suffix}",
                status="active",
            )
            foreign_company = Company(
                legal_name=f"Empresa Estranha {suffix} Ltda.",
                trade_name=f"Empresa Estranha {suffix}",
                document_number=f"EXT{suffix}",
                slug=f"estranha-{suffix}",
                status="active",
            )
            user = User(
                name="Administrador de integração",
                email=f"admin-{suffix}@example.com",
                password_hash=hash_password(password),
                status="active",
                is_platform_admin=True,
            )
            database.add_all((company, foreign_company, user))
            await database.flush()
            owner_role, member_role = await ensure_company_system_roles(database, company.id)
            await ensure_company_system_roles(database, foreign_company.id)
            database.add(
                CompanyUser(
                    company_id=company.id,
                    user_id=user.id,
                    role_id=owner_role.id,
                    status="active",
                    is_owner=True,
                )
            )
            await database.commit()
            return SeededIdentity(
                email=user.email,
                password=password,
                user_id=user.id,
                company_id=company.id,
                foreign_company_id=foreign_company.id,
                member_role_id=member_role.id,
            )
    finally:
        await resources.close()


async def remove_identity(
    settings: Settings,
    identity: SeededIdentity,
    invitation_email: str,
    created_company_id: UUID | None,
) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            company_ids = [identity.company_id, identity.foreign_company_id]
            if created_company_id is not None:
                company_ids.append(created_company_id)
            await database.execute(delete(Company).where(Company.id.in_(company_ids)))
            await database.execute(
                delete(User).where(User.email.in_((identity.email, invitation_email)))
            )
            await database.commit()
    finally:
        await resources.close()


@pytest.mark.integration
def test_login_refresh_logout_invitation_and_tenant_isolation() -> None:
    settings = Settings(app_env="testing", development_expose_tokens=True)
    identity = asyncio.run(seed_identity(settings))
    invitation_email = f"membro-{uuid4().hex[:10]}@example.com"
    created_company_id: UUID | None = None
    app = create_app(settings)

    try:
        with TestClient(app) as client:
            login = client.post(
                "/auth/login",
                json={"email": identity.email, "password": identity.password},
            )
            assert login.status_code == 200
            access_token = login.json()["access_token"]
            first_refresh = client.cookies.get(settings.auth_cookie_name)
            assert first_refresh

            headers = {"Authorization": f"Bearer {access_token}"}
            profile = client.get("/auth/me", headers=headers)
            assert profile.status_code == 200
            assert profile.json()["current_company"]["id"] == str(identity.company_id)

            custom_role = client.post(
                "/authorization/roles",
                headers=headers,
                json={
                    "name": "Leitor de usuários",
                    "description": "Pode consultar a equipe sem administrá-la.",
                    "permission_codes": ["users.view"],
                },
            )
            assert custom_role.status_code == 201
            custom_role_id = custom_role.json()["id"]
            assert custom_role.json()["permission_codes"] == ["users.view"]

            immutable_system_role = client.patch(
                f"/authorization/roles/{identity.member_role_id}",
                headers=headers,
                json={"name": "Alteração indevida"},
            )
            assert immutable_system_role.status_code == 409

            company_suffix = uuid4().hex[:10]
            created_company = client.post(
                "/companies",
                headers=headers,
                json={
                    "legal_name": f"Empresa criada {company_suffix} Ltda.",
                    "trade_name": f"Empresa criada {company_suffix}",
                    "document_number": f"CRT{company_suffix}",
                    "slug": f"criada-{company_suffix}",
                    "status": "trial",
                },
            )
            assert created_company.status_code == 201
            created_company_id = UUID(created_company.json()["id"])

            foreign_selection = client.post(
                "/auth/select-company",
                headers=headers,
                json={"company_id": str(identity.foreign_company_id)},
            )
            assert foreign_selection.status_code == 403

            invitation = client.post(
                "/company/invitations",
                headers=headers,
                json={
                    "email": invitation_email,
                    "name": "Membro convidado",
                    "role_id": custom_role_id,
                },
            )
            assert invitation.status_code == 201
            invitation_token = invitation.json()["development_token"]
            assert invitation_token

            accepted = client.post(
                "/auth/accept-invitation",
                json={
                    "token": invitation_token,
                    "name": "Membro convidado",
                    "password": "Convite-Seguro-2026!",
                },
            )
            assert accepted.status_code == 200

            refreshed = client.post("/auth/refresh")
            assert refreshed.status_code == 200
            assert client.cookies.get(settings.auth_cookie_name) != first_refresh

            suspended = client.patch(
                f"/companies/{identity.company_id}",
                headers=headers,
                json={"status": "suspended"},
            )
            assert suspended.status_code == 200
            assert client.get("/companies", headers=headers).status_code == 200
            reactivated = client.patch(
                f"/companies/{identity.company_id}",
                headers=headers,
                json={"status": "active"},
            )
            assert reactivated.status_code == 200

            logout = client.post("/auth/logout")
            assert logout.status_code == 204
            assert client.post("/auth/refresh").status_code == 401

            member_login = client.post(
                "/auth/login",
                json={
                    "email": invitation_email,
                    "password": "Convite-Seguro-2026!",
                },
            )
            assert member_login.status_code == 200
            member_headers = {"Authorization": f"Bearer {member_login.json()['access_token']}"}
            member_profile = client.get("/auth/me", headers=member_headers)
            assert member_profile.status_code == 200
            assert member_profile.json()["current_company"]["id"] == str(identity.company_id)
            assert member_profile.json()["permissions"] == ["users.view"]
            assert client.get("/company/users", headers=member_headers).status_code == 200
            assert client.get("/authorization/roles", headers=member_headers).status_code == 403

            admin_login_again = client.post(
                "/auth/login",
                json={"email": identity.email, "password": identity.password},
            )
            assert admin_login_again.status_code == 200
            headers = {"Authorization": f"Bearer {admin_login_again.json()['access_token']}"}
            expanded_role = client.patch(
                f"/authorization/roles/{custom_role_id}",
                headers=headers,
                json={"permission_codes": ["roles.view", "users.view"]},
            )
            assert expanded_role.status_code == 200
            assert client.get("/authorization/roles", headers=member_headers).status_code == 200

            audit = client.get("/authorization/audit-events", headers=headers)
            assert audit.status_code == 200
            audit_actions = {event["action"] for event in audit.json()}
            assert {"role.created", "role.updated", "user.invited"} <= audit_actions

            forgot = client.post("/auth/forgot-password", json={"email": invitation_email})
            assert forgot.status_code == 202
            reset_token = forgot.json()["development_token"]
            assert reset_token
            reset = client.post(
                "/auth/reset-password",
                json={
                    "token": reset_token,
                    "password": "Senha-Nova-Segura-2026!",
                },
            )
            assert reset.status_code == 200
            assert client.get("/auth/me", headers=member_headers).status_code == 401
            assert (
                client.post(
                    "/auth/login",
                    json={
                        "email": invitation_email,
                        "password": "Convite-Seguro-2026!",
                    },
                ).status_code
                == 401
            )
            assert (
                client.post(
                    "/auth/login",
                    json={
                        "email": invitation_email,
                        "password": "Senha-Nova-Segura-2026!",
                    },
                ).status_code
                == 200
            )
    finally:
        asyncio.run(remove_identity(settings, identity, invitation_email, created_company_id))

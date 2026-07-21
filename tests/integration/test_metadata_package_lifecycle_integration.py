from __future__ import annotations

import asyncio
import copy
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
class PackageLifecycleIdentity:
    company_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> PackageLifecycleIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Package-Lifecycle-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Package Lifecycle {label} {suffix} Ltda.",
                    trade_name=f"Package Lifecycle {label} {suffix}",
                    document_number=f"PACKAGE{label}{suffix}",
                    slug=f"package-lifecycle-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Administrador Package {label}",
                    email=f"package-{label.lower()}-{suffix}@example.com",
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
            return PackageLifecycleIdentity(
                company_ids=(companies[0].id, companies[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: PackageLifecycleIdentity) -> None:
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


def _published_entity(client: TestClient, headers: dict[str, str], key: str) -> str:
    created = client.post(
        "/metadata/entities",
        headers=headers,
        json={
            "key": key,
            "label": key.replace("_", " ").title(),
            "plural_label": f"{key.replace('_', ' ').title()}s",
            "fields": [
                {
                    "key": "name",
                    "label": "Nome",
                    "data_type": "text",
                    "required": True,
                    "position": 0,
                }
            ],
        },
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    assert client.post(f"/metadata/entities/{entity_id}/validate", headers=headers).json()["valid"]
    assert (
        client.post(f"/metadata/entities/{entity_id}/publish", headers=headers).status_code == 200
    )
    return entity_id


def _release(
    client: TestClient,
    headers: dict[str, str],
    definition_id: str,
    version: str,
    dependencies: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    response = client.post(
        "/metadata/packages/releases",
        headers=headers,
        json={
            "definition_id": definition_id,
            "version": version,
            "dependencies": dependencies or [],
        },
    )
    assert response.status_code == 201, response.text
    release = response.json()
    validated = client.post(
        f"/metadata/packages/releases/{release['id']}/validate", headers=headers
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["valid"] is True
    published = client.post(f"/metadata/packages/releases/{release['id']}/publish", headers=headers)
    assert published.status_code == 200, published.text
    return published.json()


@pytest.mark.integration
def test_package_releases_dependencies_installation_and_promotion_are_tenant_safe() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)
            dependency_id = _published_entity(client, headers_a, "package_dependency")
            application_id = _published_entity(client, headers_a, "package_application")
            dependency_release = _release(client, headers_a, dependency_id, "1.0.0")
            application_release = _release(
                client,
                headers_a,
                application_id,
                "2.0.0",
                [{"package_key": "package_dependency", "version": "1.0.0"}],
            )
            duplicate = client.post(
                "/metadata/packages/releases",
                headers=headers_a,
                json={"definition_id": dependency_id, "version": "1.0.0"},
            )
            assert duplicate.status_code == 409
            cross_tenant = client.get(
                f"/metadata/packages/releases/{dependency_release['id']}/bundle", headers=headers_b
            )
            assert cross_tenant.status_code == 404
            dependency_bundle = client.get(
                f"/metadata/packages/releases/{dependency_release['id']}/bundle", headers=headers_a
            ).json()
            application_bundle = client.get(
                f"/metadata/packages/releases/{application_release['id']}/bundle", headers=headers_a
            ).json()
            assert str(identity.company_ids[0]) not in str(application_bundle)
            assert application_id not in str(application_bundle)

            missing = client.post(
                "/metadata/packages/installations/preview",
                headers=headers_b,
                json={"bundle": application_bundle, "target_environment": "testing"},
            ).json()
            assert missing["can_install"] is False
            assert "package_dependency@1.0.0" in missing["blockers"][0]

            dependency_preview = client.post(
                "/metadata/packages/installations/preview",
                headers=headers_b,
                json={"bundle": dependency_bundle, "target_environment": "testing"},
            ).json()
            assert dependency_preview["can_install"] is True
            installed_dependency = client.post(
                "/metadata/packages/installations",
                headers=headers_b,
                json={
                    "bundle": dependency_bundle,
                    "target_environment": "testing",
                    "plan_checksum": dependency_preview["plan_checksum"],
                },
            )
            assert installed_dependency.status_code == 201, installed_dependency.text

            application_preview = client.post(
                "/metadata/packages/installations/preview",
                headers=headers_b,
                json={
                    "bundle": application_bundle,
                    "target_environment": "testing",
                    "key_override": "installed_application",
                },
            ).json()
            assert application_preview["can_install"] is True
            assert application_preview["resolved_dependencies"] == ["package_dependency@1.0.0"]
            installed_application = client.post(
                "/metadata/packages/installations",
                headers=headers_b,
                json={
                    "bundle": application_bundle,
                    "target_environment": "testing",
                    "key_override": "installed_application",
                    "plan_checksum": application_preview["plan_checksum"],
                },
            )
            assert installed_application.status_code == 201, installed_application.text
            assert (
                len(client.get("/metadata/packages/installations", headers=headers_b).json()) == 2
            )
            assert client.get("/metadata/packages/releases", headers=headers_b).json() == []

            tampered = copy.deepcopy(application_bundle)
            tampered["manifest"]["display_name"] = "Conteudo alterado"
            tampered_preview = client.post(
                "/metadata/packages/installations/preview",
                headers=headers_b,
                json={
                    "bundle": tampered,
                    "target_environment": "testing",
                    "key_override": "tampered_application",
                },
            ).json()
            assert tampered_preview["can_install"] is False
            assert "corrompido" in tampered_preview["blockers"][0]

            blocked = client.post(
                f"/metadata/packages/releases/{application_release['id']}/promotion",
                headers=headers_a,
                json={"target_environment": "production"},
            ).json()
            assert blocked["allowed"] is False
            allowed = client.post(
                f"/metadata/packages/releases/{application_release['id']}/promotion",
                headers=headers_a,
                json={"target_environment": "development"},
            ).json()
            assert allowed["allowed"] is True
            assert allowed["bundle"]["checksum"] == application_bundle["checksum"]
    finally:
        asyncio.run(_remove(settings, identity))

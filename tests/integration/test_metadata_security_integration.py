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
class SecurityIdentity:
    company_ids: tuple[UUID, UUID]
    user_ids: tuple[UUID, UUID, UUID]
    emails: tuple[str, str, str]
    password: str


async def _seed(settings: Settings) -> SecurityIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Metadata-Security-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Metadata Security {label} {suffix} Ltda.",
                    trade_name=f"Metadata Security {label} {suffix}",
                    document_number=f"MSEC{label}{suffix}",
                    slug=f"metadata-security-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=name,
                    email=f"{prefix}-{suffix}@example.com",
                    password_hash=hash_password(password),
                    status="active",
                )
                for name, prefix in (
                    ("Proprietario Metadata", "metadata-owner"),
                    ("Operador Metadata", "metadata-operator"),
                    ("Proprietario Externo", "metadata-foreign"),
                )
            ]
            database.add_all((*companies, *users))
            await database.flush()
            owner_a, _ = await ensure_company_system_roles(database, companies[0].id)
            owner_b, _ = await ensure_company_system_roles(database, companies[1].id)
            database.add_all(
                (
                    CompanyUser(
                        company_id=companies[0].id,
                        user_id=users[0].id,
                        role_id=owner_a.id,
                        status="active",
                        is_owner=True,
                    ),
                    CompanyUser(
                        company_id=companies[0].id,
                        user_id=users[1].id,
                        role_id=owner_a.id,
                        status="active",
                        is_owner=False,
                    ),
                    CompanyUser(
                        company_id=companies[1].id,
                        user_id=users[2].id,
                        role_id=owner_b.id,
                        status="active",
                        is_owner=True,
                    ),
                )
            )
            await database.commit()
            return SecurityIdentity(
                company_ids=(companies[0].id, companies[1].id),
                user_ids=(users[0].id, users[1].id, users[2].id),
                emails=(users[0].email, users[1].email, users[2].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: SecurityIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(delete(Company).where(Company.id.in_(identity.company_ids)))
            await database.execute(delete(User).where(User.id.in_(identity.user_ids)))
            await database.commit()
    finally:
        await resources.close()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_metadata_security_enforces_fields_ownership_sharing_and_tenant_isolation() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            owner = _login(client, identity.emails[0], identity.password)
            operator = _login(client, identity.emails[1], identity.password)
            foreign = _login(client, identity.emails[2], identity.password)
            definition = client.post(
                "/metadata/entities",
                headers=owner,
                json={
                    "key": "secured_customer",
                    "label": "Cliente protegido",
                    "plural_label": "Clientes protegidos",
                    "fields": [
                        {
                            "key": "name",
                            "label": "Nome",
                            "data_type": "text",
                            "required": True,
                            "position": 0,
                        },
                        {
                            "key": "secret_note",
                            "label": "Nota restrita",
                            "data_type": "text",
                            "position": 1,
                        },
                    ],
                },
            )
            assert definition.status_code == 201
            definition_id = definition.json()["id"]
            assert client.post(
                f"/metadata/entities/{definition_id}/validate", headers=owner
            ).status_code == 200
            assert client.post(
                f"/metadata/entities/{definition_id}/publish", headers=owner
            ).status_code == 200

            configured = client.put(
                f"/metadata/entities/{definition_id}/security",
                headers=owner,
                json={
                    "entity_rules": [
                        {
                            "subject_type": "user",
                            "subject_id": str(identity.user_ids[1]),
                            "can_view": True,
                            "can_create": True,
                            "can_update": True,
                            "can_delete": False,
                            "can_export": False,
                            "record_scope": "owned_shared",
                        }
                    ],
                    "field_rules": [
                        {
                            "field_key": "secret_note",
                            "subject_type": "user",
                            "subject_id": str(identity.user_ids[1]),
                            "can_view": False,
                            "can_edit": False,
                        }
                    ],
                },
            )
            assert configured.status_code == 200
            assert configured.json()["configured"] is True

            forbidden_create = client.post(
                f"/metadata/entities/{definition_id}/records",
                headers=operator,
                json={"values": {"name": "Operador", "secret_note": "nao expor"}},
            )
            assert forbidden_create.status_code == 403
            own_record = client.post(
                f"/metadata/entities/{definition_id}/records",
                headers=operator,
                json={"values": {"name": "Registro do operador"}},
            )
            assert own_record.status_code == 201
            assert own_record.json()["owner_user_id"] == str(identity.user_ids[1])
            owner_record = client.post(
                f"/metadata/entities/{definition_id}/records",
                headers=owner,
                json={"values": {"name": "Registro do socio", "secret_note": "restrito"}},
            )
            assert owner_record.status_code == 201
            record_id = owner_record.json()["id"]

            before_share = client.get(
                f"/metadata/entities/{definition_id}/records", headers=operator
            )
            assert before_share.status_code == 200
            assert before_share.json()["total"] == 1
            assert client.get(
                f"/metadata/entities/{definition_id}/records/{record_id}", headers=operator
            ).status_code == 404

            shared = client.post(
                f"/metadata/entities/{definition_id}/records/{record_id}/shares",
                headers=owner,
                json={
                    "subject_type": "user",
                    "subject_id": str(identity.user_ids[1]),
                    "can_view": True,
                    "can_edit": True,
                },
            )
            assert shared.status_code == 201
            after_share = client.get(
                f"/metadata/entities/{definition_id}/records", headers=operator
            )
            assert after_share.status_code == 200
            assert after_share.json()["total"] == 2
            visible = client.get(
                f"/metadata/entities/{definition_id}/records/{record_id}", headers=operator
            )
            assert visible.status_code == 200
            assert visible.json()["values"] == {"name": "Registro do socio"}
            assert visible.json()["masked_fields"] == ["secret_note"]

            updated = client.put(
                f"/metadata/entities/{definition_id}/records/{record_id}",
                headers=operator,
                json={"values": {"name": "Atualizado com acesso"}, "expected_version": 1},
            )
            assert updated.status_code == 200
            forbidden_field = client.put(
                f"/metadata/entities/{definition_id}/records/{record_id}",
                headers=operator,
                json={"values": {"secret_note": "tentativa"}, "expected_version": 2},
            )
            assert forbidden_field.status_code == 403
            forbidden_delete = client.delete(
                f"/metadata/entities/{definition_id}/records/{record_id}",
                headers=operator,
                params={"expected_version": 2},
            )
            assert forbidden_delete.status_code == 403

            assert client.get(
                f"/metadata/entities/{definition_id}/security", headers=foreign
            ).status_code == 404
            assert client.post(
                f"/metadata/entities/{definition_id}/records/{record_id}/shares",
                headers=foreign,
                json={
                    "subject_type": "user",
                    "subject_id": str(identity.user_ids[2]),
                    "can_view": True,
                },
            ).status_code == 404
    finally:
        asyncio.run(_remove(settings, identity))

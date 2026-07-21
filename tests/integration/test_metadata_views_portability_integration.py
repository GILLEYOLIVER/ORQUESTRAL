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
class PortableMetadataIdentity:
    company_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> PortableMetadataIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Metadata-Views-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Portable Metadata {label} {suffix} Ltda.",
                    trade_name=f"Portable Metadata {label} {suffix}",
                    document_number=f"PORTABLE{label}{suffix}",
                    slug=f"portable-metadata-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Administrador Portable {label}",
                    email=f"portable-{label.lower()}-{suffix}@example.com",
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
            return PortableMetadataIdentity(
                company_ids=(companies[0].id, companies[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: PortableMetadataIdentity) -> None:
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


@pytest.mark.integration
def test_metadata_views_filter_paginate_and_packages_are_tenant_safe() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)
            created = client.post(
                "/metadata/entities",
                headers=headers_a,
                json={
                    "key": "portable_order",
                    "label": "Pedido portatil",
                    "plural_label": "Pedidos portateis",
                    "fields": [
                        {
                            "key": "name",
                            "label": "Nome",
                            "data_type": "text",
                            "required": True,
                            "position": 0,
                        },
                        {
                            "key": "amount",
                            "label": "Valor",
                            "data_type": "decimal",
                            "position": 1,
                        },
                    ],
                },
            )
            assert created.status_code == 201
            definition_id = created.json()["id"]
            design_payload = {
                "layouts": [
                    {
                        "key": "default_layout",
                        "label": "Formulario principal",
                        "is_default": True,
                        "sections": [
                            {
                                "key": "main_section",
                                "label": "Dados",
                                "fields": ["name", "amount"],
                                "columns": 2,
                            }
                        ],
                    }
                ],
                "views": [
                    {
                        "key": "all_orders",
                        "label": "Todos os pedidos",
                        "columns": ["name", "amount"],
                        "filters": [],
                        "sorting": [{"field_key": "name", "direction": "asc"}],
                        "is_default": True,
                    },
                    {
                        "key": "high_value",
                        "label": "Alto valor",
                        "columns": ["name", "amount"],
                        "filters": [
                            {
                                "field_key": "amount",
                                "operator": "greater_than",
                                "value": "100",
                            }
                        ],
                        "sorting": [{"field_key": "amount", "direction": "desc"}],
                        "is_default": False,
                    },
                ],
                "validation_rules": [],
                "relationships": [],
                "formulas": [],
                "record_types": [
                    {
                        "key": "default",
                        "label": "Padrao",
                        "layout_key": "default_layout",
                        "is_default": True,
                        "active": True,
                    }
                ],
            }
            updated_design = client.put(
                f"/metadata/entities/{definition_id}/design",
                headers=headers_a,
                json=design_payload,
            )
            assert updated_design.status_code == 200
            assert (
                client.post(
                    f"/metadata/entities/{definition_id}/validate", headers=headers_a
                ).json()["valid"]
                is True
            )
            assert (
                client.post(
                    f"/metadata/entities/{definition_id}/publish", headers=headers_a
                ).status_code
                == 200
            )

            for name, amount in (("Basico", "50"), ("Premium", "250"), ("Plus", "150")):
                response = client.post(
                    f"/metadata/entities/{definition_id}/records",
                    headers=headers_a,
                    json={"values": {"name": name, "amount": amount}},
                )
                assert response.status_code == 201

            first_page = client.get(
                f"/metadata/entities/{definition_id}/records",
                headers=headers_a,
                params={"view_key": "high_value", "page": 1, "page_size": 1},
            )
            assert first_page.status_code == 200
            assert first_page.json()["total"] == 2
            assert first_page.json()["pages"] == 2
            assert first_page.json()["items"][0]["values"]["name"] == "Premium"
            second_page = client.get(
                f"/metadata/entities/{definition_id}/records",
                headers=headers_a,
                params={"view_key": "high_value", "page": 2, "page_size": 1},
            )
            assert second_page.json()["items"][0]["values"]["name"] == "Plus"
            assert (
                client.get(
                    f"/metadata/entities/{definition_id}/records",
                    headers=headers_a,
                    params={"view_key": "missing_view"},
                ).status_code
                == 404
            )
            assert (
                client.get(
                    f"/metadata/entities/{definition_id}/records", headers=headers_b
                ).status_code
                == 404
            )

            exported = client.get(f"/metadata/entities/{definition_id}/package", headers=headers_a)
            assert exported.status_code == 200
            package = exported.json()
            serialized = exported.text
            assert str(identity.company_ids[0]) not in serialized
            assert definition_id not in serialized
            assert "record_version" not in serialized
            assert package["definition"]["design"]["views"][1]["key"] == "high_value"

            tampered = copy.deepcopy(package)
            tampered["definition"]["label"] = "Pacote adulterado"
            assert (
                client.post(
                    "/metadata/packages/import",
                    headers=headers_b,
                    json={"package": tampered, "key_override": "tampered_order"},
                ).status_code
                == 422
            )

            imported = client.post(
                "/metadata/packages/import",
                headers=headers_b,
                json={"package": package, "key_override": "imported_order"},
            )
            assert imported.status_code == 201
            imported_id = imported.json()["id"]
            imported_design = client.get(
                f"/metadata/entities/{imported_id}/design", headers=headers_b
            )
            assert imported_design.status_code == 200
            assert [item["key"] for item in imported_design.json()["views"]] == [
                "all_orders",
                "high_value",
            ]
            assert (
                client.post(
                    "/metadata/packages/import",
                    headers=headers_b,
                    json={"package": package, "key_override": "imported_order"},
                ).status_code
                == 409
            )
    finally:
        asyncio.run(_remove(settings, identity))

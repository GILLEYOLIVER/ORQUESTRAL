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
class AdvancedMetadataIdentity:
    company_ids: tuple[UUID, UUID]
    user_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> AdvancedMetadataIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Metadata-Advanced-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = [
                Company(
                    legal_name=f"Advanced Metadata {label} {suffix} Ltda.",
                    trade_name=f"Advanced Metadata {label} {suffix}",
                    document_number=f"ADVMETA{label}{suffix}",
                    slug=f"advanced-metadata-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            ]
            users = [
                User(
                    name=f"Administrador Advanced {label}",
                    email=f"advanced-metadata-{label.lower()}-{suffix}@example.com",
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
            return AdvancedMetadataIdentity(
                company_ids=(companies[0].id, companies[1].id),
                user_ids=(users[0].id, users[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: AdvancedMetadataIdentity) -> None:
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


def _create_published_entity(
    client: TestClient,
    headers: dict[str, str],
    *,
    key: str,
    label: str,
    fields: list[dict[str, object]],
) -> str:
    created = client.post(
        "/metadata/entities",
        headers=headers,
        json={
            "key": key,
            "label": label,
            "plural_label": f"{label}s",
            "fields": fields,
        },
    )
    assert created.status_code == 201
    entity_id = created.json()["id"]
    validated = client.post(f"/metadata/entities/{entity_id}/validate", headers=headers)
    assert validated.status_code == 200 and validated.json()["valid"] is True
    assert (
        client.post(f"/metadata/entities/{entity_id}/publish", headers=headers).status_code == 200
    )
    return entity_id


@pytest.mark.integration
def test_relations_formulas_and_record_types_are_versioned_and_tenant_safe() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)
            account_fields = [
                {
                    "key": "name",
                    "label": "Nome",
                    "data_type": "text",
                    "required": True,
                    "position": 0,
                }
            ]
            foreign_account_id = _create_published_entity(
                client,
                headers_a,
                key="foreign_account",
                label="Conta externa",
                fields=account_fields,
            )
            foreign_record = client.post(
                f"/metadata/entities/{foreign_account_id}/records",
                headers=headers_a,
                json={"values": {"name": "Outra empresa"}},
            )
            assert foreign_record.status_code == 201

            account_id = _create_published_entity(
                client,
                headers_b,
                key="account",
                label="Conta",
                fields=account_fields,
            )
            account_record = client.post(
                f"/metadata/entities/{account_id}/records",
                headers=headers_b,
                json={"values": {"name": "Cliente principal"}},
            )
            assert account_record.status_code == 201
            account_record_id = account_record.json()["id"]

            order_fields = [
                {"key": "name", "label": "Nome", "data_type": "text", "position": 0},
                {
                    "key": "account_id",
                    "label": "Conta",
                    "data_type": "uuid",
                    "position": 1,
                },
                {
                    "key": "quantity",
                    "label": "Quantidade",
                    "data_type": "decimal",
                    "position": 2,
                },
                {
                    "key": "unit_price",
                    "label": "Preco unitario",
                    "data_type": "decimal",
                    "position": 3,
                },
                {
                    "key": "total",
                    "label": "Total",
                    "data_type": "decimal",
                    "position": 4,
                },
            ]
            order = client.post(
                "/metadata/entities",
                headers=headers_b,
                json={
                    "key": "order",
                    "label": "Pedido",
                    "plural_label": "Pedidos",
                    "fields": order_fields,
                },
            )
            assert order.status_code == 201
            order_id = order.json()["id"]

            def design(target_id: str) -> dict[str, object]:
                return {
                    "layouts": [
                        {
                            "key": "default_layout",
                            "label": "Pedido padrao",
                            "sections": [
                                {
                                    "key": "main_section",
                                    "label": "Dados principais",
                                    "fields": [
                                        "name",
                                        "account_id",
                                        "quantity",
                                        "unit_price",
                                        "total",
                                    ],
                                    "columns": 2,
                                }
                            ],
                            "is_default": True,
                        },
                        {
                            "key": "priority_layout",
                            "label": "Pedido prioritario",
                            "sections": [
                                {
                                    "key": "priority_section",
                                    "label": "Operacao prioritaria",
                                    "fields": ["name", "account_id", "total"],
                                    "columns": 1,
                                }
                            ],
                            "is_default": False,
                        },
                    ],
                    "views": [
                        {
                            "key": "default_view",
                            "label": "Pedidos",
                            "columns": ["name", "total"],
                            "filters": [],
                            "sorting": [],
                            "is_default": True,
                        }
                    ],
                    "validation_rules": [],
                    "relationships": [
                        {
                            "key": "order_account",
                            "label": "Conta do pedido",
                            "source_field_key": "account_id",
                            "target_definition_id": target_id,
                            "relationship_type": "many_to_one",
                            "on_delete": "restrict",
                        }
                    ],
                    "formulas": [
                        {
                            "key": "order_total",
                            "label": "Total do pedido",
                            "target_field_key": "total",
                            "expression": {
                                "operator": "multiply",
                                "operands": [
                                    {"type": "field", "field_key": "quantity"},
                                    {"type": "field", "field_key": "unit_price"},
                                ],
                            },
                            "active": True,
                        }
                    ],
                    "record_types": [
                        {
                            "key": "standard",
                            "label": "Padrao",
                            "layout_key": "default_layout",
                            "is_default": True,
                            "active": True,
                        },
                        {
                            "key": "priority",
                            "label": "Prioritario",
                            "layout_key": "priority_layout",
                            "is_default": False,
                            "active": True,
                        },
                    ],
                }

            cross_tenant = client.put(
                f"/metadata/entities/{order_id}/design",
                headers=headers_b,
                json=design(foreign_account_id),
            )
            assert cross_tenant.status_code == 422
            assert "destino indisponivel" in cross_tenant.json()["detail"]

            configured = client.put(
                f"/metadata/entities/{order_id}/design",
                headers=headers_b,
                json=design(account_id),
            )
            assert configured.status_code == 200
            assert configured.json()["record_types"][1]["layout_key"] == "priority_layout"
            assert configured.json()["formulas"][0]["expression"]["operator"] == "multiply"
            assert (
                client.get(f"/metadata/entities/{order_id}/design", headers=headers_a).status_code
                == 404
            )
            validated = client.post(f"/metadata/entities/{order_id}/validate", headers=headers_b)
            assert validated.status_code == 200 and validated.json()["valid"] is True
            assert (
                client.post(f"/metadata/entities/{order_id}/publish", headers=headers_b).status_code
                == 200
            )

            created_order = client.post(
                f"/metadata/entities/{order_id}/records",
                headers=headers_b,
                json={
                    "record_type_key": "priority",
                    "values": {
                        "name": "Pedido seguro",
                        "account_id": account_record_id,
                        "quantity": "3",
                        "unit_price": "12.50",
                    },
                },
            )
            assert created_order.status_code == 201
            assert created_order.json()["record_type_key"] == "priority"
            assert created_order.json()["values"]["total"] == "37.50"

            manual_formula = client.post(
                f"/metadata/entities/{order_id}/records",
                headers=headers_b,
                json={
                    "values": {
                        "name": "Manipulado",
                        "account_id": account_record_id,
                        "quantity": "1",
                        "unit_price": "1",
                        "total": "0",
                    }
                },
            )
            assert manual_formula.status_code == 422
            assert "nao aceita valor manual" in manual_formula.json()["detail"]

            foreign_reference = client.post(
                f"/metadata/entities/{order_id}/records",
                headers=headers_b,
                json={
                    "values": {
                        "name": "Referencia externa",
                        "account_id": foreign_record.json()["id"],
                        "quantity": "1",
                        "unit_price": "1",
                    }
                },
            )
            assert foreign_reference.status_code == 422
            assert "nao foi encontrado" in foreign_reference.json()["detail"]

            blocked_delete = client.delete(
                f"/metadata/entities/{account_id}/records/{account_record_id}?expected_version=1",
                headers=headers_b,
            )
            assert blocked_delete.status_code == 409
            assert "esta em uso" in blocked_delete.json()["detail"]
    finally:
        asyncio.run(_remove(settings, identity))

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterator
from typing import get_args

from fastapi.routing import APIRoute
from pydantic import BaseModel

import app.core.model_registry  # noqa: F401
from app.core.database import Base
from app.main import create_app
from app.modules.authorization.catalog import (
    PLATFORM_PERMISSION_CODES,
    TENANT_PERMISSION_CODES,
)

GLOBAL_TABLES = frozenset(
    {
        "auth_attempts",
        "auth_sessions",
        "companies",
        "metric_aggregation_runs",
        "modules_catalog",
        "password_reset_tokens",
        "permissions",
        "plans",
        "plugins",
        "users",
    }
)

# These associations inherit their tenant boundary from both referenced parents.
PARENT_SCOPED_ASSOCIATIONS = frozenset({"crm_contact_tags", "role_permissions"})

SELF_SERVICE_MUTATIONS = frozenset(
    {
        "/notifications/preferences",
        "/notifications/read-all",
        "/notifications/{notification_id}/read",
    }
)

SIGNED_WEBHOOKS = frozenset(
    {
        "/webhooks/workflows/{public_key}",
        "/support/ingress/{company_id}/{public_key}",
    }
)
SIGNED_MONITOR_READS = frozenset({"/health/agent-memory-scheduler"})
PUBLIC_READ_ROUTES = frozenset(
    {
        "/auth/development-access",
        "/health",
        "/ready",
        "/system/capabilities",
        "/system/features",
        "/system/version",
    }
)

FORBIDDEN_RESPONSE_FIELDS = frozenset(
    {
        "api_key",
        "api_token",
        "client_secret",
        "encrypted_credentials",
        "encrypted_payload",
        "encryption_key",
        "password",
        "password_hash",
        "private_key",
        "refresh_token",
        "refresh_token_hash",
        "token_hash",
    }
)


def _application_routes() -> Iterator[APIRoute]:
    application = create_app()
    for included_router in application.routes:
        router = getattr(included_router, "original_router", None)
        for route in getattr(router, "routes", ()):  # pragma: no branch - tiny adapter
            if isinstance(route, APIRoute):
                yield route


def _dependency_calls(route: APIRoute) -> list[Callable[..., object]]:
    calls: list[Callable[..., object]] = []
    dependencies = list(route.dependant.dependencies)
    while dependencies:
        dependency = dependencies.pop()
        if dependency.call is not None:
            calls.append(dependency.call)
        dependencies.extend(dependency.dependencies)
    return calls


def _dependency_names(route: APIRoute) -> set[str]:
    return {getattr(call, "__name__", type(call).__name__) for call in _dependency_calls(route)}


def _response_models(annotation: object) -> set[type[BaseModel]]:
    models: set[type[BaseModel]] = set()
    candidates = [annotation]
    while candidates:
        candidate = candidates.pop()
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            if candidate in models:
                continue
            models.add(candidate)
            candidates.extend(field.annotation for field in candidate.model_fields.values())
        candidates.extend(get_args(candidate))
    return models


def test_every_business_table_has_an_explicit_tenant_scope() -> None:
    without_company_id = {
        table.name for table in Base.metadata.tables.values() if "company_id" not in table.c
    }
    expected = GLOBAL_TABLES | PARENT_SCOPED_ASSOCIATIONS

    assert without_company_id == expected, (
        "Toda nova tabela sem company_id deve ser classificada explicitamente como global "
        "ou como associação protegida pelos registros pais. "
        f"Esperado={sorted(expected)}; encontrado={sorted(without_company_id)}"
    )


def test_tenant_columns_are_indexed_and_reference_company() -> None:
    for table in Base.metadata.tables.values():
        if "company_id" not in table.c:
            continue

        company_id = table.c.company_id
        references = {foreign_key.target_fullname for foreign_key in company_id.foreign_keys}
        on_delete = {foreign_key.ondelete for foreign_key in company_id.foreign_keys}

        assert company_id.index is True, f"{table.name}.company_id precisa de indice."
        assert references == {"companies.id"}, (
            f"{table.name}.company_id deve referenciar somente companies.id."
        )

        if table.name == "audit_events":
            assert company_id.nullable is True
            assert on_delete == {"SET NULL"}
        else:
            assert company_id.nullable is False, f"{table.name}.company_id nao pode aceitar NULL."
            assert on_delete == {"CASCADE"}


def test_every_declared_route_permission_exists_in_the_catalog() -> None:
    catalog = TENANT_PERMISSION_CODES | PLATFORM_PERMISSION_CODES
    declared: set[str] = set()

    for route in _application_routes():
        for call in _dependency_calls(route):
            if getattr(call, "__name__", "") != "permission_dependency":
                continue
            permission_code = inspect.getclosurevars(call).nonlocals["permission_code"]
            declared.add(permission_code)

    assert declared
    assert declared <= catalog, (
        f"Rotas usam permissoes ausentes do catalogo: {sorted(declared - catalog)}"
    )


def test_business_mutations_require_an_explicit_security_boundary() -> None:
    mutation_methods = {"POST", "PUT", "PATCH", "DELETE"}
    failures: list[str] = []

    for route in _application_routes():
        methods = set(route.methods or set()) & mutation_methods
        if not methods or route.path.startswith("/auth/"):
            continue

        dependency_names = _dependency_names(route)
        if route.path in SIGNED_WEBHOOKS:
            continue
        if route.path in SELF_SERVICE_MUTATIONS:
            if "get_current_principal" not in dependency_names:
                failures.append(f"{sorted(methods)} {route.path}: sem usuario autenticado")
            continue
        if not {"permission_dependency", "require_platform_admin"} & dependency_names:
            failures.append(f"{sorted(methods)} {route.path}: sem permissao explicita")

    assert not failures, "\n".join(failures)


def test_non_public_reads_require_an_authenticated_principal() -> None:
    failures: list[str] = []

    for route in _application_routes():
        if "GET" not in set(route.methods or set()) or route.path in PUBLIC_READ_ROUTES:
            continue
        if route.path in SIGNED_MONITOR_READS:
            assert "verify_agent_memory_monitor" in _dependency_names(route)
            continue
        if "get_current_principal" not in _dependency_names(route):
            failures.append(f"GET {route.path}: sem usuario autenticado")

    assert not failures, "\n".join(failures)


def test_api_response_contracts_never_publish_secret_material() -> None:
    failures: list[str] = []
    for route in _application_routes():
        if route.response_model is None:
            continue
        for model in _response_models(route.response_model):
            exposed = FORBIDDEN_RESPONSE_FIELDS & model.model_fields.keys()
            if exposed:
                failures.append(
                    f"{route.path} ({model.__name__}): {sorted(exposed)}"
                )

    assert not failures, "Campos sensíveis em respostas da API:\n" + "\n".join(failures)

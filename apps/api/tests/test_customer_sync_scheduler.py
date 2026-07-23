from __future__ import annotations

from fastapi.testclient import TestClient

from app.modules.crm.customer_sync_adapters import evaluate_adapter_readiness
from app.modules.crm.customer_sync_scheduler_service import adapter_catalog


def test_adapter_readiness_is_fail_closed() -> None:
    assert (
        evaluate_adapter_readiness(
            adapter_key="unknown",
            transport="pull",
            credential_configured=True,
            connection_test_success=True,
        ).status
        == "blocked"
    )
    assert (
        evaluate_adapter_readiness(
            adapter_key="generic_rest_pull",
            transport="pull",
            credential_configured=False,
            connection_test_success=None,
        ).error_code
        == "CREDENTIAL_REQUIRED"
    )
    assert (
        evaluate_adapter_readiness(
            adapter_key="generic_rest_pull",
            transport="pull",
            credential_configured=True,
            connection_test_success=None,
        ).status
        == "unverified"
    )
    assert evaluate_adapter_readiness(
        adapter_key="generic_rest_pull",
        transport="pull",
        credential_configured=True,
        connection_test_success=True,
    ).can_dispatch


def test_adapter_catalog_exposes_capabilities_without_secret_values() -> None:
    adapters = adapter_catalog()
    assert {adapter.key for adapter in adapters} == {
        "secure_push",
        "generic_rest_pull",
        "signed_webhook",
    }
    assert all(not hasattr(adapter, "credential_id") for adapter in adapters)
    assert all(not hasattr(adapter, "token") for adapter in adapters)


def test_customer_sync_scheduler_routes_are_protected(client: TestClient) -> None:
    assert client.get("/crm/customer-data/sync/adapters").status_code == 401
    assert client.get("/crm/customer-data/sync/adapter-health").status_code == 401
    assert client.get("/crm/customer-data/sync/dispatches").status_code == 401
    paths = client.get("/openapi.json").json()["paths"]
    assert "/crm/customer-data/sync/adapters" in paths
    assert "/crm/customer-data/sync/adapter-health" in paths
    assert "/crm/customer-data/sync/connectors/{connector_id}/health" in paths
    assert "/crm/customer-data/sync/dispatches" in paths
    assert "/crm/customer-data/sync/scheduler-summary" in paths

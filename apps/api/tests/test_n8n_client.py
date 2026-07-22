from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.modules.workflows.services.n8n_client import (
    N8nClient,
    N8nConfigurationError,
    N8nRequestError,
)


def workflow_definition() -> dict[str, object]:
    return {"nodes": [], "connections": {}, "settings": {}}


@pytest.mark.asyncio
async def test_n8n_client_uses_api_key_and_official_create_endpoint() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("X-N8N-API-KEY", "")
        return httpx.Response(200, json={"id": "workflow-1", "versionId": "version-1"})

    settings = Settings(
        n8n_base_url="http://automation.internal:5678",
        n8n_api_key="valid-api-key-with-enough-entropy",
    )
    client = N8nClient(settings, transport=httpx.MockTransport(handler))

    result = await client.create_workflow("Teste", workflow_definition())

    assert result["id"] == "workflow-1"
    assert seen == {"path": "/api/v1/workflows", "key": settings.n8n_api_key}


@pytest.mark.asyncio
async def test_n8n_client_retries_transient_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts == 1 else 200, json={"data": []})

    client = N8nClient(
        Settings(n8n_api_key="valid-api-key-with-enough-entropy"),
        transport=httpx.MockTransport(handler),
        retry_delay_seconds=0,
    )

    await client.test_connection()

    assert attempts == 2


@pytest.mark.asyncio
async def test_n8n_client_rejects_placeholder_key_without_network_call() -> None:
    client = N8nClient(Settings())

    with pytest.raises(N8nConfigurationError, match="aguarda"):
        await client.test_connection()


@pytest.mark.asyncio
async def test_internal_webhook_does_not_send_admin_api_key() -> None:
    seen_key: str | None = "not-called"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_key
        seen_key = request.headers.get("X-N8N-API-KEY")
        return httpx.Response(200, json={"ok": True})

    client = N8nClient(
        Settings(n8n_api_key="valid-api-key-with-enough-entropy"),
        transport=httpx.MockTransport(handler),
    )

    await client.trigger_webhook("private-path", {"company_id": "company"})

    assert seen_key is None


@pytest.mark.asyncio
async def test_public_adapter_does_not_fake_remote_cancellation() -> None:
    client = N8nClient(Settings(n8n_api_key="valid-api-key-with-enough-entropy"))
    assert client.supports_remote_cancellation is False
    assert await client.cancel_execution("execution-1") is False


@pytest.mark.asyncio
async def test_update_restores_previous_workflow_when_n8n_rejects_change() -> None:
    put_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "name": "Anterior",
                    "nodes": [{"id": "old"}],
                    "connections": {},
                    "settings": {},
                },
            )
        put_payloads.append(json.loads(request.content))
        if len(put_payloads) == 1:
            return httpx.Response(400, json={"message": "invalid"})
        return httpx.Response(200, json={"id": "workflow-1"})

    client = N8nClient(
        Settings(n8n_api_key="valid-api-key-with-enough-entropy"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(N8nRequestError, match="versão anterior foi restaurada"):
        await client.update_workflow_with_rollback("workflow-1", "Nova", workflow_definition())

    assert put_payloads[0]["name"] == "Nova"
    assert put_payloads[1]["name"] == "Anterior"
    assert put_payloads[1]["nodes"] == [{"id": "old"}]

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings


class N8nClientError(RuntimeError):
    pass


class N8nConfigurationError(N8nClientError):
    pass


class N8nUnavailableError(N8nClientError):
    pass


class N8nRequestError(N8nClientError):
    pass


class N8nClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_delay_seconds: float = 0.2,
    ) -> None:
        self._base_url = str(settings.n8n_base_url).rstrip("/")
        self._api_key = settings.n8n_api_key.strip()
        self._timeout = settings.n8n_timeout_seconds
        self._max_attempts = settings.n8n_max_attempts
        self._transport = transport
        self._retry_delay_seconds = retry_delay_seconds

    @property
    def configured(self) -> bool:
        lowered = self._api_key.lower()
        return bool(self._api_key) and not any(
            marker in lowered for marker in ("change-me", "development-only", "placeholder")
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        require_api_key: bool = True,
    ) -> dict[str, Any]:
        if require_api_key and not self.configured:
            raise N8nConfigurationError(
                "O motor de automação aguarda uma chave administrativa válida."
            )
        headers = {"Accept": "application/json"}
        if require_api_key:
            headers["X-N8N-API-KEY"] = self._api_key
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            follow_redirects=True,
        ) as client:
            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = await client.request(
                        method,
                        path,
                        headers=headers,
                        json=json_data,
                        params=params,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                    if attempt < self._max_attempts:
                        await asyncio.sleep(self._retry_delay_seconds * attempt)
                        continue
                    raise N8nUnavailableError(
                        "O motor de automação está temporariamente indisponível."
                    ) from exc
                if response.status_code in {429, 502, 503, 504} and attempt < self._max_attempts:
                    await asyncio.sleep(self._retry_delay_seconds * attempt)
                    continue
                if response.status_code == 401:
                    raise N8nConfigurationError(
                        "A chave do motor de automação foi recusada."
                    )
                if response.status_code == 404:
                    raise N8nRequestError("A automação não foi encontrada no motor interno.")
                if response.status_code >= 400:
                    raise N8nRequestError(
                        f"O motor interno recusou a operação (HTTP {response.status_code})."
                    )
                if response.status_code == 204 or not response.content:
                    return {}
                try:
                    data = response.json()
                except ValueError as exc:
                    raise N8nRequestError(
                        "O motor interno devolveu uma resposta inválida."
                    ) from exc
                return data if isinstance(data, dict) else {"data": data}
        raise N8nUnavailableError("O motor de automação não respondeu.") from last_error

    async def test_connection(self) -> None:
        await self._request(
            "GET",
            "/api/v1/workflows",
            params={"limit": 1, "excludePinnedData": "true"},
        )

    async def create_workflow(
        self, name: str, definition: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/workflows",
            json_data={"name": name, **definition},
        )

    async def update_workflow(
        self, workflow_id: str, name: str, definition: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "PUT",
            f"/api/v1/workflows/{quote(workflow_id, safe='')}",
            json_data={"name": name, **definition},
        )

    async def update_workflow_with_rollback(
        self, workflow_id: str, name: str, definition: dict[str, Any]
    ) -> dict[str, Any]:
        previous = await self.get_workflow(workflow_id)
        previous_definition = {
            key: previous.get(key, default)
            for key, default in (
                ("nodes", []),
                ("connections", {}),
                ("settings", {}),
            )
        }
        previous_name = str(previous.get("name") or name)
        try:
            return await self.update_workflow(workflow_id, name, definition)
        except N8nClientError as update_error:
            try:
                await self.update_workflow(
                    workflow_id, previous_name, previous_definition
                )
            except N8nClientError as rollback_error:
                raise N8nRequestError(
                    "A atualização falhou e a restauração automática também falhou."
                ) from rollback_error
            raise N8nRequestError(
                "A atualização foi recusada; a versão anterior foi restaurada."
            ) from update_error

    async def activate_workflow(self, workflow_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v1/workflows/{quote(workflow_id, safe='')}/activate"
        )

    async def deactivate_workflow(self, workflow_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v1/workflows/{quote(workflow_id, safe='')}/deactivate"
        )

    async def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/workflows/{quote(workflow_id, safe='')}"
        )

    async def list_executions(
        self, workflow_id: str, *, limit: int = 20
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/v1/executions",
            params={
                "workflowId": workflow_id,
                "limit": limit,
                "includeData": "false",
                "redactExecutionData": "true",
            },
        )

    async def get_execution(self, execution_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/executions/{quote(execution_id, safe='')}",
            params={"includeData": "false", "redactExecutionData": "true"},
        )

    async def trigger_webhook(
        self, webhook_path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/webhook/{quote(webhook_path, safe='')}",
            json_data=payload,
            require_api_key=False,
        )

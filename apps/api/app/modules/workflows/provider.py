from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings
from app.modules.workflows.compiler import compile_definition
from app.modules.workflows.definition import validate_definition
from app.modules.workflows.services.n8n_client import (
    N8nClient,
    N8nClientError,
    N8nUnavailableError,
)


class WorkflowProviderError(RuntimeError):
    pass


class WorkflowProviderUnavailable(WorkflowProviderError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderWorkflowReference:
    workflow_id: str
    version_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderExecutionResult:
    output: dict[str, Any]
    execution_id: str | None = None


class WorkflowProvider(Protocol):
    key: str

    @property
    def configured(self) -> bool: ...

    @property
    def supports_remote_cancellation(self) -> bool: ...

    async def test_connection(self) -> None: ...

    async def sync_workflow(
        self,
        *,
        external_workflow_id: str | None,
        name: str,
        definition: dict[str, Any],
        internal_webhook_path: str,
    ) -> ProviderWorkflowReference: ...

    async def activate_workflow(self, workflow_id: str) -> ProviderWorkflowReference: ...

    async def deactivate_workflow(self, workflow_id: str) -> None: ...

    async def trigger_workflow(
        self, webhook_path: str, payload: dict[str, Any]
    ) -> ProviderExecutionResult: ...

    async def cancel_execution(self, execution_id: str) -> bool: ...


def _provider_error(exc: N8nClientError) -> WorkflowProviderError:
    if isinstance(exc, N8nUnavailableError):
        return WorkflowProviderUnavailable(str(exc))
    return WorkflowProviderError(str(exc))


class N8nWorkflowProvider:
    key = "n8n"

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.n8n_enabled
        self._client = N8nClient(settings)

    @property
    def configured(self) -> bool:
        return self._enabled and self._client.configured

    @property
    def supports_remote_cancellation(self) -> bool:
        return self._client.supports_remote_cancellation

    async def test_connection(self) -> None:
        try:
            await self._client.test_connection()
        except N8nClientError as exc:
            raise _provider_error(exc) from exc

    async def sync_workflow(
        self,
        *,
        external_workflow_id: str | None,
        name: str,
        definition: dict[str, Any],
        internal_webhook_path: str,
    ) -> ProviderWorkflowReference:
        compiled = compile_definition(definition, internal_webhook_path=internal_webhook_path)
        try:
            if external_workflow_id:
                result = await self._client.update_workflow_with_rollback(
                    external_workflow_id, name, compiled
                )
                provider_id = external_workflow_id
            else:
                result = await self._client.create_workflow(name, compiled)
                provider_id = str(result.get("id") or "")
        except N8nClientError as exc:
            raise _provider_error(exc) from exc
        if not provider_id:
            raise WorkflowProviderError("O motor interno nao retornou a referencia do fluxo.")
        return ProviderWorkflowReference(
            workflow_id=provider_id,
            version_id=str(result.get("versionId") or "") or None,
        )

    async def activate_workflow(self, workflow_id: str) -> ProviderWorkflowReference:
        try:
            result = await self._client.activate_workflow(workflow_id)
        except N8nClientError as exc:
            raise _provider_error(exc) from exc
        return ProviderWorkflowReference(
            workflow_id=workflow_id,
            version_id=str(result.get("versionId") or "") or None,
        )

    async def deactivate_workflow(self, workflow_id: str) -> None:
        try:
            await self._client.deactivate_workflow(workflow_id)
        except N8nClientError as exc:
            raise _provider_error(exc) from exc

    async def trigger_workflow(
        self, webhook_path: str, payload: dict[str, Any]
    ) -> ProviderExecutionResult:
        try:
            output = await self._client.trigger_webhook(webhook_path, payload)
        except N8nClientError as exc:
            raise _provider_error(exc) from exc
        execution_id = str(output.get("executionId") or output.get("execution_id") or "") or None
        return ProviderExecutionResult(output=output, execution_id=execution_id)

    async def cancel_execution(self, execution_id: str) -> bool:
        try:
            return await self._client.cancel_execution(execution_id)
        except N8nClientError as exc:
            raise _provider_error(exc) from exc


class FakeWorkflowProvider:
    """Deterministic provider used to prove that the canonical engine is portable."""

    key = "fake"

    def __init__(self) -> None:
        self.workflows: dict[str, dict[str, Any]] = {}
        self.active: set[str] = set()
        self.canceled_executions: set[str] = set()
        self._sequence = 0

    @property
    def configured(self) -> bool:
        return True

    @property
    def supports_remote_cancellation(self) -> bool:
        return True

    async def test_connection(self) -> None:
        return None

    async def sync_workflow(
        self,
        *,
        external_workflow_id: str | None,
        name: str,
        definition: dict[str, Any],
        internal_webhook_path: str,
    ) -> ProviderWorkflowReference:
        validate_definition(definition)
        self._sequence += 1
        workflow_id = external_workflow_id or f"fake-workflow-{self._sequence}"
        self.workflows[workflow_id] = {
            "name": name,
            "definition": json.loads(json.dumps(definition)),
            "entrypoint_registered": bool(internal_webhook_path),
        }
        return ProviderWorkflowReference(workflow_id, f"fake-version-{self._sequence}")

    async def activate_workflow(self, workflow_id: str) -> ProviderWorkflowReference:
        if workflow_id not in self.workflows:
            raise WorkflowProviderError("Fluxo nao encontrado no provider de teste.")
        self.active.add(workflow_id)
        return ProviderWorkflowReference(workflow_id, "fake-active")

    async def deactivate_workflow(self, workflow_id: str) -> None:
        self.active.discard(workflow_id)

    async def trigger_workflow(
        self, webhook_path: str, payload: dict[str, Any]
    ) -> ProviderExecutionResult:
        self._sequence += 1
        return ProviderExecutionResult(
            output={"accepted": True, "provider": self.key, "entrypoint": bool(webhook_path)},
            execution_id=f"fake-execution-{self._sequence}",
        )

    async def cancel_execution(self, execution_id: str) -> bool:
        self.canceled_executions.add(execution_id)
        return True


def get_workflow_provider(settings: Settings) -> WorkflowProvider:
    return N8nWorkflowProvider(settings)

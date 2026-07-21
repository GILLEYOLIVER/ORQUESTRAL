from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol, runtime_checkable

FieldKind = Literal["text", "password", "url", "integer", "boolean"]


@dataclass(frozen=True, slots=True)
class PluginField:
    key: str
    label: str
    kind: FieldKind = "text"
    required: bool = True
    secret: bool = False
    placeholder: str | None = None
    default: str | int | bool | None = None


@dataclass(frozen=True, slots=True)
class PluginTool:
    code: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class PluginDefinition:
    code: str
    name: str
    version: str
    description: str
    authentication_type: str
    credential_fields: tuple[PluginField, ...] = ()
    configuration_fields: tuple[PluginField, ...] = ()
    tools: tuple[PluginTool, ...] = ()
    triggers: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    supports_token_refresh: bool = False
    supports_webhooks: bool = False

    def to_manifest(self) -> dict[str, Any]:
        return {
            "credential_fields": [asdict(field) for field in self.credential_fields],
            "configuration_fields": [asdict(field) for field in self.configuration_fields],
            "tools": [asdict(tool) for tool in self.tools],
            "triggers": list(self.triggers),
            "actions": list(self.actions),
            "supports_token_refresh": self.supports_token_refresh,
            "supports_webhooks": self.supports_webhooks,
        }


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    success: bool
    message: str


@runtime_checkable
class Plugin(Protocol):
    definition: PluginDefinition

    def validate_credentials(self, credentials: Mapping[str, Any]) -> None: ...

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult: ...

    async def execute(
        self,
        action: str,
        payload: Mapping[str, Any],
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...

    async def refresh_credentials(self, credentials: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def handle_webhook(
        self,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


class BasePlugin:
    definition: PluginDefinition

    def validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        from .exceptions import PluginValidationError

        missing = [
            field.label
            for field in self.definition.credential_fields
            if field.required and credentials.get(field.key) in (None, "")
        ]
        if missing:
            raise PluginValidationError(f"Campos obrigatórios ausentes: {', '.join(missing)}.")

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        from .exceptions import PluginExecutionError

        raise PluginExecutionError("Este plugin não implementa teste de conexão.")

    async def execute(
        self,
        action: str,
        payload: Mapping[str, Any],
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        from .exceptions import PluginExecutionError

        raise PluginExecutionError(f"A ação {action} não é suportada por este plugin.")

    async def refresh_credentials(self, credentials: Mapping[str, Any]) -> Mapping[str, Any]:
        from .exceptions import PluginExecutionError

        raise PluginExecutionError("Este plugin não implementa renovação de token.")

    async def handle_webhook(
        self,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        from .exceptions import PluginExecutionError

        raise PluginExecutionError("Este plugin não implementa webhooks.")

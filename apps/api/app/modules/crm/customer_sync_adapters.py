from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AdapterHealthStatus = Literal["ready", "unverified", "degraded", "blocked"]


@dataclass(frozen=True, slots=True)
class SyncAdapterDefinition:
    key: str
    version: str
    name: str
    description: str
    transports: tuple[str, ...]
    requires_credential: bool
    supports_scheduled_dispatch: bool


@dataclass(frozen=True, slots=True)
class AdapterReadiness:
    status: AdapterHealthStatus
    error_code: str | None

    @property
    def can_dispatch(self) -> bool:
        return self.status == "ready"


_ADAPTERS = (
    SyncAdapterDefinition(
        key="secure_push",
        version="1.0.0",
        name="Envio seguro Orkestral",
        description="Recebe lotes autenticados pela API sem consultar uma origem externa.",
        transports=("push",),
        requires_credential=False,
        supports_scheduled_dispatch=False,
    ),
    SyncAdapterDefinition(
        key="generic_rest_pull",
        version="1.0.0",
        name="API REST governada",
        description="Agenda uma consulta REST por credencial testada no cofre de integrações.",
        transports=("pull",),
        requires_credential=True,
        supports_scheduled_dispatch=True,
    ),
    SyncAdapterDefinition(
        key="signed_webhook",
        version="1.0.0",
        name="Webhook assinado",
        description="Recebe eventos com credencial ativa e validação de assinatura.",
        transports=("webhook",),
        requires_credential=True,
        supports_scheduled_dispatch=False,
    ),
)


def list_sync_adapter_definitions() -> tuple[SyncAdapterDefinition, ...]:
    return _ADAPTERS


def get_sync_adapter_definition(key: str) -> SyncAdapterDefinition | None:
    return next((adapter for adapter in _ADAPTERS if adapter.key == key), None)


def evaluate_adapter_readiness(
    *,
    adapter_key: str,
    transport: str,
    credential_configured: bool,
    connection_test_success: bool | None,
) -> AdapterReadiness:
    adapter = get_sync_adapter_definition(adapter_key)
    if adapter is None:
        return AdapterReadiness("blocked", "ADAPTER_NOT_REGISTERED")
    if transport not in adapter.transports:
        return AdapterReadiness("blocked", "ADAPTER_TRANSPORT_MISMATCH")
    if adapter.requires_credential and not credential_configured:
        return AdapterReadiness("blocked", "CREDENTIAL_REQUIRED")
    if not adapter.requires_credential:
        return AdapterReadiness("ready", None)
    if connection_test_success is None:
        return AdapterReadiness("unverified", "CONNECTION_NOT_TESTED")
    if not connection_test_success:
        return AdapterReadiness("degraded", "CONNECTION_TEST_FAILED")
    return AdapterReadiness("ready", None)

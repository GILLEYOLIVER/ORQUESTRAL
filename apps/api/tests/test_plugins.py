from __future__ import annotations

import pytest
from orkestral_plugin_sdk import BasePlugin, PluginDefinition, PluginExecutionError, PluginRegistry

from app.modules.plugins.adapters import HttpAdapter, PluginAdapterError, get_plugin_adapter
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError, mask_credentials


def test_credential_vault_round_trip() -> None:
    vault = CredentialVault("testing-secret")
    values = {"token": "segredo", "port": 443}

    encrypted = vault.encrypt(values)

    assert encrypted != b"segredo"
    assert vault.decrypt(encrypted) == values


def test_credential_vault_rejects_wrong_key() -> None:
    encrypted = CredentialVault("first-key").encrypt({"token": "segredo"})

    with pytest.raises(CredentialVaultError):
        CredentialVault("second-key").decrypt(encrypted)


def test_mask_credentials_never_exposes_values() -> None:
    masked = mask_credentials({"token": "super-secret", "empty": ""})

    assert masked == {"token": "••••••••", "empty": ""}
    assert "super-secret" not in str(masked)


def test_adapter_registry() -> None:
    assert isinstance(get_plugin_adapter("rest_api"), HttpAdapter)
    assert get_plugin_adapter("generic_webhook").definition.code == "generic_webhook"

    with pytest.raises(PluginAdapterError):
        get_plugin_adapter("unknown")


@pytest.mark.asyncio
async def test_http_adapter_rejects_invalid_url() -> None:
    with pytest.raises(PluginAdapterError):
        await HttpAdapter().test_connection({"base_url": "ftp://example.com"})


def test_credential_vault_rotates_from_previous_key() -> None:
    encrypted = CredentialVault("old-key").encrypt({"token": "segredo"})

    rotated = CredentialVault("new-key,old-key").rotate(encrypted)

    assert CredentialVault("new-key").decrypt(rotated) == {"token": "segredo"}
    with pytest.raises(CredentialVaultError):
        CredentialVault("old-key").decrypt(rotated)


class ExplodingPlugin(BasePlugin):
    definition = PluginDefinition(
        code="exploding",
        name="Exploding",
        version="1.0.0",
        description="Plugin usado pelo teste de isolamento.",
        authentication_type="none",
    )

    async def test_connection(self, credentials, configuration=None):  # type: ignore[no-untyped-def]
        raise RuntimeError("segredo-interno")


@pytest.mark.asyncio
async def test_plugin_registry_isolates_unexpected_failures() -> None:
    registry = PluginRegistry()
    registry.register(ExplodingPlugin())

    with pytest.raises(PluginExecutionError, match="forma isolada") as error:
        await registry.test_connection("exploding", {})

    assert "segredo-interno" not in str(error.value)

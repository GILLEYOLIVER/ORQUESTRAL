from __future__ import annotations

import pytest
from orkestral_plugin_sdk import BasePlugin, PluginDefinition, PluginExecutionError, PluginRegistry

from app.modules.plugins.adapters import (
    HttpAdapter,
    ManagedVaultAdapter,
    PluginAdapterError,
    get_plugin_adapter,
)
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError, mask_credentials
from app.modules.plugins.managed_vault import (
    ManagedVaultResolutionError,
    ManagedVaultSecretResolver,
)


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


@pytest.mark.parametrize(
    ("plugin_code", "reference"),
    [
        ("aws_secrets_manager", "aws-sm://sa-east-1/orkestral/active"),
        ("azure_key_vault", "azure-kv://orkestral-vault/active"),
        ("google_secret_manager", "gcp-sm://project/secrets/active"),
        ("hashicorp_vault", "vault://orkestral/active"),
    ],
)
def test_managed_vault_adapters_validate_protected_references(
    plugin_code: str, reference: str
) -> None:
    adapter = get_plugin_adapter(plugin_code)
    assert isinstance(adapter, ManagedVaultAdapter)
    adapter.validate_credentials({"key_reference": reference})
    with pytest.raises(PluginAdapterError, match="sem segredo embutido"):
        adapter.validate_credentials({"key_reference": f"{reference}?token=segredo"})


@pytest.mark.asyncio
async def test_managed_vault_test_requires_real_remote_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def resolve(
        self: ManagedVaultSecretResolver,
        reference: str,
        *,
        identity_reference: str | None = None,
    ) -> str:
        assert reference == "aws-sm://sa-east-1/orkestral/active"
        assert identity_reference is None
        return "resolved-secret-that-never-leaves-the-adapter"

    monkeypatch.setattr(ManagedVaultSecretResolver, "resolve", resolve)
    result = await get_plugin_adapter("aws_secrets_manager").test_connection(
        {"key_reference": "aws-sm://sa-east-1/orkestral/active"}
    )
    assert result.success is True
    assert "resolved-secret" not in result.message


@pytest.mark.asyncio
async def test_managed_vault_test_masks_provider_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(
        self: ManagedVaultSecretResolver,
        reference: str,
        *,
        identity_reference: str | None = None,
    ) -> str:
        raise ManagedVaultResolutionError("provider-secret-response")

    monkeypatch.setattr(ManagedVaultSecretResolver, "resolve", fail)
    with pytest.raises(PluginAdapterError) as error:
        await get_plugin_adapter("aws_secrets_manager").test_connection(
            {"key_reference": "aws-sm://sa-east-1/orkestral/active"}
        )
    assert "provider-secret-response" not in str(error.value)


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

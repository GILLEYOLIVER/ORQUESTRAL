from __future__ import annotations

import pytest

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
    assert isinstance(get_plugin_adapter("api-rest"), HttpAdapter)
    assert isinstance(get_plugin_adapter("webhook"), HttpAdapter)

    with pytest.raises(PluginAdapterError):
        get_plugin_adapter("unknown")


@pytest.mark.asyncio
async def test_http_adapter_rejects_invalid_url() -> None:
    with pytest.raises(PluginAdapterError):
        await HttpAdapter().test_connection({"url": "ftp://example.com"})

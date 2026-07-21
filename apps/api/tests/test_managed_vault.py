from __future__ import annotations

import base64

import httpx
import pytest

from app.modules.plugins.managed_vault import (
    ManagedVaultResolutionError,
    ManagedVaultSecretResolver,
    parse_managed_vault_reference,
)

SECRET = "managed-vault-secret-material-with-32-chars"


def test_managed_vault_references_are_strict() -> None:
    assert parse_managed_vault_reference("aws-sm://sa-east-1/orkestral/active").provider == "aws"
    assert parse_managed_vault_reference("azure-kv://orkestral-vault/active").provider == "azure"
    assert parse_managed_vault_reference("gcp-sm://project/secrets/active").version == "latest"
    assert parse_managed_vault_reference("vault://secret/orkestral/active").provider == "vault"
    for invalid in (
        "https://vault.example/secret",
        "aws-sm://sa-east-1/../secret",
        "azure-kv://vault/secret?token=hidden",
        "gcp-sm://project/invalid/secret",
    ):
        with pytest.raises(ManagedVaultResolutionError):
            parse_managed_vault_reference(invalid)


@pytest.mark.asyncio
async def test_aws_workload_identity_resolves_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "169.254.170.2":
            return httpx.Response(
                200,
                json={
                    "AccessKeyId": "AKIATEST",
                    "SecretAccessKey": "workload-secret",
                    "Token": "session-token",
                },
            )
        assert request.url.host == "secretsmanager.sa-east-1.amazonaws.com"
        assert request.headers["Authorization"].startswith("AWS4-HMAC-SHA256")
        return httpx.Response(200, json={"SecretString": SECRET})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolver = ManagedVaultSecretResolver(
            client=client,
            environment={"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials"},
        )
        assert await resolver.resolve("aws-sm://sa-east-1/orkestral/active") == SECRET


@pytest.mark.asyncio
async def test_azure_workload_identity_resolves_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "169.254.169.254":
            assert request.headers["Metadata"] == "true"
            return httpx.Response(200, json={"access_token": "ephemeral-token"})
        assert request.url.host == "orkestral-vault.vault.azure.net"
        assert request.headers["Authorization"] == "Bearer ephemeral-token"
        return httpx.Response(200, json={"value": SECRET})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolver = ManagedVaultSecretResolver(client=client, environment={})
        assert await resolver.resolve("azure-kv://orkestral-vault/active") == SECRET


@pytest.mark.asyncio
async def test_gcp_workload_identity_resolves_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "metadata.google.internal":
            assert request.headers["Metadata-Flavor"] == "Google"
            return httpx.Response(200, json={"access_token": "ephemeral-token"})
        assert request.url.host == "secretmanager.googleapis.com"
        return httpx.Response(
            200,
            json={"payload": {"data": base64.b64encode(SECRET.encode()).decode()}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolver = ManagedVaultSecretResolver(client=client, environment={})
        assert await resolver.resolve("gcp-sm://project/secrets/active") == SECRET


@pytest.mark.asyncio
async def test_vault_kubernetes_identity_resolves_secret(tmp_path) -> None:  # type: ignore[no-untyped-def]
    token_file = tmp_path / "service-account-token"
    token_file.write_text("signed-workload-token", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/kubernetes/login"):
            return httpx.Response(200, json={"auth": {"client_token": "ephemeral-token"}})
        assert request.headers["X-Vault-Token"] == "ephemeral-token"
        return httpx.Response(200, json={"data": {"data": {"value": SECRET}}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolver = ManagedVaultSecretResolver(
            client=client,
            environment={
                "VAULT_ADDR": "https://vault.internal",
                "VAULT_ROLE": "orkestral-api",
                "VAULT_KUBERNETES_TOKEN_FILE": str(token_file),
            },
        )
        assert await resolver.resolve("vault://secret/orkestral/active") == SECRET


@pytest.mark.asyncio
async def test_managed_vault_rejects_duplicate_key_material() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "metadata.google.internal":
            return httpx.Response(200, json={"access_token": "ephemeral-token"})
        return httpx.Response(
            200,
            json={"payload": {"data": base64.b64encode(SECRET.encode()).decode()}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolver = ManagedVaultSecretResolver(client=client, environment={})
        with pytest.raises(ManagedVaultResolutionError, match="chaves duplicadas"):
            await resolver.resolve_keyring(
                (
                    "gcp-sm://project/secrets/active",
                    "gcp-sm://project/secrets/previous",
                )
            )

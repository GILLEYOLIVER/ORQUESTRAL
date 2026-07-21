from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import quote, urlparse

import httpx

ManagedVaultProvider = Literal["aws", "azure", "gcp", "vault"]


class ManagedVaultResolutionError(RuntimeError):
    """Safe external-vault failure that never carries provider response bodies."""


@dataclass(frozen=True, slots=True)
class ManagedVaultReference:
    provider: ManagedVaultProvider
    location: str
    secret_name: str
    version: str | None = None


def parse_managed_vault_reference(reference: str) -> ManagedVaultReference:
    if reference != reference.strip() or len(reference) > 512:
        raise ManagedVaultResolutionError("Referência de cofre inválida.")
    if any(character.isspace() for character in reference) or any(
        character in reference for character in ("?", "#", "@")
    ):
        raise ManagedVaultResolutionError("Referência de cofre inválida.")

    if reference.startswith("aws-sm://"):
        parts = _safe_parts(reference.removeprefix("aws-sm://"))
        if len(parts) < 2 or not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", parts[0]):
            raise ManagedVaultResolutionError("Referência AWS inválida.")
        return ManagedVaultReference("aws", parts[0], "/".join(parts[1:]))

    if reference.startswith("azure-kv://"):
        parts = _safe_parts(reference.removeprefix("azure-kv://"))
        if len(parts) not in (2, 3) or not re.fullmatch(r"[A-Za-z0-9-]{3,24}", parts[0]):
            raise ManagedVaultResolutionError("Referência Azure inválida.")
        return ManagedVaultReference(
            "azure", parts[0], parts[1], parts[2] if len(parts) == 3 else None
        )

    if reference.startswith("gcp-sm://"):
        parts = _safe_parts(reference.removeprefix("gcp-sm://"))
        if len(parts) not in (3, 5) or parts[1] != "secrets":
            raise ManagedVaultResolutionError("Referência GCP inválida.")
        if len(parts) == 5 and parts[3] != "versions":
            raise ManagedVaultResolutionError("Versão GCP inválida.")
        return ManagedVaultReference(
            "gcp", parts[0], parts[2], parts[4] if len(parts) == 5 else "latest"
        )

    if reference.startswith("vault://"):
        parts = _safe_parts(reference.removeprefix("vault://"))
        if len(parts) < 2:
            raise ManagedVaultResolutionError("Referência HashiCorp Vault inválida.")
        return ManagedVaultReference("vault", parts[0], "/".join(parts[1:]))

    raise ManagedVaultResolutionError("Provedor de cofre não suportado.")


def _safe_parts(value: str) -> list[str]:
    parts = value.split("/")
    if not parts or any(not part or part in (".", "..") for part in parts):
        raise ManagedVaultResolutionError("Referência de cofre inválida.")
    if any(not re.fullmatch(r"[A-Za-z0-9._+=,:@-]+", part) for part in parts):
        raise ManagedVaultResolutionError("Referência de cofre inválida.")
    return parts


class ManagedVaultSecretResolver:
    """Resolves secret material only through workload-identity endpoints."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._environment = dict(environment if environment is not None else os.environ)

    async def resolve(self, reference: str, *, identity_reference: str | None = None) -> str:
        if self._client is None:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
                return await ManagedVaultSecretResolver(
                    client=client, environment=self._environment
                ).resolve(reference, identity_reference=identity_reference)
        parsed = parse_managed_vault_reference(reference)
        try:
            if parsed.provider == "aws":
                value = await self._resolve_aws(parsed)
            elif parsed.provider == "azure":
                value = await self._resolve_azure(parsed, identity_reference)
            elif parsed.provider == "gcp":
                value = await self._resolve_gcp(parsed, identity_reference)
            else:
                value = await self._resolve_vault(parsed, identity_reference)
        except ManagedVaultResolutionError:
            raise
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
            raise ManagedVaultResolutionError(
                "A identidade gerenciada não conseguiu resolver a referência do cofre."
            ) from exc
        if not value or len(value) < 32 or len(value) > 16_384:
            raise ManagedVaultResolutionError("O material protegido retornado é inválido.")
        return value

    async def resolve_keyring(
        self, references: Sequence[str], *, identity_reference: str | None = None
    ) -> tuple[str, ...]:
        if not references or len(set(references)) != len(references):
            raise ManagedVaultResolutionError("O keyring externo possui referências inválidas.")
        if self._client is None:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
                return await ManagedVaultSecretResolver(
                    client=client, environment=self._environment
                ).resolve_keyring(references, identity_reference=identity_reference)
        values = tuple(
            [
                await self.resolve(reference, identity_reference=identity_reference)
                for reference in references
            ]
        )
        if len(set(values)) != len(values):
            raise ManagedVaultResolutionError("O cofre retornou chaves duplicadas.")
        return values

    async def _resolve_aws(self, reference: ManagedVaultReference) -> str:
        credentials = await self._aws_credentials()
        access_key = _required_text(credentials, "AccessKeyId")
        secret_key = _required_text(credentials, "SecretAccessKey")
        session_token = _required_text(credentials, "Token")
        host = f"secretsmanager.{reference.location}.amazonaws.com"
        payload = json.dumps({"SecretId": reference.secret_name}, separators=(",", ":")).encode()
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        headers = {
            "content-type": "application/x-amz-json-1.1",
            "host": host,
            "x-amz-date": amz_date,
            "x-amz-security-token": session_token,
            "x-amz-target": "secretsmanager.GetSecretValue",
        }
        signed_header_names = sorted(headers)
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in signed_header_names)
        signed_headers = ";".join(signed_header_names)
        payload_hash = hashlib.sha256(payload).hexdigest()
        canonical_request = "\n".join(
            ["POST", "/", "", canonical_headers, signed_headers, payload_hash]
        )
        scope = f"{date_stamp}/{reference.location}/secretsmanager/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        signing_key = _aws_signing_key(secret_key, date_stamp, reference.location)
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        payload_json = await self._json(
            "POST", f"https://{host}/", headers=headers, content=payload
        )
        if isinstance(payload_json.get("SecretString"), str):
            return cast(str, payload_json["SecretString"])
        encoded = _required_text(payload_json, "SecretBinary")
        return base64.b64decode(encoded, validate=True).decode()

    async def _aws_credentials(self) -> Mapping[str, Any]:
        relative_uri = self._environment.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        full_uri = self._environment.get("AWS_CONTAINER_CREDENTIALS_FULL_URI")
        headers: dict[str, str] = {}
        authorization = self._environment.get("AWS_CONTAINER_AUTHORIZATION_TOKEN")
        if authorization:
            headers["Authorization"] = authorization
        if relative_uri:
            if not relative_uri.startswith("/") or ".." in relative_uri:
                raise ManagedVaultResolutionError("Endpoint de identidade AWS inválido.")
            return await self._json("GET", f"http://169.254.170.2{relative_uri}", headers=headers)
        if full_uri:
            parsed = urlparse(full_uri)
            if parsed.scheme != "http" or parsed.hostname not in {
                "169.254.170.2",
                "169.254.170.23",
            }:
                raise ManagedVaultResolutionError("Endpoint de identidade AWS inválido.")
            return await self._json("GET", full_uri, headers=headers)

        token_response = await self._request(
            "PUT",
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        )
        token = token_response.text.strip()
        role_response = await self._request(
            "GET",
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            headers={"X-aws-ec2-metadata-token": token},
        )
        role = role_response.text.strip()
        if not re.fullmatch(r"[A-Za-z0-9+=,.@_-]{1,128}", role):
            raise ManagedVaultResolutionError("Papel da identidade AWS inválido.")
        return await self._json(
            "GET",
            f"http://169.254.169.254/latest/meta-data/iam/security-credentials/{quote(role)}",
            headers={"X-aws-ec2-metadata-token": token},
        )

    async def _resolve_azure(
        self, reference: ManagedVaultReference, identity_reference: str | None
    ) -> str:
        endpoint = self._environment.get(
            "IDENTITY_ENDPOINT", "http://169.254.169.254/metadata/identity/oauth2/token"
        )
        parsed_endpoint = urlparse(endpoint)
        if parsed_endpoint.scheme != "http" or parsed_endpoint.hostname not in {
            "169.254.169.254",
            "169.254.129.1",
        }:
            raise ManagedVaultResolutionError("Endpoint de identidade Azure inválido.")
        headers = {"Metadata": "true"}
        identity_header = self._environment.get("IDENTITY_HEADER")
        if identity_header:
            headers["X-IDENTITY-HEADER"] = identity_header
        params = {"api-version": "2018-02-01", "resource": "https://vault.azure.net"}
        if identity_reference:
            params["client_id"] = identity_reference
        token_payload = await self._json("GET", endpoint, headers=headers, params=params)
        token = _required_text(token_payload, "access_token")
        version_path = f"/{quote(reference.version)}" if reference.version else ""
        secret_payload = await self._json(
            "GET",
            f"https://{reference.location}.vault.azure.net/secrets/"
            f"{quote(reference.secret_name)}{version_path}",
            headers={"Authorization": f"Bearer {token}"},
            params={"api-version": "7.4"},
        )
        return _required_text(secret_payload, "value")

    async def _resolve_gcp(
        self, reference: ManagedVaultReference, identity_reference: str | None
    ) -> str:
        service_account = identity_reference or "default"
        if not re.fullmatch(r"[A-Za-z0-9._@-]{1,254}", service_account):
            raise ManagedVaultResolutionError("Identidade GCP inválida.")
        token_payload = await self._json(
            "GET",
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/"
            f"{quote(service_account, safe='@')}/token",
            headers={"Metadata-Flavor": "Google"},
        )
        token = _required_text(token_payload, "access_token")
        secret_payload = await self._json(
            "GET",
            "https://secretmanager.googleapis.com/v1/projects/"
            f"{quote(reference.location)}/secrets/{quote(reference.secret_name)}/versions/"
            f"{quote(reference.version or 'latest')}:access",
            headers={"Authorization": f"Bearer {token}"},
        )
        payload = secret_payload.get("payload")
        if not isinstance(payload, Mapping):
            raise ManagedVaultResolutionError("Resposta protegida GCP inválida.")
        return base64.b64decode(_required_text(payload, "data"), validate=True).decode()

    async def _resolve_vault(
        self, reference: ManagedVaultReference, identity_reference: str | None
    ) -> str:
        address = self._environment.get("VAULT_ADDR", "")
        parsed_address = urlparse(address)
        if parsed_address.scheme != "https" or not parsed_address.hostname:
            raise ManagedVaultResolutionError("VAULT_ADDR deve usar HTTPS.")
        role = identity_reference or self._environment.get("VAULT_ROLE", "")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", role):
            raise ManagedVaultResolutionError("Papel do HashiCorp Vault inválido.")
        token_file = Path(
            self._environment.get(
                "VAULT_KUBERNETES_TOKEN_FILE",
                "/var/run/secrets/kubernetes.io/serviceaccount/token",
            )
        )
        jwt = (await asyncio.to_thread(token_file.read_text, encoding="utf-8")).strip()
        if not jwt or len(jwt) > 16_384:
            raise ManagedVaultResolutionError("Token da carga de trabalho inválido.")
        auth_path = self._environment.get("VAULT_KUBERNETES_AUTH_PATH", "auth/kubernetes/login")
        auth_parts = _safe_parts(auth_path.strip("/"))
        login_payload = await self._json(
            "POST",
            f"{address.rstrip('/')}/v1/{'/'.join(auth_parts)}",
            json_body={"role": role, "jwt": jwt},
        )
        auth = login_payload.get("auth")
        if not isinstance(auth, Mapping):
            raise ManagedVaultResolutionError("Autenticação do HashiCorp Vault inválida.")
        client_token = _required_text(auth, "client_token")
        secret_payload = await self._json(
            "GET",
            f"{address.rstrip('/')}/v1/{quote(reference.location)}/"
            f"{quote(reference.secret_name, safe='/')}",
            headers={"X-Vault-Token": client_token},
        )
        data = secret_payload.get("data")
        if not isinstance(data, Mapping):
            raise ManagedVaultResolutionError("Resposta protegida do HashiCorp Vault inválida.")
        nested = data.get("data")
        values = nested if isinstance(nested, Mapping) else data
        return _required_text(values, "value")

    async def _json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        content: bytes | None = None,
        json_body: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._request(
            method,
            url,
            headers=headers,
            params=params,
            content=content,
            json=json_body,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ManagedVaultResolutionError("Resposta do cofre inválida.") from exc
        if not isinstance(payload, dict):
            raise ManagedVaultResolutionError("Resposta do cofre inválida.")
        return cast(dict[str, Any], payload)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:  # pragma: no cover - protected by resolve
            raise ManagedVaultResolutionError("Cliente do cofre indisponível.")
        response = await self._client.request(method, url, **kwargs)
        if len(response.content) > 65_536:
            raise ManagedVaultResolutionError("Resposta do cofre excedeu o limite seguro.")
        if response.status_code < 200 or response.status_code >= 300:
            raise ManagedVaultResolutionError("O provedor recusou a identidade gerenciada.")
        return response


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ManagedVaultResolutionError("Resposta do cofre incompleta.")
    return value


def _aws_signing_key(secret: str, date_stamp: str, region: str) -> bytes:
    date_key = hmac.new(f"AWS4{secret}".encode(), date_stamp.encode(), hashlib.sha256).digest()
    region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"secretsmanager", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class MarketplaceContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PackageContract:
    plugin_code: str
    version: str
    manifest: dict[str, Any]
    artifact_digest: str
    min_platform_version: str
    max_platform_version: str | None
    requested_permissions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PackageContract:
        try:
            return cls(
                plugin_code=str(value["plugin_code"]),
                version=str(value["version"]),
                manifest=dict(value["manifest"]),
                artifact_digest=str(value["artifact_digest"]),
                min_platform_version=str(value["min_platform_version"]),
                max_platform_version=(
                    str(value["max_platform_version"])
                    if value.get("max_platform_version") is not None
                    else None
                ),
                requested_permissions=[
                    str(item) for item in value.get("requested_permissions", [])
                ],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MarketplaceContractError("Contrato de pacote inválido.") from error


def _decode_base64(value: str, label: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise MarketplaceContractError(f"{label} não possui Base64 válido.") from error


def _semver(value: str) -> tuple[int, int, int]:
    parts = value.split("-", 1)[0].split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise MarketplaceContractError(f"Versão semântica inválida: {value}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def is_version_supported(
    platform_version: str, minimum: str, maximum: str | None
) -> bool:
    current = _semver(platform_version)
    return current >= _semver(minimum) and (maximum is None or current <= _semver(maximum))


def canonical_package_payload(contract: PackageContract) -> bytes:
    payload = contract.to_dict()
    payload["requested_permissions"] = sorted(set(contract.requested_permissions))
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


def generate_signing_keypair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        base64.b64encode(private_bytes).decode(),
        base64.b64encode(public_bytes).decode(),
    )


def publisher_fingerprint(public_key: str) -> str:
    key = _decode_base64(public_key, "Chave pública")
    if len(key) != 32:
        raise MarketplaceContractError("Chave pública Ed25519 deve possuir 32 bytes.")
    return hashlib.sha256(key).hexdigest()


def sign_package_contract(private_key: str, contract: PackageContract) -> str:
    key = _decode_base64(private_key, "Chave privada")
    if len(key) != 32:
        raise MarketplaceContractError("Chave privada Ed25519 deve possuir 32 bytes.")
    signature = Ed25519PrivateKey.from_private_bytes(key).sign(
        canonical_package_payload(contract)
    )
    return base64.b64encode(signature).decode()


def validate_package_signature(
    public_key: str, signature: str, contract: PackageContract
) -> None:
    key = _decode_base64(public_key, "Chave pública")
    signature_bytes = _decode_base64(signature, "Assinatura")
    if len(key) != 32 or len(signature_bytes) != 64:
        raise MarketplaceContractError("Contrato Ed25519 inválido.")
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(
            signature_bytes, canonical_package_payload(contract)
        )
    except InvalidSignature as error:
        raise MarketplaceContractError("Assinatura do pacote inválida.") from error

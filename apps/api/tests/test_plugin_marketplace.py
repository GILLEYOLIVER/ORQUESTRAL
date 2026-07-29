from __future__ import annotations

import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.plugins.marketplace import (
    MarketplaceContractError,
    PackageContract,
    canonical_package_payload,
    is_version_supported,
    publisher_fingerprint,
    validate_package_signature,
)


def _signed_contract() -> tuple[str, str, PackageContract]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    contract = PackageContract(
        plugin_code="crm.connector",
        version="1.2.0",
        manifest={"dependencies": []},
        artifact_digest=hashlib.sha256(b"artifact").hexdigest(),
        min_platform_version="0.12.0",
        max_platform_version="1.0.0",
        requested_permissions=["plugins.view"],
    )
    signature = private_key.sign(canonical_package_payload(contract))
    return (
        base64.b64encode(public_key).decode(),
        base64.b64encode(signature).decode(),
        contract,
    )


def test_ed25519_package_contract_and_fingerprint() -> None:
    public_key, signature, contract = _signed_contract()
    validate_package_signature(public_key, signature, contract)
    assert len(publisher_fingerprint(public_key)) == 64


def test_package_signature_rejects_tampering_and_unknown_permissions() -> None:
    public_key, signature, contract = _signed_contract()
    tampered = PackageContract(
        plugin_code=contract.plugin_code,
        version="9.9.9",
        manifest=contract.manifest,
        artifact_digest=contract.artifact_digest,
        min_platform_version=contract.min_platform_version,
        max_platform_version=contract.max_platform_version,
        requested_permissions=contract.requested_permissions,
    )
    with pytest.raises(MarketplaceContractError, match="Assinatura"):
        validate_package_signature(public_key, signature, tampered)
    unknown_permission = PackageContract(
        plugin_code=contract.plugin_code,
        version=contract.version,
        manifest=contract.manifest,
        artifact_digest=contract.artifact_digest,
        min_platform_version=contract.min_platform_version,
        max_platform_version=contract.max_platform_version,
        requested_permissions=["root.everything"],
    )
    with pytest.raises(MarketplaceContractError, match="Permissões desconhecidas"):
        validate_package_signature(public_key, signature, unknown_permission)


def test_platform_compatibility_is_bounded() -> None:
    assert is_version_supported("0.13.0", "0.12.0", "0.14.0")
    assert not is_version_supported("0.13.0", "0.14.0", None)
    assert not is_version_supported("0.13.0", "0.1.0", "0.12.9")

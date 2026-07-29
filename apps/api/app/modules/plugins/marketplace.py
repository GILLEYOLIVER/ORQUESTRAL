from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select

from app.core.security import utc_now
from app.core.tenancy import RequestContext
from app.modules.authorization.catalog import PERMISSION_CATALOG
from app.modules.authorization.service import record_authorization_audit
from app.modules.plugins.models import (
    CompanyPlugin,
    CompanyPluginInstallation,
    Plugin,
    PluginPackageVersion,
    PluginPublisher,
)
from app.modules.plugins.schemas import PluginInstallationResponse


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
    payload = {
        "artifact_digest": contract.artifact_digest,
        "manifest": contract.manifest,
        "max_platform_version": contract.max_platform_version,
        "min_platform_version": contract.min_platform_version,
        "plugin_code": contract.plugin_code,
        "requested_permissions": sorted(set(contract.requested_permissions)),
        "version": contract.version,
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


def _decode_base64(value: str, label: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise MarketplaceContractError(f"{label} não possui Base64 válido.") from error


def publisher_fingerprint(public_key: str) -> str:
    key = _decode_base64(public_key, "Chave pública")
    if len(key) != 32:
        raise MarketplaceContractError("Chave pública Ed25519 deve possuir 32 bytes.")
    return hashlib.sha256(key).hexdigest()


def validate_package_signature(
    public_key: str, signature: str, contract: PackageContract
) -> None:
    key = _decode_base64(public_key, "Chave pública")
    signature_bytes = _decode_base64(signature, "Assinatura")
    if len(key) != 32 or len(signature_bytes) != 64:
        raise MarketplaceContractError("Contrato Ed25519 inválido.")
    known_permissions = {item.code for item in PERMISSION_CATALOG}
    unknown = sorted(set(contract.requested_permissions) - known_permissions)
    if unknown:
        raise MarketplaceContractError(
            f"Permissões desconhecidas no pacote: {', '.join(unknown)}"
        )
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(
            signature_bytes, canonical_package_payload(contract)
        )
    except InvalidSignature as error:
        raise MarketplaceContractError("Assinatura do pacote inválida.") from error


def _response(
    installation: CompanyPluginInstallation,
    plugin_code: str,
    version: str,
    previous_version: str | None,
) -> PluginInstallationResponse:
    return PluginInstallationResponse(
        id=installation.id,
        plugin_code=plugin_code,
        version=version,
        previous_version=previous_version,
        operation=installation.operation,
        status=installation.status,
        installed_at=installation.installed_at,
    )


async def _release(
    database: Any, plugin_code: str, version: str
) -> tuple[Plugin, PluginPackageVersion, PluginPublisher]:
    row = (
        await database.execute(
            select(Plugin, PluginPackageVersion, PluginPublisher)
            .join(PluginPackageVersion, PluginPackageVersion.plugin_id == Plugin.id)
            .join(PluginPublisher, PluginPublisher.id == PluginPackageVersion.publisher_id)
            .where(
                Plugin.code == plugin_code,
                PluginPackageVersion.version == version,
                PluginPackageVersion.status == "published",
                PluginPublisher.status == "trusted",
            )
        )
    ).one_or_none()
    if row is None:
        raise MarketplaceContractError("Versão publicada e confiável não encontrada.")
    return row[0], row[1], row[2]


def _contract(plugin: Plugin, release: PluginPackageVersion) -> PackageContract:
    return PackageContract(
        plugin_code=plugin.code,
        version=release.version,
        manifest=release.manifest,
        artifact_digest=release.artifact_digest,
        min_platform_version=release.min_platform_version,
        max_platform_version=release.max_platform_version,
        requested_permissions=release.requested_permissions,
    )


async def _validate_dependencies(
    database: Any, company_id: Any, manifest: dict[str, Any]
) -> None:
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise MarketplaceContractError("Dependências do manifesto devem ser uma lista.")
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise MarketplaceContractError("Dependência de pacote inválida.")
        code = dependency.get("code")
        minimum = dependency.get("min_version")
        if not isinstance(code, str) or not isinstance(minimum, str):
            raise MarketplaceContractError("Dependência deve informar code e min_version.")
        installed = (
            await database.execute(
                select(PluginPackageVersion.version)
                .join(CompanyPlugin, CompanyPlugin.installed_version_id == PluginPackageVersion.id)
                .join(Plugin, Plugin.id == CompanyPlugin.plugin_id)
                .where(
                    CompanyPlugin.company_id == company_id,
                    CompanyPlugin.status == "active",
                    Plugin.code == code,
                )
            )
        ).scalar_one_or_none()
        if installed is None or _semver(installed) < _semver(minimum):
            raise MarketplaceContractError(
                f"Dependência ausente ou incompatível: {code}>={minimum}"
            )


async def install_release(
    database: Any,
    *,
    context: RequestContext,
    plugin_code: str,
    version: str,
    platform_version: str,
    operation: str = "install",
) -> PluginInstallationResponse:
    plugin, release, publisher = await _release(database, plugin_code, version)
    validate_package_signature(publisher.public_key, release.signature, _contract(plugin, release))
    if not is_version_supported(
        platform_version, release.min_platform_version, release.max_platform_version
    ):
        raise MarketplaceContractError("Versão incompatível com esta versão do Orkestral.")
    await _validate_dependencies(database, context.company_id, release.manifest)
    company_plugin = await database.scalar(
        select(CompanyPlugin).where(
            CompanyPlugin.company_id == context.company_id,
            CompanyPlugin.plugin_id == plugin.id,
        )
    )
    if company_plugin is None:
        company_plugin = CompanyPlugin(company_id=context.company_id, plugin_id=plugin.id)
        database.add(company_plugin)
        await database.flush()
    current_release = None
    current_installation = None
    if company_plugin.installed_version_id is not None:
        current_release = await database.get(
            PluginPackageVersion, company_plugin.installed_version_id
        )
        current_installation = await database.scalar(
            select(CompanyPluginInstallation)
            .where(
                CompanyPluginInstallation.company_id == context.company_id,
                CompanyPluginInstallation.plugin_id == plugin.id,
                CompanyPluginInstallation.status == "installed",
            )
            .order_by(CompanyPluginInstallation.installed_at.desc())
        )
        if current_release is not None and current_release.id == release.id:
            if current_installation is None:
                raise MarketplaceContractError("Histórico da instalação está inconsistente.")
            return _response(
                current_installation, plugin.code, release.version, current_release.version
            )
    if current_installation is not None:
        current_installation.status = "replaced"
    installation = CompanyPluginInstallation(
        company_id=context.company_id,
        plugin_id=plugin.id,
        package_version_id=release.id,
        previous_version_id=current_release.id if current_release else None,
        status="installed",
        operation=operation,
        installed_by_user_id=context.user_id,
        installed_at=utc_now(),
    )
    database.add(installation)
    company_plugin.installed_version_id = release.id
    company_plugin.status = "active"
    company_plugin.activated_at = utc_now()
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"plugin.marketplace.{operation}",
        target_type="company_plugin_installation",
        target_id=installation.id,
        details={
            "plugin_code": plugin.code,
            "version": release.version,
            "previous_version": current_release.version if current_release else None,
            "publisher_fingerprint": publisher.key_fingerprint,
        },
    )
    await database.commit()
    await database.refresh(installation)
    return _response(
        installation,
        plugin.code,
        release.version,
        current_release.version if current_release else None,
    )


async def rollback_release(
    database: Any,
    *,
    context: RequestContext,
    plugin_code: str,
    platform_version: str,
) -> PluginInstallationResponse:
    plugin = await database.scalar(select(Plugin).where(Plugin.code == plugin_code))
    if plugin is None:
        raise MarketplaceContractError("Plugin não encontrado.")
    current = await database.scalar(
        select(CompanyPluginInstallation)
        .where(
            CompanyPluginInstallation.company_id == context.company_id,
            CompanyPluginInstallation.plugin_id == plugin.id,
            CompanyPluginInstallation.status == "installed",
        )
        .order_by(CompanyPluginInstallation.installed_at.desc())
    )
    if current is None or current.previous_version_id is None:
        raise MarketplaceContractError("Não existe versão anterior para rollback.")
    previous = await database.get(PluginPackageVersion, current.previous_version_id)
    if previous is None:
        raise MarketplaceContractError("Versão anterior não está mais disponível.")
    return await install_release(
        database,
        context=context,
        plugin_code=plugin_code,
        version=previous.version,
        platform_version=platform_version,
        operation="rollback",
    )

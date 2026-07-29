from __future__ import annotations

from time import perf_counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from orkestral_plugin_sdk import PluginSDKError
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import (
    Principal,
    get_request_context,
    require_permission,
    require_platform_admin,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.billing.service import UsageMetric, enforce_limit, record_usage
from app.modules.plugins.adapters import MANAGED_VAULT_PROVIDERS, get_plugin_runtime
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError, mask_credential_fields
from app.modules.plugins.marketplace import (
    MarketplaceContractError,
    PackageContract,
    install_release,
    publisher_fingerprint,
    rollback_release,
    validate_package_signature,
)
from app.modules.plugins.models import (
    CompanyPlugin,
    IntegrationCredential,
    Plugin,
    PluginConnectionTest,
    PluginPackageVersion,
    PluginPublisher,
)
from app.modules.plugins.schemas import (
    CompanyPluginUpdate,
    ConnectionTestHistoryResponse,
    ConnectionTestResponse,
    CredentialCreate,
    CredentialResponse,
    CredentialRotationResponse,
    ManagedVaultMetricResponse,
    PluginInstallationRequest,
    PluginInstallationResponse,
    PluginPackagePublish,
    PluginPackageVersionResponse,
    PluginPublisherCreate,
    PluginPublisherResponse,
    PluginResponse,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])
CanViewPlugins = Annotated[Principal, Depends(require_permission("plugins.view"))]
CanManagePlugins = Annotated[Principal, Depends(require_permission("plugins.manage"))]
PlatformAdmin = Annotated[Principal, Depends(require_platform_admin)]


def _plugin_response(plugin: Plugin, company_plugin: CompanyPlugin | None) -> PluginResponse:
    return PluginResponse(
        id=plugin.id,
        code=plugin.code,
        name=plugin.name,
        version=plugin.version,
        description=plugin.description,
        authentication_type=plugin.authentication_type,
        catalog_status=plugin.status,
        company_status=company_plugin.status if company_plugin else "inactive",
        configuration=company_plugin.configuration if company_plugin else {},
        manifest=plugin.manifest,
    )


def _credential_response(credential: IntegrationCredential) -> CredentialResponse:
    return CredentialResponse(
        id=credential.id,
        plugin_id=credential.plugin_id,
        name=credential.name,
        status=credential.status,
        masked_values=mask_credential_fields(credential.credential_fields),
        expires_at=credential.expires_at,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


async def _active_plugin(
    database: DatabaseSession, company_id: UUID, plugin_code: str
) -> tuple[Plugin, CompanyPlugin]:
    row = (
        await database.execute(
            select(Plugin, CompanyPlugin)
            .join(
                CompanyPlugin,
                and_(
                    CompanyPlugin.plugin_id == Plugin.id,
                    CompanyPlugin.company_id == company_id,
                    CompanyPlugin.status == "active",
                ),
            )
            .where(Plugin.code == plugin_code, Plugin.status == "installed")
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=409, detail="Ative o plugin antes de administrar credenciais."
        )
    return row[0], row[1]


@router.get("", response_model=list[PluginResponse])
async def list_plugins(
    principal: CanViewPlugins, database: DatabaseSession
) -> list[PluginResponse]:
    context = get_request_context(principal)
    rows = (
        await database.execute(
            select(Plugin, CompanyPlugin)
            .outerjoin(
                CompanyPlugin,
                and_(
                    CompanyPlugin.plugin_id == Plugin.id,
                    CompanyPlugin.company_id == context.company_id,
                ),
            )
            .order_by(Plugin.name)
        )
    ).all()
    return [_plugin_response(plugin, company_plugin) for plugin, company_plugin in rows]


@router.patch("/{plugin_code}", response_model=PluginResponse)
async def update_company_plugin(
    plugin_code: str,
    payload: CompanyPluginUpdate,
    principal: CanManagePlugins,
    database: DatabaseSession,
    settings: RequestSettings,
) -> PluginResponse:
    context = get_request_context(principal)
    plugin = await database.scalar(select(Plugin).where(Plugin.code == plugin_code))
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin não encontrado.")
    if plugin.status != "installed":
        raise HTTPException(status_code=409, detail="O plugin ainda não está instalado.")
    company_plugin = await database.scalar(
        select(CompanyPlugin).where(
            CompanyPlugin.company_id == context.company_id,
            CompanyPlugin.plugin_id == plugin.id,
        )
    )
    consumes_capacity = payload.status == "active" and (
        company_plugin is None or company_plugin.status != "active"
    )
    if consumes_capacity:
        await enforce_limit(
            database,
            company_id=context.company_id,
            metric=UsageMetric.INTEGRATIONS,
            enforcement_enabled=settings.billing_enforcement_enabled,
        )
    if company_plugin is None:
        company_plugin = CompanyPlugin(company_id=context.company_id, plugin_id=plugin.id)
        database.add(company_plugin)
    now = utc_now()
    company_plugin.status = payload.status
    if payload.configuration is not None:
        company_plugin.configuration = payload.configuration
    company_plugin.activated_at = now if payload.status == "active" else company_plugin.activated_at
    company_plugin.deactivated_at = now if payload.status == "inactive" else None
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"plugin.{payload.status}",
        target_type="plugin",
        target_id=plugin.id,
        details={"code": plugin.code},
    )
    if consumes_capacity:
        await record_usage(
            database,
            company_id=context.company_id,
            metric=UsageMetric.INTEGRATIONS,
            quantity=1,
            metadata={"plugin_id": str(plugin.id), "code": plugin.code},
            idempotency_key=f"plugin-activation:{company_plugin.id}:{now.isoformat()}",
        )
    await database.commit()
    await database.refresh(company_plugin)
    return _plugin_response(plugin, company_plugin)


@router.get("/{plugin_code}/credentials", response_model=list[CredentialResponse])
async def list_credentials(
    plugin_code: str,
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> list[CredentialResponse]:
    context = get_request_context(principal)
    plugin, _ = await _active_plugin(database, context.company_id, plugin_code)
    credentials = (
        await database.scalars(
            select(IntegrationCredential)
            .where(
                IntegrationCredential.company_id == context.company_id,
                IntegrationCredential.plugin_id == plugin.id,
            )
            .order_by(IntegrationCredential.created_at.desc())
        )
    ).all()
    return [_credential_response(credential) for credential in credentials]


@router.post("/{plugin_code}/credentials", response_model=CredentialResponse, status_code=201)
async def create_credential(
    plugin_code: str,
    payload: CredentialCreate,
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> CredentialResponse:
    context = get_request_context(principal)
    plugin, _ = await _active_plugin(database, context.company_id, plugin_code)
    try:
        get_plugin_runtime().get(plugin.code).validate_credentials(payload.values)
    except PluginSDKError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    credential = IntegrationCredential(
        company_id=context.company_id,
        plugin_id=plugin.id,
        name=payload.name,
        encrypted_credentials=CredentialVault(get_settings().encryption_key).encrypt(
            payload.values
        ),
        credential_fields=sorted(payload.values),
        expires_at=payload.expires_at,
    )
    database.add(credential)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="plugin.credential.created",
        target_type="integration_credential",
        target_id=credential.id,
        details={"plugin_code": plugin.code, "fields": credential.credential_fields},
    )
    await database.commit()
    await database.refresh(credential)
    return _credential_response(credential)


@router.delete("/{plugin_code}/credentials/{credential_id}", status_code=204)
async def revoke_credential(
    plugin_code: str,
    credential_id: UUID,
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> None:
    context = get_request_context(principal)
    plugin, _ = await _active_plugin(database, context.company_id, plugin_code)
    credential = await database.scalar(
        select(IntegrationCredential).where(
            IntegrationCredential.id == credential_id,
            IntegrationCredential.company_id == context.company_id,
            IntegrationCredential.plugin_id == plugin.id,
        )
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada.")
    credential.status = "revoked"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="plugin.credential.revoked",
        target_type="integration_credential",
        target_id=credential.id,
        details={"plugin_code": plugin.code},
    )
    await database.commit()


@router.post(
    "/{plugin_code}/credentials/{credential_id}/test", response_model=ConnectionTestResponse
)
async def test_credential(
    plugin_code: str,
    credential_id: UUID,
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> ConnectionTestResponse:
    context = get_request_context(principal)
    plugin, company_plugin = await _active_plugin(database, context.company_id, plugin_code)
    credential = await database.scalar(
        select(IntegrationCredential).where(
            IntegrationCredential.id == credential_id,
            IntegrationCredential.company_id == context.company_id,
            IntegrationCredential.plugin_id == plugin.id,
            IntegrationCredential.status == "active",
        )
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="Credencial ativa não encontrada.")

    started = perf_counter()
    success = False
    message = "Não foi possível validar a conexão."
    try:
        values = CredentialVault(get_settings().encryption_key).decrypt(
            credential.encrypted_credentials
        )
        result = await get_plugin_runtime().test_connection(
            plugin.code,
            values,
            company_plugin.configuration,
        )
        success = result.success
        message = result.message
    except (CredentialVaultError, PluginSDKError) as exc:
        message = str(exc)
    duration_ms = max(0, round((perf_counter() - started) * 1000))
    attempt = PluginConnectionTest(
        company_id=context.company_id,
        plugin_id=plugin.id,
        credential_id=credential.id,
        success=success,
        message=message[:500],
        duration_ms=duration_ms,
    )
    database.add(attempt)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="plugin.credential.tested",
        target_type="integration_credential",
        target_id=credential.id,
        details={"plugin_code": plugin.code, "success": success, "attempt_id": str(attempt.id)},
    )
    await database.commit()
    await database.refresh(attempt)
    return ConnectionTestResponse(
        test_id=attempt.id,
        success=attempt.success,
        message=attempt.message,
        duration_ms=attempt.duration_ms,
        tested_at=attempt.created_at,
    )


@router.get("/{plugin_code}/tests", response_model=list[ConnectionTestHistoryResponse])
async def list_connection_tests(
    plugin_code: str,
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> list[ConnectionTestHistoryResponse]:
    context = get_request_context(principal)
    plugin, _ = await _active_plugin(database, context.company_id, plugin_code)
    attempts = (
        await database.scalars(
            select(PluginConnectionTest)
            .where(
                PluginConnectionTest.company_id == context.company_id,
                PluginConnectionTest.plugin_id == plugin.id,
            )
            .order_by(PluginConnectionTest.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        ConnectionTestHistoryResponse(
            id=attempt.id,
            plugin_id=attempt.plugin_id,
            credential_id=attempt.credential_id,
            success=attempt.success,
            message=attempt.message,
            duration_ms=attempt.duration_ms,
            created_at=attempt.created_at,
        )
        for attempt in attempts
    ]


@router.post("/credentials/rotate", response_model=CredentialRotationResponse)
async def rotate_company_credentials(
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> CredentialRotationResponse:
    context = get_request_context(principal)
    credentials = (
        await database.scalars(
            select(IntegrationCredential).where(
                IntegrationCredential.company_id == context.company_id,
                IntegrationCredential.status == "active",
            )
        )
    ).all()
    vault = CredentialVault(get_settings().encryption_key)
    rotated = 0
    failed = 0
    for credential in credentials:
        try:
            credential.encrypted_credentials = vault.rotate(credential.encrypted_credentials)
            rotated += 1
        except CredentialVaultError:
            failed += 1
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="plugin.credentials.rotated",
        target_type="company",
        target_id=context.company_id,
        details={"rotated": rotated, "failed": failed},
    )
    await database.commit()
    return CredentialRotationResponse(rotated=rotated, failed=failed)


@router.get(
    "/managed-vault-metrics/summary",
    response_model=list[ManagedVaultMetricResponse],
)
async def get_managed_vault_metrics(
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> list[ManagedVaultMetricResponse]:
    context = get_request_context(principal)
    rows = (
        await database.execute(
            select(PluginConnectionTest, Plugin.code)
            .join(Plugin, Plugin.id == PluginConnectionTest.plugin_id)
            .where(
                PluginConnectionTest.company_id == context.company_id,
                Plugin.code.in_(tuple(MANAGED_VAULT_PROVIDERS)),
            )
            .order_by(PluginConnectionTest.created_at.desc())
            .limit(5_000)
        )
    ).all()
    grouped: dict[str, list[PluginConnectionTest]] = {}
    for attempt, plugin_code in rows:
        grouped.setdefault(str(plugin_code), []).append(attempt)
    metrics: list[ManagedVaultMetricResponse] = []
    for provider_code, attempts in sorted(grouped.items()):
        successes = sum(1 for attempt in attempts if attempt.success)
        total = len(attempts)
        metrics.append(
            ManagedVaultMetricResponse(
                provider_code=provider_code,
                provider_name=MANAGED_VAULT_PROVIDERS[provider_code][0],
                total_tests=total,
                successful_tests=successes,
                failed_tests=total - successes,
                success_rate=round(successes / total, 4),
                average_duration_ms=round(sum(attempt.duration_ms for attempt in attempts) / total),
                last_tested_at=attempts[0].created_at,
            )
        )
    return metrics


@router.post("/marketplace/publishers", response_model=PluginPublisherResponse, status_code=201)
async def create_marketplace_publisher(
    payload: PluginPublisherCreate,
    principal: PlatformAdmin,
    database: DatabaseSession,
) -> PluginPublisherResponse:
    context = get_request_context(principal)
    try:
        fingerprint = publisher_fingerprint(payload.public_key)
    except MarketplaceContractError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    publisher = PluginPublisher(
        code=payload.code,
        name=payload.name,
        public_key=payload.public_key,
        key_fingerprint=fingerprint,
    )
    database.add(publisher)
    try:
        await database.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Publicador já registrado.") from error
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="plugin.publisher.created",
        target_type="plugin_publisher",
        target_id=publisher.id,
        details={"code": publisher.code, "key_fingerprint": fingerprint},
    )
    await database.commit()
    await database.refresh(publisher)
    return PluginPublisherResponse.model_validate(publisher, from_attributes=True)


@router.post(
    "/{plugin_code}/marketplace/versions",
    response_model=PluginPackageVersionResponse,
    status_code=201,
)
async def publish_marketplace_version(
    plugin_code: str,
    payload: PluginPackagePublish,
    principal: PlatformAdmin,
    database: DatabaseSession,
) -> PluginPackageVersionResponse:
    context = get_request_context(principal)
    plugin = await database.scalar(select(Plugin).where(Plugin.code == plugin_code))
    publisher = await database.scalar(
        select(PluginPublisher).where(
            PluginPublisher.code == payload.publisher_code,
            PluginPublisher.status == "trusted",
        )
    )
    if plugin is None or publisher is None:
        raise HTTPException(status_code=404, detail="Plugin ou publicador confiável não encontrado.")
    contract = PackageContract(
        plugin_code=plugin.code,
        version=payload.version,
        manifest=payload.manifest,
        artifact_digest=payload.artifact_digest,
        min_platform_version=payload.min_platform_version,
        max_platform_version=payload.max_platform_version,
        requested_permissions=payload.requested_permissions,
    )
    try:
        validate_package_signature(publisher.public_key, payload.signature, contract)
    except MarketplaceContractError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    release = PluginPackageVersion(
        plugin_id=plugin.id,
        publisher_id=publisher.id,
        version=payload.version,
        manifest=payload.manifest,
        artifact_digest=payload.artifact_digest,
        signature=payload.signature,
        min_platform_version=payload.min_platform_version,
        max_platform_version=payload.max_platform_version,
        requested_permissions=sorted(set(payload.requested_permissions)),
    )
    database.add(release)
    try:
        await database.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Versão já publicada.") from error
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="plugin.package.published",
        target_type="plugin_package_version",
        target_id=release.id,
        details={
            "plugin_code": plugin.code,
            "version": release.version,
            "artifact_digest": release.artifact_digest,
            "publisher_fingerprint": publisher.key_fingerprint,
        },
    )
    await database.commit()
    await database.refresh(release)
    return _package_response(release, plugin, publisher)


def _package_response(
    release: PluginPackageVersion, plugin: Plugin, publisher: PluginPublisher
) -> PluginPackageVersionResponse:
    return PluginPackageVersionResponse(
        id=release.id,
        plugin_id=plugin.id,
        publisher_code=publisher.code,
        version=release.version,
        manifest=release.manifest,
        artifact_digest=release.artifact_digest,
        key_fingerprint=publisher.key_fingerprint,
        min_platform_version=release.min_platform_version,
        max_platform_version=release.max_platform_version,
        requested_permissions=release.requested_permissions,
        status=release.status,
        published_at=release.published_at,
    )


@router.get(
    "/{plugin_code}/marketplace/versions",
    response_model=list[PluginPackageVersionResponse],
)
async def list_marketplace_versions(
    plugin_code: str,
    principal: CanViewPlugins,
    database: DatabaseSession,
) -> list[PluginPackageVersionResponse]:
    del principal
    rows = (
        await database.execute(
            select(PluginPackageVersion, PluginPublisher, Plugin)
            .join(PluginPublisher, PluginPublisher.id == PluginPackageVersion.publisher_id)
            .join(Plugin, Plugin.id == PluginPackageVersion.plugin_id)
            .where(
                Plugin.code == plugin_code,
                PluginPackageVersion.status == "published",
                PluginPublisher.status == "trusted",
            )
            .order_by(PluginPackageVersion.published_at.desc())
        )
    ).all()
    return [_package_response(release, plugin, publisher) for release, publisher, plugin in rows]


@router.post(
    "/{plugin_code}/marketplace/install",
    response_model=PluginInstallationResponse,
)
async def install_marketplace_package(
    plugin_code: str,
    payload: PluginInstallationRequest,
    principal: CanManagePlugins,
    database: DatabaseSession,
    settings: RequestSettings,
) -> PluginInstallationResponse:
    context = get_request_context(principal)
    try:
        return await install_release(
            database,
            context=context,
            plugin_code=plugin_code,
            version=payload.version,
            platform_version=settings.app_version,
        )
    except MarketplaceContractError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/{plugin_code}/marketplace/rollback",
    response_model=PluginInstallationResponse,
)
async def rollback_marketplace_package(
    plugin_code: str,
    principal: CanManagePlugins,
    database: DatabaseSession,
    settings: RequestSettings,
) -> PluginInstallationResponse:
    context = get_request_context(principal)
    try:
        return await rollback_release(
            database,
            context=context,
            plugin_code=plugin_code,
            platform_version=settings.app_version,
        )
    except MarketplaceContractError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

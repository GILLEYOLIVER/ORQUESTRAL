from __future__ import annotations

from time import perf_counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from orkestral_plugin_sdk import PluginSDKError
from sqlalchemy import and_, select

from app.core.config import get_settings
from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.billing.service import UsageMetric, enforce_limit, record_usage
from app.modules.plugins.adapters import get_plugin_runtime
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError, mask_credential_fields
from app.modules.plugins.models import (
    CompanyPlugin,
    IntegrationCredential,
    Plugin,
    PluginConnectionTest,
)
from app.modules.plugins.schemas import (
    CompanyPluginUpdate,
    ConnectionTestHistoryResponse,
    ConnectionTestResponse,
    CredentialCreate,
    CredentialResponse,
    CredentialRotationResponse,
    PluginResponse,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])
CanViewPlugins = Annotated[Principal, Depends(require_permission("plugins.view"))]
CanManagePlugins = Annotated[Principal, Depends(require_permission("plugins.manage"))]


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

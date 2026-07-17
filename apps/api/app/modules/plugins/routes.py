from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select

from app.core.config import get_settings
from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.plugins.crypto import CredentialVault, mask_credentials
from app.modules.plugins.models import CompanyPlugin, IntegrationCredential, Plugin
from app.modules.plugins.schemas import (
    CompanyPluginUpdate,
    ConnectionTestResponse,
    CredentialCreate,
    CredentialResponse,
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
    )


@router.get("", response_model=list[PluginResponse])
async def list_plugins(principal: CanViewPlugins, database: DatabaseSession) -> list[PluginResponse]:
    context = get_request_context(principal)
    rows = (
        await database.execute(
            select(Plugin, CompanyPlugin)
            .outerjoin(
                CompanyPlugin,
                and_(CompanyPlugin.plugin_id == Plugin.id, CompanyPlugin.company_id == context.company_id),
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
    await database.commit()
    await database.refresh(company_plugin)
    return _plugin_response(plugin, company_plugin)


@router.post("/{plugin_code}/credentials", response_model=CredentialResponse, status_code=201)
async def create_credential(
    plugin_code: str,
    payload: CredentialCreate,
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> CredentialResponse:
    context = get_request_context(principal)
    plugin = await database.scalar(select(Plugin).where(Plugin.code == plugin_code))
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin não encontrado.")
    company_plugin = await database.scalar(
        select(CompanyPlugin).where(
            CompanyPlugin.company_id == context.company_id,
            CompanyPlugin.plugin_id == plugin.id,
            CompanyPlugin.status == "active",
        )
    )
    if company_plugin is None:
        raise HTTPException(status_code=409, detail="Ative o plugin antes de cadastrar credenciais.")
    vault = CredentialVault(get_settings().encryption_key)
    credential = IntegrationCredential(
        company_id=context.company_id,
        plugin_id=plugin.id,
        name=payload.name,
        encrypted_credentials=vault.encrypt(payload.values),
        expires_at=payload.expires_at,
    )
    database.add(credential)
    await database.commit()
    await database.refresh(credential)
    return CredentialResponse(
        id=credential.id,
        plugin_id=credential.plugin_id,
        name=credential.name,
        status=credential.status,
        masked_values=mask_credentials(payload.values),
        expires_at=credential.expires_at,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


@router.post("/{plugin_code}/credentials/{credential_id}/test", response_model=ConnectionTestResponse)
async def test_credential(
    plugin_code: str,
    credential_id: UUID,
    principal: CanManagePlugins,
    database: DatabaseSession,
) -> ConnectionTestResponse:
    context = get_request_context(principal)
    row = (
        await database.execute(
            select(IntegrationCredential, Plugin)
            .join(Plugin, Plugin.id == IntegrationCredential.plugin_id)
            .where(
                IntegrationCredential.id == credential_id,
                IntegrationCredential.company_id == context.company_id,
                Plugin.code == plugin_code,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada.")
    credential, plugin = row
    CredentialVault(get_settings().encryption_key).decrypt(credential.encrypted_credentials)
    return ConnectionTestResponse(
        success=True,
        message=f"Credencial do plugin {plugin.name} foi descriptografada e validada localmente.",
    )

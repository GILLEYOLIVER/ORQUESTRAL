from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.modularity.models import CompanyModule, ModuleCatalog
from app.modules.modularity.registry import module_registry
from app.modules.modularity.schemas import CompanyModuleUpdate, ModuleResponse

router = APIRouter(prefix="/modules", tags=["modules"])

CanViewModules = Annotated[Principal, Depends(require_permission("modules.view"))]
CanManageModules = Annotated[Principal, Depends(require_permission("modules.manage"))]


def _response(catalog: ModuleCatalog, company_module: CompanyModule | None) -> ModuleResponse:
    definition = module_registry.get(catalog.code)
    installed = definition is not None and catalog.status == "installed"
    is_core_active = catalog.is_core and catalog.status == "installed"
    return ModuleResponse(
        id=catalog.id,
        code=catalog.code,
        name=catalog.name,
        description=catalog.description,
        version=definition.version if definition is not None and installed else catalog.version,
        category=catalog.category,
        is_core=catalog.is_core,
        catalog_status=catalog.status,
        installed=installed,
        company_status=(
            company_module.status
            if company_module is not None
            else "active"
            if is_core_active
            else "inactive"
        ),
        configuration=company_module.configuration if company_module else {},
        activated_at=company_module.activated_at if company_module else None,
        deactivated_at=company_module.deactivated_at if company_module else None,
    )


@router.get("", response_model=list[ModuleResponse])
async def list_modules(
    principal: CanViewModules, database: DatabaseSession
) -> list[ModuleResponse]:
    context = get_request_context(principal)
    rows = (
        await database.execute(
            select(ModuleCatalog, CompanyModule)
            .outerjoin(
                CompanyModule,
                and_(
                    CompanyModule.module_id == ModuleCatalog.id,
                    CompanyModule.company_id == context.company_id,
                ),
            )
            .order_by(ModuleCatalog.category, ModuleCatalog.name)
        )
    ).all()
    return [_response(catalog, company_module) for catalog, company_module in rows]


@router.patch("/{module_code}", response_model=ModuleResponse)
async def update_company_module(
    module_code: str,
    payload: CompanyModuleUpdate,
    principal: CanManageModules,
    database: DatabaseSession,
) -> ModuleResponse:
    context = get_request_context(principal)
    catalog = await database.scalar(select(ModuleCatalog).where(ModuleCatalog.code == module_code))
    if catalog is None:
        raise HTTPException(status_code=404, detail="Módulo não encontrado.")
    if catalog.status != "installed" or module_registry.get(catalog.code) is None:
        raise HTTPException(status_code=409, detail="O módulo ainda não está instalado.")
    if catalog.is_core and payload.status == "inactive":
        raise HTTPException(status_code=409, detail="Módulos essenciais não podem ser desativados.")

    company_module = await database.scalar(
        select(CompanyModule).where(
            CompanyModule.company_id == context.company_id,
            CompanyModule.module_id == catalog.id,
        )
    )
    if company_module is None:
        company_module = CompanyModule(
            company_id=context.company_id,
            module_id=catalog.id,
            status="inactive",
        )
        database.add(company_module)

    now = utc_now()
    company_module.status = payload.status
    if payload.configuration is not None:
        company_module.configuration = payload.configuration
    if payload.status == "active":
        company_module.activated_at = now
        company_module.deactivated_at = None
    else:
        company_module.deactivated_at = now

    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=("module.activated" if payload.status == "active" else "module.deactivated"),
        target_type="module",
        target_id=catalog.id,
        details={"code": catalog.code},
    )
    await database.commit()
    await database.refresh(company_module)
    return _response(catalog, company_module)

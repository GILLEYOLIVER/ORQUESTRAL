from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.core.dependencies import DatabaseSession
from app.core.tenancy import CurrentPrincipal, Principal, get_request_context
from app.modules.modularity.models import CompanyModule, ModuleCatalog


def require_active_module(
    module_code: str,
) -> Callable[[CurrentPrincipal, DatabaseSession], Coroutine[Any, Any, Principal]]:
    async def module_dependency(
        principal: CurrentPrincipal, database: DatabaseSession
    ) -> Principal:
        context = get_request_context(principal)
        is_active = await database.scalar(
            select(CompanyModule.id)
            .join(ModuleCatalog, ModuleCatalog.id == CompanyModule.module_id)
            .where(
                CompanyModule.company_id == context.company_id,
                CompanyModule.status == "active",
                ModuleCatalog.code == module_code,
                ModuleCatalog.status == "installed",
            )
        )
        if is_active is None:
            raise HTTPException(
                status_code=403,
                detail=f"O módulo {module_code} não está ativo para a empresa atual.",
            )
        return principal

    return module_dependency

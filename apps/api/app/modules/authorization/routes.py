from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.models import (
    AuthorizationAuditEvent,
    Permission,
    Role,
    RolePermission,
)
from app.modules.authorization.schemas import (
    AuditEventResponse,
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/authorization", tags=["authorization"])

CanViewRoles = Annotated[Principal, Depends(require_permission("roles.view"))]
CanCreateRoles = Annotated[Principal, Depends(require_permission("roles.create"))]
CanUpdateRoles = Annotated[Principal, Depends(require_permission("roles.update"))]
CanDeleteRoles = Annotated[Principal, Depends(require_permission("roles.delete"))]


async def _permission_rows(
    database: DatabaseSession, permission_codes: list[str]
) -> list[Permission]:
    normalized = sorted(set(permission_codes))
    permissions = (
        await database.scalars(
            select(Permission).where(
                Permission.code.in_(normalized), Permission.module_code != "platform"
            )
        )
    ).all()
    if len(permissions) != len(normalized):
        raise HTTPException(status_code=422, detail="Uma ou mais permissões são inválidas.")
    return list(permissions)


async def _role_response(database: DatabaseSession, role: Role) -> RoleResponse:
    permission_codes = list(
        await database.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
            .order_by(Permission.code)
        )
    )
    return RoleResponse(
        id=role.id,
        company_id=role.company_id,
        name=role.name,
        description=role.description,
        is_system_role=role.is_system_role,
        permission_codes=permission_codes,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    principal: CanViewRoles, database: DatabaseSession
) -> list[PermissionResponse]:
    get_request_context(principal)
    permissions = (
        await database.scalars(
            select(Permission)
            .where(Permission.module_code != "platform")
            .order_by(Permission.module_code, Permission.action)
        )
    ).all()
    return [
        PermissionResponse.model_validate(permission, from_attributes=True)
        for permission in permissions
    ]


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(principal: CanViewRoles, database: DatabaseSession) -> list[RoleResponse]:
    context = get_request_context(principal)
    roles = (
        await database.scalars(
            select(Role).where(Role.company_id == context.company_id).order_by(Role.name)
        )
    ).all()
    return [await _role_response(database, role) for role in roles]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    principal: CanCreateRoles,
    database: DatabaseSession,
) -> RoleResponse:
    context = get_request_context(principal)
    permissions = await _permission_rows(database, payload.permission_codes)
    role = Role(
        company_id=context.company_id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
    )
    database.add(role)
    try:
        await database.flush()
        database.add_all(
            RolePermission(role_id=role.id, permission_id=permission.id)
            for permission in permissions
        )
        record_authorization_audit(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            action="role.created",
            target_type="role",
            target_id=role.id,
            details={"name": role.name, "permission_codes": sorted(payload.permission_codes)},
        )
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe um papel com esse nome.") from exc
    return await _role_response(database, role)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    principal: CanUpdateRoles,
    database: DatabaseSession,
) -> RoleResponse:
    context = get_request_context(principal)
    role = await database.scalar(
        select(Role).where(Role.id == role_id, Role.company_id == context.company_id)
    )
    if role is None:
        raise HTTPException(status_code=404, detail="Papel não encontrado.")
    if role.is_system_role:
        raise HTTPException(status_code=409, detail="Papéis de sistema não podem ser alterados.")

    if payload.name is not None:
        role.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        role.description = payload.description.strip() if payload.description else None
    if payload.permission_codes is not None:
        permissions = await _permission_rows(database, payload.permission_codes)
        await database.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        database.add_all(
            RolePermission(role_id=role.id, permission_id=permission.id)
            for permission in permissions
        )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="role.updated",
        target_type="role",
        target_id=role.id,
        details={
            "fields": sorted(payload.model_fields_set),
            "permission_codes": sorted(payload.permission_codes or []),
        },
    )
    role.updated_at = utc_now()
    try:
        await database.commit()
        await database.refresh(role)
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe um papel com esse nome.") from exc
    return await _role_response(database, role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    principal: CanDeleteRoles,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    role = await database.scalar(
        select(Role).where(Role.id == role_id, Role.company_id == context.company_id)
    )
    if role is None:
        raise HTTPException(status_code=404, detail="Papel não encontrado.")
    if role.is_system_role:
        raise HTTPException(status_code=409, detail="Papéis de sistema não podem ser excluídos.")
    assigned = await database.scalar(
        select(func.count()).select_from(CompanyUser).where(CompanyUser.role_id == role.id)
    )
    if assigned:
        raise HTTPException(status_code=409, detail="O papel possui usuários vinculados.")
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="role.deleted",
        target_type="role",
        target_id=role.id,
        details={"name": role.name},
    )
    await database.delete(role)
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    principal: CanViewRoles, database: DatabaseSession
) -> list[AuditEventResponse]:
    context = get_request_context(principal)
    events = (
        await database.scalars(
            select(AuthorizationAuditEvent)
            .where(AuthorizationAuditEvent.company_id == context.company_id)
            .order_by(AuthorizationAuditEvent.created_at.desc())
            .limit(100)
        )
    ).all()
    return [AuditEventResponse.model_validate(event, from_attributes=True) for event in events]

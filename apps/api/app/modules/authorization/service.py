from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.catalog import (
    SYSTEM_MEMBER_ROLE_NAME,
    SYSTEM_OWNER_ROLE_NAME,
    TENANT_PERMISSION_CODES,
)
from app.modules.authorization.models import (
    AuthorizationAuditEvent,
    Permission,
    Role,
    RolePermission,
)


async def ensure_company_system_roles(
    database: AsyncSession, company_id: UUID
) -> tuple[Role, Role]:
    roles = (
        await database.scalars(
            select(Role).where(
                Role.company_id == company_id,
                Role.is_system_role.is_(True),
            )
        )
    ).all()
    by_name = {role.name.lower(): role for role in roles}
    owner = by_name.get(SYSTEM_OWNER_ROLE_NAME.lower())
    member = by_name.get(SYSTEM_MEMBER_ROLE_NAME.lower())
    if owner is None:
        owner = Role(
            company_id=company_id,
            name=SYSTEM_OWNER_ROLE_NAME,
            description="Acesso administrativo completo à empresa.",
            is_system_role=True,
        )
        database.add(owner)
    if member is None:
        member = Role(
            company_id=company_id,
            name=SYSTEM_MEMBER_ROLE_NAME,
            description="Acesso básico sem permissões administrativas.",
            is_system_role=True,
        )
        database.add(member)
    await database.flush()

    tenant_permissions = (
        await database.scalars(
            select(Permission).where(Permission.code.in_(TENANT_PERMISSION_CODES))
        )
    ).all()
    existing_permission_ids = set(
        await database.scalars(
            select(RolePermission.permission_id).where(RolePermission.role_id == owner.id)
        )
    )
    database.add_all(
        RolePermission(role_id=owner.id, permission_id=permission.id)
        for permission in tenant_permissions
        if permission.id not in existing_permission_ids
    )
    await database.flush()
    return owner, member


def record_authorization_audit(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID | str,
    details: Mapping[str, Any] | None = None,
) -> None:
    database.add(
        AuthorizationAuditEvent(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            details=dict(details or {}),
        )
    )

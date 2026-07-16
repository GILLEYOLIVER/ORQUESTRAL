"""Importa os modelos para que o metadata do Alembic permaneça completo."""

from app.modules.authentication.models import (
    AuthAttempt,
    AuthSession,
    CompanyInvitation,
    PasswordResetToken,
)
from app.modules.authorization.models import (
    AuthorizationAuditEvent,
    Permission,
    Role,
    RolePermission,
)
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser, User

__all__ = [
    "AuthAttempt",
    "AuthSession",
    "AuthorizationAuditEvent",
    "Company",
    "CompanyInvitation",
    "CompanyUser",
    "PasswordResetToken",
    "Permission",
    "Role",
    "RolePermission",
    "User",
]

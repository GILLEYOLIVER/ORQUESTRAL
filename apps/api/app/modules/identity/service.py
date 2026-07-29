from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID

from app.core.security import hash_opaque_token

SCIM_PREFIX = "scim"


@dataclass(frozen=True, slots=True)
class SCIMTokenParts:
    company_id: UUID
    token_id: UUID


def create_scim_token(company_id: UUID, token_id: UUID) -> str:
    return f"{SCIM_PREFIX}.{company_id}.{token_id}.{secrets.token_urlsafe(48)}"


def parse_scim_token(value: str) -> SCIMTokenParts:
    parts = value.split(".")
    if len(parts) != 4 or parts[0] != SCIM_PREFIX or len(parts[3]) < 48:
        raise ValueError("Token SCIM inválido.")
    try:
        return SCIMTokenParts(company_id=UUID(parts[1]), token_id=UUID(parts[2]))
    except ValueError as error:
        raise ValueError("Token SCIM inválido.") from error


def scim_token_hash(settings: object, token: str) -> str:
    return hash_opaque_token(settings, token)  # type: ignore[arg-type]

from __future__ import annotations

from uuid import UUID

from app.core.config import Settings
from app.core.field_encryption import decrypt_text, encrypt_text


def delegation_associated_data(*, company_id: UUID, delegation_id: UUID) -> str:
    return f"agent-delegation:{company_id}:{delegation_id}"


def encrypt_delegation_objective(
    settings: Settings, *, company_id: UUID, delegation_id: UUID, objective: str
) -> str:
    return encrypt_text(
        settings,
        objective,
        associated_data=delegation_associated_data(
            company_id=company_id, delegation_id=delegation_id
        ),
    )


def decrypt_delegation_objective(
    settings: Settings, *, company_id: UUID, delegation_id: UUID, encrypted: str
) -> str:
    return decrypt_text(
        settings,
        encrypted,
        associated_data=delegation_associated_data(
            company_id=company_id, delegation_id=delegation_id
        ),
    )

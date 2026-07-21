from __future__ import annotations

import json
from typing import Any
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


def approval_associated_data(*, company_id: UUID, delegation_id: UUID, approval_id: UUID) -> str:
    return f"agent-delegation-approval:{company_id}:{delegation_id}:{approval_id}"


def encrypt_approval_arguments(
    settings: Settings,
    *,
    company_id: UUID,
    delegation_id: UUID,
    approval_id: UUID,
    arguments: dict[str, Any],
) -> str:
    return encrypt_text(
        settings,
        json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        associated_data=approval_associated_data(
            company_id=company_id,
            delegation_id=delegation_id,
            approval_id=approval_id,
        ),
    )


def decrypt_approval_arguments(
    settings: Settings,
    *,
    company_id: UUID,
    delegation_id: UUID,
    approval_id: UUID,
    encrypted: str,
) -> dict[str, Any]:
    value = json.loads(
        decrypt_text(
            settings,
            encrypted,
            associated_data=approval_associated_data(
                company_id=company_id,
                delegation_id=delegation_id,
                approval_id=approval_id,
            ),
        )
    )
    if not isinstance(value, dict):
        raise ValueError("Argumentos aprovados inválidos.")
    return value

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SENSITIVE_KEY_PARTS = frozenset(
    {"authorization", "cookie", "credential", "password", "secret", "session", "token"}
)
MAX_PAYLOAD_BYTES = 32_768


def _validate_safe_payload(value: object, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold()
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                raise ValueError(f"Campo sensivel nao permitido em evento: {path}.{key}")
            _validate_safe_payload(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_safe_payload(item, f"{path}[{index}]")


class DomainEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    event_id: UUID
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    event_version: int = Field(ge=1, le=1000)
    company_id: UUID
    actor_user_id: UUID | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    classification: Literal["public", "internal", "confidential", "restricted"]
    occurred_at: datetime
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_payload(payload)
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
        if len(encoded) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Payload de evento excede {MAX_PAYLOAD_BYTES} bytes.")
        return payload

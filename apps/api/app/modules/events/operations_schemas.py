from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
CONSUMER_PATTERN = r"^[a-z][a-z0-9_.-]{2,159}$"
MAX_SCHEMA_BYTES = 32_768


class EventOperationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EventContractCreate(EventOperationSchema):
    event_type: str = Field(min_length=3, max_length=160, pattern=EVENT_TYPE_PATTERN)
    version: int = Field(ge=1, le=1000)
    classification: Literal["public", "internal", "confidential", "restricted"] = "internal"
    compatibility_mode: Literal["strict", "backward"] = "backward"
    payload_schema: dict[str, object]

    @field_validator("payload_schema")
    @classmethod
    def validate_payload_schema(cls, value: dict[str, object]) -> dict[str, object]:
        if (
            len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())
            > MAX_SCHEMA_BYTES
        ):
            raise ValueError("O schema do evento excede 32 KiB.")
        properties_value = value.get("properties")
        if value.get("type") != "object" or not isinstance(properties_value, dict):
            raise ValueError("O schema deve declarar type=object e properties.")
        if "$ref" in json.dumps(value):
            raise ValueError("Referencias externas nao sao permitidas em contratos de evento.")
        required = value.get("required", [])
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ValueError("required deve ser uma lista de campos.")
        properties = properties_value
        if any(item not in properties for item in required):
            raise ValueError("Todo campo obrigatorio deve existir em properties.")
        if value.get("additionalProperties", False) not in (True, False):
            raise ValueError("additionalProperties deve ser booleano.")
        return value


class EventContractResponse(EventOperationSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    version: int
    status: str
    classification: str
    compatibility_mode: str
    payload_schema: dict[str, object]
    checksum: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EventSubscriptionCreate(EventOperationSchema):
    name: str = Field(min_length=3, max_length=120)
    consumer_name: str = Field(min_length=3, max_length=160, pattern=CONSUMER_PATTERN)
    event_type: str = Field(min_length=3, max_length=160, pattern=EVENT_TYPE_PATTERN)
    min_version: int = Field(default=1, ge=1, le=1000)
    max_version: int | None = Field(default=None, ge=1, le=1000)
    delivery_mode: Literal["ledger", "workflow"] = "ledger"
    workflow_id: UUID | None = None
    max_attempts: int = Field(default=8, ge=1, le=25)

    @model_validator(mode="after")
    def validate_binding(self) -> EventSubscriptionCreate:
        if self.max_version is not None and self.max_version < self.min_version:
            raise ValueError("A versao maxima deve ser maior ou igual a minima.")
        if self.delivery_mode == "workflow" and self.workflow_id is None:
            raise ValueError("Selecione uma automacao para a assinatura.")
        if self.delivery_mode == "ledger" and self.workflow_id is not None:
            raise ValueError("Assinaturas de registro nao recebem uma automacao.")
        return self


class EventSubscriptionPatch(EventOperationSchema):
    active: bool


class EventSubscriptionResponse(EventOperationSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    consumer_name: str
    event_type: str
    min_version: int
    max_version: int | None
    delivery_mode: str
    workflow_id: UUID | None
    active: bool
    max_attempts: int
    created_at: datetime
    updated_at: datetime


class EventDeliveryResponse(EventOperationSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    subscription_id: UUID
    status: str
    attempt_count: int
    max_attempts: int
    last_error_code: str | None
    replay_count: int
    available_at: datetime
    processed_at: datetime | None
    created_at: datetime


class OutboxEventResponse(EventOperationSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    event_version: int
    classification: str
    status: str
    attempt_count: int
    max_attempts: int
    correlation_id: UUID | None
    causation_id: UUID | None
    last_error_code: str | None
    published_at: datetime | None
    created_at: datetime


class EventReplayResponse(EventOperationSchema):
    id: UUID
    status: str
    source_id: UUID


class EventOperationsSummary(EventOperationSchema):
    contracts: int
    subscriptions: int
    pending_deliveries: int
    dead_letters: int
    failed_outbox: int

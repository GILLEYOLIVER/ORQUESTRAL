from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.events.schemas import MAX_PAYLOAD_BYTES, DomainEventEnvelope


def _event(**overrides: object) -> DomainEventEnvelope:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "event_type": "contact.created",
        "event_version": 1,
        "company_id": uuid4(),
        "classification": "internal",
        "occurred_at": datetime.now(UTC),
        "payload": {"contact_id": str(uuid4())},
    }
    values.update(overrides)
    return DomainEventEnvelope.model_validate(values)


def test_domain_event_accepts_a_versioned_minimal_payload() -> None:
    event = _event()
    assert event.event_type == "contact.created"
    assert event.event_version == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "nao-pode"},
        {"nested": {"access_token": "nao-pode"}},
        {"items": [{"client_secret": "nao-pode"}]},
    ],
)
def test_domain_event_rejects_sensitive_payload_keys(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="Campo sensivel"):
        _event(payload=payload)


def test_domain_event_rejects_oversized_payload() -> None:
    with pytest.raises(ValidationError, match="excede"):
        _event(payload={"content": "x" * (MAX_PAYLOAD_BYTES + 1)})

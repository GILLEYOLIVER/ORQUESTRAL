from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from app.modules.support.channels_schemas import SupportChannelIngressRequest
from app.modules.support.channels_security import (
    protected_reference,
    sign_channel_request,
    valid_idempotency_key,
    verify_channel_request,
)


def test_channel_signature_is_body_bound_and_replay_limited() -> None:
    secret = "integration-secret"
    body = b'{"subject":"Ajuda","message":"Preciso de suporte"}'
    timestamp = str(int(time.time()))
    signature = sign_channel_request(secret, timestamp, body)

    assert verify_channel_request(
        secret,
        timestamp,
        body,
        signature,
        max_age_seconds=300,
        now=int(timestamp),
    )
    assert not verify_channel_request(
        secret,
        timestamp,
        body + b" ",
        signature,
        max_age_seconds=300,
        now=int(timestamp),
    )
    assert not verify_channel_request(
        secret,
        timestamp,
        body,
        signature,
        max_age_seconds=300,
        now=int(timestamp) + 301,
    )


def test_channel_idempotency_and_sensitive_reference_contracts() -> None:
    assert valid_idempotency_key("provider:event-0001")
    assert not valid_idempotency_key("short")
    assert not valid_idempotency_key("event with spaces")

    first = protected_reference("private-key", "cliente@example.com")
    second = protected_reference("private-key", "cliente@example.com")
    assert first == second
    assert first != "cliente@example.com"
    assert len(first or "") == 64


def test_channel_payload_is_strict_and_normalized() -> None:
    payload = SupportChannelIngressRequest(
        subject="  Preciso de ajuda  ",
        message="  Minha entrega atrasou.  ",
        language_code=" PT-BR ",
    )
    assert payload.subject == "Preciso de ajuda"
    assert payload.message == "Minha entrega atrasou."
    assert payload.language_code == "pt-br"

    with pytest.raises(ValidationError):
        SupportChannelIngressRequest(subject=" ", message="mensagem")

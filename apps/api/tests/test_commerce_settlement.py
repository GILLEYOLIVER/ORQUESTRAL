from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.commerce.settlement_schemas import PaymentIntentCreate, ReturnCreate
from app.modules.commerce.settlement_service import (
    PaymentSecurityError,
    calculate_percentage,
    verify_webhook_signature,
    webhook_signature,
)


def test_percentage_rounds_as_currency() -> None:
    assert calculate_percentage(Decimal("199.99"), Decimal("2.5")) == Decimal("5.00")


def test_payment_schema_rejects_sensitive_card_fields() -> None:
    with pytest.raises(ValidationError):
        PaymentIntentCreate.model_validate(
            {
                "provider": "manual",
                "method_type": "card",
                "idempotency_key": "payment-123",
                "card_number": "4111111111111111",
            }
        )


def test_return_rejects_duplicate_order_items() -> None:
    line = {
        "order_item_id": "35bd6aea-dcb8-4cd7-a9a6-9b09caeb55c7",
        "quantity": "1",
    }
    with pytest.raises(ValidationError):
        ReturnCreate.model_validate(
            {
                "reason": "Produto devolvido pelo cliente",
                "idempotency_key": "return-123",
                "items": [line, line],
            }
        )


def test_webhook_signature_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET_MANUAL", "segredo-forte-de-teste")
    body = b'{"event":"captured"}'
    signature = webhook_signature("manual", body, "segredo-forte-de-teste")
    verify_webhook_signature("manual", body, f"sha256={signature}")
    with pytest.raises(PaymentSecurityError):
        verify_webhook_signature("manual", body, "sha256=invalid")

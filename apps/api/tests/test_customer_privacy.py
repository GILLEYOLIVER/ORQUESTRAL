from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.crm.customer_privacy_schemas import (
    CustomerPrivacyLegalHoldRequest,
    CustomerPrivacyRequestCreate,
)
from app.modules.crm.customer_privacy_service import privacy_reference_fingerprint


def test_privacy_reference_fingerprint_is_normalized_and_tenant_scoped() -> None:
    first_company = UUID("00000000-0000-0000-0000-000000000001")
    second_company = UUID("00000000-0000-0000-0000-000000000002")

    first = privacy_reference_fingerprint(first_company, "  Protocolo   123 ")
    normalized = privacy_reference_fingerprint(first_company, "protocolo 123")
    other_tenant = privacy_reference_fingerprint(second_company, "protocolo 123")

    assert first == normalized
    assert first != other_tenant
    assert len(first) == 64
    assert "protocolo" not in first


def test_privacy_request_deduplicates_scope() -> None:
    payload = CustomerPrivacyRequestCreate(
        profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        request_type="deletion",
        request_reference="PROTOCOLO-123",
        scope=["profile", "profile", "crm"],
    )

    assert payload.scope == ["profile", "crm"]


def test_legal_hold_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        CustomerPrivacyLegalHoldRequest(enabled=True)


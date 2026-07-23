from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.crm.customer_segment_schemas import (
    CustomerProfileSearchResponse,
    CustomerSegmentActivationRequest,
    CustomerSegmentCreate,
    CustomerSegmentDefinition,
)


def test_segment_definition_requires_purpose_for_specific_channel() -> None:
    with pytest.raises(ValidationError):
        CustomerSegmentDefinition(consent_channel="email")


def test_segment_definition_accepts_governed_filters() -> None:
    definition = CustomerSegmentDefinition(
        profile_type="person",
        lifecycle_status="customer",
        min_quality_score=75,
        consent_purpose="marketing",
        consent_channel="email",
    )
    payload = CustomerSegmentCreate(
        name="Clientes engajados",
        definition=definition,
    )
    assert payload.definition.min_quality_score == 75


def test_activation_accepts_only_uuid_campaign() -> None:
    payload = CustomerSegmentActivationRequest(campaign_id=uuid4())
    assert payload.campaign_id
    with pytest.raises(ValidationError):
        CustomerSegmentActivationRequest(campaign_id="campanha")


def test_search_contract_does_not_expose_raw_identity_fields() -> None:
    response = CustomerProfileSearchResponse(query_kind="text", results=[])
    serialized = response.model_dump(mode="json")
    assert "email" not in serialized
    assert "phone" not in serialized
    assert "value_hash" not in serialized

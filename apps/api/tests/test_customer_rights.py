from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.crm.customer_rights_schemas import (
    CustomerCorrectionRequest,
    CustomerSubjectActivitySummary,
    CustomerSubjectExportResponse,
    CustomerSubjectProfileExport,
)


def test_customer_correction_requires_at_least_one_non_null_field() -> None:
    with pytest.raises(ValidationError):
        CustomerCorrectionRequest()
    with pytest.raises(ValidationError):
        CustomerCorrectionRequest(email=None)


def test_customer_correction_normalizes_email_and_text() -> None:
    payload = CustomerCorrectionRequest(
        display_name="  Cliente Corrigido  ",
        email="  PESSOA@EXAMPLE.COM ",
    )
    assert payload.display_name == "Cliente Corrigido"
    assert payload.email == "pessoa@example.com"


def test_subject_export_contract_never_contains_identity_hashes() -> None:
    response = CustomerSubjectExportResponse(
        generated_at=datetime.now(UTC),
        profile=CustomerSubjectProfileExport(
            id=uuid4(),
            display_name="Cliente de Teste",
            profile_type="person",
            lifecycle_status="lead",
            quality_score=90,
            status="active",
        ),
        contact=None,
        identities=[],
        consents=[],
        activity_summary=CustomerSubjectActivitySummary(
            support_tickets=0,
            opportunities=0,
            marketing_attributions=0,
            privacy_requests=0,
        ),
        processing_restricted=False,
        integrity_sha256="0" * 64,
    )
    exported = response.model_dump(mode="json")
    assert "value_hash" not in str(exported)
    assert exported["export_version"] == "1.0"


def test_subject_export_integrity_digest_is_required() -> None:
    with pytest.raises(ValidationError):
        CustomerSubjectExportResponse.model_validate(
            {
                "generated_at": datetime.now(UTC),
                "profile": {
                    "id": uuid4(),
                    "display_name": "Cliente",
                    "profile_type": "person",
                    "lifecycle_status": "lead",
                    "quality_score": 100,
                    "status": "active",
                },
                "contact": None,
                "identities": [],
                "consents": [],
                "activity_summary": {
                    "support_tickets": 0,
                    "opportunities": 0,
                    "marketing_attributions": 0,
                    "privacy_requests": 0,
                },
                "processing_restricted": False,
            }
        )

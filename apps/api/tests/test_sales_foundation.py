from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.crm.sales_schemas import (
    CRMAccountCreate,
    CRMLeadConversionCreate,
    CRMLeadCreate,
    CRMLeadQualification,
)
from app.modules.crm.sales_service import calculate_lead_score


def test_lead_score_is_deterministic_and_bounded() -> None:
    assert calculate_lead_score({}) == 10
    assert (
        calculate_lead_score(
            {
                "email": "lead@example.test",
                "phone": "+5511999999999",
                "company_name": "Empresa Teste",
                "job_title": "Diretora",
                "source": "evento",
            }
        )
        == 100
    )


def test_sales_payloads_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        CRMAccountCreate(name="A", annual_revenue=Decimal("-1"))
    with pytest.raises(ValidationError):
        CRMLeadCreate(name="A")
    with pytest.raises(ValidationError):
        CRMLeadQualification(decision="qualified", note="x")


def test_conversion_requires_non_negative_amount() -> None:
    with pytest.raises(ValidationError):
        CRMLeadConversionCreate(
            pipeline_id="11111111-1111-4111-8111-111111111111",
            stage_id="22222222-2222-4222-8222-222222222222",
            opportunity_title="Contrato anual",
            amount=Decimal("-0.01"),
        )

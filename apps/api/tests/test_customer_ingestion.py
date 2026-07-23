from __future__ import annotations

from fastapi.testclient import TestClient

from app.modules.crm.customer_ingestion_schemas import CustomerIngestionRecordInput
from app.modules.crm.customer_ingestion_service import (
    masked_hint,
    payload_fingerprint,
    validate_ingestion_record,
)


def test_ingestion_validation_and_fingerprint_do_not_expose_payload() -> None:
    record = CustomerIngestionRecordInput(
        source_record_id="customer-1",
        external_id="ext-1",
        display_name="Cliente Seguro",
        email="cliente@example.com",
        phone="+55 11 99999-0000",
    )
    errors, score = validate_ingestion_record(
        record,
        {
            "required": ["external_id", "display_name"],
            "email_format": True,
            "phone_min_digits": 8,
            "minimum_score": 60,
        },
    )
    fingerprint = payload_fingerprint(record)
    assert errors == []
    assert score == 100
    assert len(fingerprint) == 64
    assert "cliente" not in fingerprint


def test_ingestion_rejects_invalid_contact_data() -> None:
    record = CustomerIngestionRecordInput(
        source_record_id="customer-2",
        email="invalido",
        phone="123",
    )
    errors, score = validate_ingestion_record(record, {})
    assert "external_id:required" in errors
    assert "display_name:required" in errors
    assert "email:invalid_format" in errors
    assert "phone:insufficient_digits" in errors
    assert "quality:below_minimum" in errors
    assert score == 0


def test_masked_hints_keep_sensitive_values_out() -> None:
    assert masked_hint("cliente@example.com", "email") == "c***@example.com"
    assert masked_hint("+55 11 99999-1234", "phone") == "***1234"


def test_customer_ingestion_routes_are_protected_and_published(client: TestClient) -> None:
    assert client.get("/crm/customer-data/ingestion/jobs").status_code == 401
    assert client.get("/crm/customer-data/ingestion/dead-letters").status_code == 401
    paths = client.get("/openapi.json").json()["paths"]
    assert "/crm/customer-data/ingestion/quality-rules" in paths
    assert "/crm/customer-data/ingestion/jobs" in paths
    assert "/crm/customer-data/ingestion/dead-letters" in paths
    assert "/crm/customer-data/ingestion/dead-letters/{record_id}/reprocess" in paths

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.crm.customer_cdc_schemas import (
    CustomerCdcRetentionPurgeRequest,
    CustomerCdcSubscriptionCreate,
)
from app.modules.crm.customer_cdc_service import customer_change_metadata
from worker.main import celery_app


def test_customer_change_metadata_exposes_only_field_names_and_fingerprint() -> None:
    changed_fields, fingerprint = customer_change_metadata(
        {
            "display_name": "Cliente Sigiloso",
            "email": "segredo@example.com",
            "phone": "+5511999999999",
            "unexpected_secret": "never-expose-me",
        }
    )

    assert changed_fields == ["display_name", "email", "phone"]
    assert len(fingerprint) == 64
    assert "Cliente Sigiloso" not in fingerprint
    assert "segredo@example.com" not in fingerprint
    assert "unexpected_secret" not in changed_fields


def test_customer_cdc_subscription_deduplicates_operations() -> None:
    subscription = CustomerCdcSubscriptionCreate(
        name="Analytics autorizado",
        consumer_key="analytics.authorized",
        operations=["upserted", "upserted", "deleted"],
    )

    assert subscription.operations == ["upserted", "deleted"]


def test_customer_cdc_purge_requires_literal_confirmation() -> None:
    with pytest.raises(ValidationError):
        CustomerCdcRetentionPurgeRequest(
            confirmation="delete",
            max_delete=100,
        )


def test_customer_cdc_purge_has_a_bounded_batch() -> None:
    with pytest.raises(ValidationError):
        CustomerCdcRetentionPurgeRequest(
            confirmation="PURGE_EXPIRED_CDC_EVENTS",
            max_delete=5_001,
        )


def test_customer_cdc_retention_worker_is_scheduled_hourly() -> None:
    schedule = celery_app.conf.beat_schedule[
        "maintain-customer-cdc-retention-every-hour"
    ]

    assert schedule["task"] == "orkestral.customer_data.maintain_cdc_retention"
    assert schedule["schedule"] == 3600.0

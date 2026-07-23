from __future__ import annotations

from app.modules.crm.customer_cdc_schemas import CustomerCdcSubscriptionCreate
from app.modules.crm.customer_cdc_service import customer_change_metadata


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


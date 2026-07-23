from __future__ import annotations

import asyncio
import json

import pytest

from app.core.secure_http import SecureHttpResponse
from app.modules.crm.customer_sync_rest_adapter import (
    RestPullAdapterError,
    pull_customer_records,
)


def test_rest_pull_maps_typed_records_without_returning_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(*args: object, **kwargs: object) -> SecureHttpResponse:
        assert "secret-token" in str(kwargs["headers"])
        return SecureHttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body=json.dumps(
                {
                    "records": [
                        {
                            "source_record_id": "external-1",
                            "external_id": "customer-1",
                            "display_name": "Cliente Exemplo",
                            "email": "cliente@example.com",
                        }
                    ],
                    "next_cursor": "page-2",
                }
            ).encode(),
        )

    monkeypatch.setattr(
        "app.modules.crm.customer_sync_rest_adapter.secure_https_get",
        fake_get,
    )
    batch = asyncio.run(
        pull_customer_records(
            {
                "base_url": "https://api.example.com/customers",
                "api_key": "secret-token",
            },
            cursor=None,
            timeout_seconds=5,
            max_response_bytes=10_000,
        )
    )
    assert batch.records[0].source_record_id == "external-1"
    assert batch.cursor_after == "page-2"
    assert batch.response_bytes > 0
    assert "secret-token" not in repr(batch)


def test_rest_pull_rejects_unbounded_record_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(*args: object, **kwargs: object) -> SecureHttpResponse:
        return SecureHttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body=json.dumps({"records": [{}] * 101}).encode(),
        )

    monkeypatch.setattr(
        "app.modules.crm.customer_sync_rest_adapter.secure_https_get",
        fake_get,
    )
    with pytest.raises(RestPullAdapterError) as captured:
        asyncio.run(
            pull_customer_records(
                {"base_url": "https://api.example.com/customers"},
                cursor=None,
                timeout_seconds=5,
                max_response_bytes=100_000,
            )
        )
    assert captured.value.code == "RESPONSE_RECORDS_INVALID"

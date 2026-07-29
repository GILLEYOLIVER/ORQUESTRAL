from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.developer.schemas import PromotionCreate, SandboxCreate
from app.modules.developer.service import can_promote


def test_promotion_routes_are_forward_only() -> None:
    assert can_promote("local", "testing")
    assert can_promote("development", "staging")
    assert can_promote("staging", "production")
    assert not can_promote("local", "production")
    assert not can_promote("production", "development")


def test_sandbox_cannot_be_production() -> None:
    with pytest.raises(ValidationError):
        SandboxCreate.model_validate(
            {
                "code": "producao",
                "name": "Produção indevida",
                "environment": "production",
                "data_policy": "empty",
                "expires_at": "2099-01-01T00:00:00Z",
            }
        )


def test_promotion_requires_sha256_checksum() -> None:
    with pytest.raises(ValidationError):
        PromotionCreate.model_validate(
            {
                "artifact_type": "plugin",
                "artifact_ref": "crm.connector@1.0.0",
                "source_environment": "testing",
                "target_environment": "staging",
                "checksum": "not-a-digest",
            }
        )

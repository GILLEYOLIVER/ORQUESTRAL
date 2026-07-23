from __future__ import annotations

from pathlib import Path

from app.modules.support.channels_schemas import SupportChannelEndpointResponse

ROOT = Path(__file__).resolve().parents[1]


def test_support_channel_tables_force_tenant_rls() -> None:
    migration = (
        ROOT
        / "app"
        / "migrations"
        / "versions"
        / "20260723_0107_support_omnichannel_ingress.py"
    ).read_text(encoding="utf-8")

    assert migration.count('_rls("support_channel_') == 2
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_company_id" in migration


def test_channel_list_contract_never_exposes_secret_ciphertext() -> None:
    fields = set(SupportChannelEndpointResponse.model_fields)
    assert "webhook_secret" not in fields
    assert "encrypted_secret" not in fields
    assert "secret_fingerprint" in fields

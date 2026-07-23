from pathlib import Path


def test_segment_activation_requires_consent_and_restriction_checks() -> None:
    source = (
        Path(__file__).parents[1]
        / "app"
        / "modules"
        / "crm"
        / "customer_segment_service.py"
    ).read_text()
    assert "customer_processing_restrictions" in source
    assert "consent.status = 'granted'" in source
    assert "consent.purpose = 'marketing'" in source
    assert "ON CONFLICT (campaign_id, contact_id) DO NOTHING" in source

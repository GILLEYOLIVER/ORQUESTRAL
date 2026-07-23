from pathlib import Path


def test_ingestion_contract_enforces_processing_restrictions() -> None:
    source = (
        Path(__file__).parents[1]
        / "app"
        / "modules"
        / "crm"
        / "customer_ingestion_service.py"
    ).read_text()
    assert "CustomerProcessingRestrictedError" in source
    assert "customer_processing_restrictions" in source
    assert '"processing_restricted"' in source

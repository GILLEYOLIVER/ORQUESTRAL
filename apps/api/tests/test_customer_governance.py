from __future__ import annotations

from fastapi.testclient import TestClient

from app.modules.crm.customer_governance_schemas import CustomerMatchRuleCreate
from app.modules.crm.customer_governance_service import name_similarity


def test_customer_name_similarity_is_accent_and_case_insensitive() -> None:
    assert name_similarity("José da Silva", "JOSE DA SILVA") == 1
    assert name_similarity("Empresa Aurora", "Comercial Boreal") < 0.5


def test_customer_match_rule_schema_rejects_unsafe_threshold() -> None:
    try:
        CustomerMatchRuleCreate(name="Regra inválida", threshold=0.2)
    except ValueError:
        pass
    else:
        raise AssertionError("Threshold inferior a 0.5 deveria ser recusado.")


def test_customer_governance_routes_require_authentication(client: TestClient) -> None:
    assert client.get("/crm/customer-data/match-rules").status_code == 401
    assert client.get("/crm/customer-data/merge-cases").status_code == 401


def test_customer_governance_contract_is_published(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/crm/customer-data/match-rules" in paths
    assert "/crm/customer-data/matches/scan" in paths
    assert "/crm/customer-data/merge-cases/{case_id}/decision" in paths
    assert "/crm/customer-data/merge-cases/{case_id}/revert" in paths
    assert "/crm/customer-data/profiles/{profile_id}/lineage" in paths

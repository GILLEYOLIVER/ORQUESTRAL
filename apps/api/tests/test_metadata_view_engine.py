from app.modules.metadata.schemas import MetadataViewInput
from app.modules.metadata.view_engine import validate_view_contract


def test_view_contract_accepts_typed_filters_and_sorting() -> None:
    view = MetadataViewInput(
        key="high_value",
        label="Alto valor",
        columns=["name", "amount"],
        filters=[{"field_key": "amount", "operator": "greater_than", "value": "100"}],
        sorting=[{"field_key": "amount", "direction": "desc"}],
        is_default=True,
    )

    assert validate_view_contract(view, {"name": "text", "amount": "decimal"}) == []


def test_view_contract_rejects_unsafe_operator_type_combinations() -> None:
    view = MetadataViewInput(
        key="invalid_view",
        label="Visualizacao invalida",
        columns=["payload"],
        filters=[
            {"field_key": "payload", "operator": "contains", "value": "secret"},
            {"field_key": "amount", "operator": "contains", "value": "10"},
            {"field_key": "name", "operator": "equals", "value": None},
        ],
        sorting=[{"field_key": "payload", "direction": "asc"}],
    )

    errors = validate_view_contract(
        view,
        {"payload": "json", "amount": "decimal", "name": "text"},
    )

    assert len(errors) == 4
    assert any("estruturado" in error for error in errors)
    assert any("exige campo textual" in error for error in errors)
    assert any("exige valor" in error for error in errors)


def test_view_contract_rejects_duplicate_sorting() -> None:
    view = MetadataViewInput(
        key="duplicate_sort",
        label="Ordem duplicada",
        columns=["name"],
        sorting=[
            {"field_key": "name", "direction": "asc"},
            {"field_key": "name", "direction": "desc"},
        ],
    )

    assert validate_view_contract(view, {"name": "text"}) == [
        "A visualizacao 'duplicate_sort' nao pode repetir campos de ordenacao."
    ]

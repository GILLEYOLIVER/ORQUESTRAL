from types import SimpleNamespace

import pytest

from app.modules.metadata.formula_engine import apply_formulas, validate_formula_contracts
from app.modules.metadata.schemas import MetadataFormulaInput


def _formula(operator: str = "multiply") -> MetadataFormulaInput:
    return MetadataFormulaInput.model_validate(
        {
            "key": "total_formula",
            "label": "Total calculado",
            "target_field_key": "total",
            "expression": {
                "operator": operator,
                "operands": [
                    {"type": "field", "field_key": "quantity"},
                    {"type": "field", "field_key": "unit_price"},
                ],
            },
        }
    )


def test_formula_engine_calculates_without_executing_code() -> None:
    result = apply_formulas([_formula()], {"quantity": "3", "unit_price": "12.50"})
    assert result["total"] == "37.50"


def test_formula_engine_rejects_division_by_zero() -> None:
    with pytest.raises(ValueError, match="dividir por zero"):
        apply_formulas([_formula("divide")], {"quantity": "3", "unit_price": "0"})


def test_formula_contract_rejects_cycles() -> None:
    formulas = [
        MetadataFormulaInput.model_validate(
            {
                "key": "total_formula",
                "label": "Total calculado",
                "target_field_key": "total",
                "expression": {
                    "operator": "add",
                    "operands": [
                        {"type": "field", "field_key": "subtotal"},
                        {"type": "literal", "value": 1},
                    ],
                },
            }
        ),
        MetadataFormulaInput.model_validate(
            {
                "key": "subtotal_formula",
                "label": "Subtotal",
                "target_field_key": "subtotal",
                "expression": {
                    "operator": "add",
                    "operands": [
                        {"type": "field", "field_key": "total"},
                        {"type": "literal", "value": 1},
                    ],
                },
            }
        ),
    ]
    fields = [
        SimpleNamespace(key="quantity", data_type="decimal"),
        SimpleNamespace(key="unit_price", data_type="decimal"),
        SimpleNamespace(key="total", data_type="decimal"),
        SimpleNamespace(key="subtotal", data_type="decimal"),
    ]
    assert "dependencia circular" in " ".join(validate_formula_contracts(formulas, fields))

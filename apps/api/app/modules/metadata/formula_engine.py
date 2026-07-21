from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import JsonValue

from app.modules.metadata.models import MetadataFieldDefinition
from app.modules.metadata.schemas import MetadataFormulaInput, MetadataFormulaOperandInput


def formula_dependencies(formula: MetadataFormulaInput) -> frozenset[str]:
    return frozenset(
        operand.field_key
        for operand in formula.expression.operands
        if operand.type == "field" and operand.field_key is not None
    )


def validate_formula_contracts(
    formulas: Sequence[MetadataFormulaInput], fields: Sequence[MetadataFieldDefinition]
) -> list[str]:
    errors: list[str] = []
    field_by_key = {field.key: field for field in fields}
    targets = {formula.target_field_key for formula in formulas if formula.active}
    for formula in formulas:
        target = field_by_key.get(formula.target_field_key)
        if target is None:
            errors.append(
                f"A formula '{formula.key}' usa o campo de destino desconhecido "
                f"'{formula.target_field_key}'."
            )
            continue
        unknown = sorted(formula_dependencies(formula) - set(field_by_key))
        if unknown:
            errors.append(
                f"A formula '{formula.key}' usa campos desconhecidos: {', '.join(unknown)}."
            )
        if formula.target_field_key in formula_dependencies(formula):
            errors.append(f"A formula '{formula.key}' nao pode depender do proprio resultado.")
        if formula.expression.operator in {
            "add",
            "subtract",
            "multiply",
            "divide",
        } and target.data_type not in {
            "integer",
            "decimal",
        }:
            errors.append(f"A formula numerica '{formula.key}' exige destino inteiro ou decimal.")
        if formula.expression.operator == "concat" and target.data_type not in {
            "text",
            "long_text",
        }:
            errors.append(f"A formula de texto '{formula.key}' exige destino textual.")

    dependencies = {
        formula.target_field_key: formula_dependencies(formula) & targets
        for formula in formulas
        if formula.active
    }
    resolved: set[str] = set()
    remaining = dict(dependencies)
    while remaining:
        ready = {target for target, deps in remaining.items() if deps <= resolved}
        if not ready:
            errors.append("As formulas possuem uma dependencia circular.")
            break
        resolved.update(ready)
        remaining = {target: deps for target, deps in remaining.items() if target not in ready}
    return errors


def _operand_value(operand: MetadataFormulaOperandInput, values: Mapping[str, JsonValue]) -> Any:
    if operand.type == "field":
        if operand.field_key is None:
            raise ValueError("A formula possui um operando de campo incompleto.")
        return values.get(operand.field_key)
    return operand.value


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("A formula numerica recebeu um valor nao numerico.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("A formula numerica recebeu um valor nao numerico.") from exc
    if not number.is_finite():
        raise ValueError("A formula numerica produziu um valor nao finito.")
    return number


def _evaluate(formula: MetadataFormulaInput, values: Mapping[str, JsonValue]) -> JsonValue:
    operands = [_operand_value(item, values) for item in formula.expression.operands]
    operator = formula.expression.operator
    if operator == "coalesce":
        return next((value for value in operands if value not in (None, "")), None)
    if operator == "concat":
        return "".join("" if value is None else str(value) for value in operands)
    numbers = [_decimal(value) for value in operands]
    result = numbers[0]
    if operator == "add":
        result = sum(numbers, Decimal(0))
    elif operator == "subtract":
        for number in numbers[1:]:
            result -= number
    elif operator == "multiply":
        for number in numbers[1:]:
            result *= number
    elif operator == "divide":
        for number in numbers[1:]:
            if number == 0:
                raise ValueError(f"A formula '{formula.label}' tentou dividir por zero.")
            result /= number
    return format(result, "f")


def apply_formulas(
    formulas: Sequence[MetadataFormulaInput], values: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    active = {formula.target_field_key: formula for formula in formulas if formula.active}
    result = dict(values)
    pending = dict(active)
    while pending:
        ready = [
            target
            for target, formula in pending.items()
            if not (formula_dependencies(formula) & set(pending))
        ]
        if not ready:
            raise ValueError("As formulas possuem uma dependencia circular.")
        for target in ready:
            result[target] = _evaluate(pending.pop(target), result)
    return result

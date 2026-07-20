from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.inventory.schemas import ItemCreate, MovementCreate


def test_movement_requires_the_correct_quantity_field() -> None:
    with pytest.raises(ValidationError):
        MovementCreate(
            item_id="00000000-0000-0000-0000-000000000001",
            location_id="00000000-0000-0000-0000-000000000002",
            movement_type="out",
            reason="Venda",
        )


def test_inventory_item_and_adjustment_are_valid() -> None:
    item = ItemCreate(sku="PROD-01", name="Produto", minimum_stock=Decimal("2.5"))
    movement = MovementCreate(
        item_id="00000000-0000-0000-0000-000000000001",
        location_id="00000000-0000-0000-0000-000000000002",
        movement_type="adjustment",
        adjusted_quantity=Decimal("7"),
        reason="Contagem fisica",
    )
    assert item.unit == "unit"
    assert movement.adjusted_quantity == Decimal("7")

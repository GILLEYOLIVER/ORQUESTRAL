from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.finance.schemas import AccountCreate, EntryCreate


def test_financial_entry_rejects_zero_amount() -> None:
    with pytest.raises(ValidationError):
        EntryCreate(
            description="Venda",
            entry_type="income",
            amount=Decimal("0"),
            due_date=date(2026, 8, 1),
        )


def test_financial_values_keep_decimal_precision() -> None:
    account = AccountCreate(
        name="Conta principal",
        account_type="bank",
        opening_balance=Decimal("1234.56"),
    )
    entry = EntryCreate(
        description="Assinatura",
        entry_type="expense",
        amount=Decimal("19.90"),
        due_date=date(2026, 8, 10),
    )
    assert account.opening_balance == Decimal("1234.56")
    assert entry.amount == Decimal("19.90")

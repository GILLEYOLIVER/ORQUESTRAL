from decimal import Decimal

import pytest

from app.modules.crm.sales_governance_service import (
    SalesGovernanceError,
    progress_percentage,
    validate_renewal_transition,
)


def test_progress_percentage_is_decimal_and_can_exceed_target() -> None:
    assert progress_percentage(Decimal("125"), Decimal("100")) == Decimal(
        "125.00"
    )
    assert progress_percentage(Decimal("1"), Decimal("3")) == Decimal("33.33")


def test_renewal_transition_follows_forward_only_state_machine() -> None:
    validate_renewal_transition("planned", "contacted")
    validate_renewal_transition("contacted", "negotiating")
    validate_renewal_transition("negotiating", "renewed")
    validate_renewal_transition("renewed", "renewed")

    with pytest.raises(SalesGovernanceError):
        validate_renewal_transition("renewed", "planned")

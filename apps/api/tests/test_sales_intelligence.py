from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.crm.sales_intelligence_service import (
    OpportunitySignal,
    evaluate_opportunity,
)


def test_recent_opportunity_with_published_quote_is_healthy() -> None:
    insight = evaluate_opportunity(
        OpportunitySignal(
            opportunity_id=uuid4(),
            title="Expansão empresarial",
            amount=Decimal("10000"),
            probability=80,
            expected_close_date=date(2026, 8, 30),
            assigned_user_id=uuid4(),
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
            last_activity_at=datetime(2026, 7, 21, tzinfo=UTC),
            activity_count=4,
            has_proposal=True,
            has_published_quote=True,
            has_accepted_quote=False,
        ),
        today=date(2026, 7, 23),
    )

    assert insight.health_level == "healthy"
    assert insight.health_score == 87
    assert insight.forecast_category == "commit"
    assert insight.weighted_amount == Decimal("8000.00")
    assert "proposta publicada" in " ".join(insight.reasons).lower()


def test_stale_overdue_opportunity_is_critical_and_explained() -> None:
    insight = evaluate_opportunity(
        OpportunitySignal(
            opportunity_id=uuid4(),
            title="Negócio sem acompanhamento",
            amount=Decimal("0"),
            probability=20,
            expected_close_date=date(2026, 7, 1),
            assigned_user_id=None,
            created_at=datetime(2026, 5, 1, tzinfo=UTC),
            last_activity_at=None,
            activity_count=0,
            has_proposal=False,
            has_published_quote=False,
            has_accepted_quote=False,
        ),
        today=date(2026, 7, 23),
    )

    assert insight.health_level == "critical"
    assert insight.health_score == 0
    assert insight.forecast_category == "pipeline"
    assert "Revisar a data prevista" in insight.next_best_action
    assert len(insight.reasons) >= 4

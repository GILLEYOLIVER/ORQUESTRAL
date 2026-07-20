from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.marketing.schemas import CampaignCreate, JourneyStepCreate


def test_campaign_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        CampaignCreate(
            name="Lancamento",
            channel="email",
            start_at=datetime(2026, 8, 10, tzinfo=UTC),
            end_at=datetime(2026, 8, 9, tzinfo=UTC),
        )


def test_marketing_defaults_and_journey_step() -> None:
    campaign = CampaignCreate(name="  Boas-vindas  ", channel="whatsapp")
    step = JourneyStepCreate(name="Aguardar um dia", action_type="wait", position=0)
    assert campaign.name == "Boas-vindas"
    assert campaign.status == "draft"
    assert campaign.budget_cents == 0
    assert step.configuration == {}

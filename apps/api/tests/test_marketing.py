from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.marketing.audience_schemas import MarketingAudienceCreate
from app.modules.marketing.governance_routes import _inside_window
from app.modules.marketing.governance_schemas import MarketingContactPolicyUpsert
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


def test_dynamic_audience_requires_segment() -> None:
    with pytest.raises(ValidationError):
        MarketingAudienceCreate(name="Clientes ativos", kind="dynamic")


def test_static_audience_rejects_segment() -> None:
    with pytest.raises(ValidationError):
        MarketingAudienceCreate(
            name="Lista manual",
            kind="static",
            segment_id="f9c76ed5-146d-4e31-84f0-cbc19f318f9e",
        )


def test_contact_policy_rejects_weekly_below_daily() -> None:
    with pytest.raises(ValidationError):
        MarketingContactPolicyUpsert(channel="email", daily_limit=5, weekly_limit=4)


def test_contact_policy_rejects_invalid_timezone() -> None:
    with pytest.raises(ValidationError):
        MarketingContactPolicyUpsert(channel="sms", timezone="Invalid/Timezone")


def test_contact_window_supports_overnight_period() -> None:
    from datetime import time

    assert _inside_window(time(23), time(22), time(6))
    assert _inside_window(time(5), time(22), time(6))
    assert not _inside_window(time(12), time(22), time(6))

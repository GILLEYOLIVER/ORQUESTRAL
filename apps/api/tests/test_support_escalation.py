from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.modules.support.escalation_schemas import (
    SupportBusinessCalendarCreate,
    SupportEscalationPolicyCreate,
)
from app.modules.support.escalation_service import calendar_is_open, escalation_phase


def test_escalation_phase_warns_then_breaches() -> None:
    now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    assert (
        escalation_phase(
            deadline=now + timedelta(minutes=20),
            now=now,
            warning_minutes_before=30,
        )
        == "warning"
    )
    assert (
        escalation_phase(
            deadline=now - timedelta(seconds=1),
            now=now,
            warning_minutes_before=30,
        )
        == "breach"
    )
    assert (
        escalation_phase(
            deadline=now + timedelta(hours=2),
            now=now,
            warning_minutes_before=30,
        )
        is None
    )


def test_calendar_respects_timezone_shifts_and_holidays() -> None:
    schedule = {
        "mon": [{"start": "09:00:00", "end": "18:00:00"}],
    }
    open_moment = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)
    assert calendar_is_open(
        weekly_schedule=schedule,
        holidays=[],
        timezone_name="America/Sao_Paulo",
        moment=open_moment,
    )
    assert not calendar_is_open(
        weekly_schedule=schedule,
        holidays=["2026-07-27"],
        timezone_name="America/Sao_Paulo",
        moment=open_moment,
    )


def test_calendar_and_policy_reject_unsafe_configuration() -> None:
    with pytest.raises(ValidationError):
        SupportBusinessCalendarCreate(
            name="Inválido",
            weekly_schedule={
                "mon": [
                    {"start": "09:00", "end": "13:00"},
                    {"start": "12:00", "end": "18:00"},
                ]
            },
        )
    with pytest.raises(ValidationError):
        SupportEscalationPolicyCreate(
            name="Sem fila",
            sla_policy_id="00000000-0000-0000-0000-000000000001",
            calendar_id="00000000-0000-0000-0000-000000000002",
            action="reassign_queue",
        )

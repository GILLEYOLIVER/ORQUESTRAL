from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.agents.dispatch_execution import (
    dispatch_status_from_tool_states,
    select_dispatch_execution_mode,
)
from app.modules.agents.runtime_schemas import AgentScheduleCreate


def test_shadow_mode_never_promotes_to_live() -> None:
    assert (
        select_dispatch_execution_mode(
            requested_mode="shadow", canary_percentage=100, fingerprint="dispatch-a"
        )
        == "shadow"
    )


def test_live_canary_boundaries_are_safe_and_deterministic() -> None:
    assert (
        select_dispatch_execution_mode(
            requested_mode="live", canary_percentage=0, fingerprint="dispatch-a"
        )
        == "shadow"
    )
    assert (
        select_dispatch_execution_mode(
            requested_mode="live", canary_percentage=100, fingerprint="dispatch-a"
        )
        == "live"
    )
    first = select_dispatch_execution_mode(
        requested_mode="live", canary_percentage=35, fingerprint="dispatch-stable"
    )
    second = select_dispatch_execution_mode(
        requested_mode="live", canary_percentage=35, fingerprint="dispatch-stable"
    )
    assert first == second


@pytest.mark.parametrize(
    ("mode", "states", "denied", "expected"),
    [
        ("shadow", ["simulated"], False, "simulated"),
        ("live", ["completed"], False, "completed"),
        ("live", ["awaiting_confirmation"], False, "awaiting_approval"),
        ("live", ["completed", "failed"], False, "failed"),
        ("live", ["completed"], True, "failed"),
        ("live", [], False, "failed"),
    ],
)
def test_dispatch_terminal_state_is_fail_closed(
    mode: str, states: list[str], denied: bool, expected: str
) -> None:
    assert (
        dispatch_status_from_tool_states(execution_mode=mode, states=states, denied=denied)
        == expected
    )


def test_tool_arguments_must_belong_to_an_authorized_tool() -> None:
    with pytest.raises(ValidationError):
        AgentScheduleCreate(
            schedule_key="daily.summary",
            name="Resumo diário",
            objective="Consultar o resumo da empresa",
            cadence_minutes=60,
            required_tool_keys=["orkestral.company.summary"],
            tool_arguments={"orkestral.workflow.status": {}},
        )

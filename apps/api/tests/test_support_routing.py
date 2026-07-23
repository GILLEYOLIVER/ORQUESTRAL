from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.support.routing_schemas import SupportAgentCapacityUpsert
from app.modules.support.routing_service import (
    RoutingCandidateInput,
    score_routing_candidate,
)


def test_routing_score_is_deterministic_and_explainable() -> None:
    skill_id = uuid4()
    candidate = RoutingCandidateInput(
        status="available",
        max_active_tickets=10,
        active_tickets=2,
        primary_queue_matches=True,
        languages=("pt-br",),
        accepted_channels=("whatsapp",),
        skill_levels={skill_id: 4},
    )

    first = score_routing_candidate(
        candidate,
        channel="whatsapp",
        language_code="pt-br",
        required_skill_ids=(skill_id,),
    )
    second = score_routing_candidate(
        candidate,
        channel="whatsapp",
        language_code="pt-br",
        required_skill_ids=(skill_id,),
    )

    assert first == second
    assert first is not None
    score, reasons = first
    assert score == 92
    assert "Habilidade compatível no nível 4" in reasons
    assert "Carga atual de 2/10" in reasons


def test_routing_rejects_capacity_channel_and_missing_skill() -> None:
    skill_id = uuid4()
    full = RoutingCandidateInput(
        status="available",
        max_active_tickets=2,
        active_tickets=2,
        primary_queue_matches=False,
        languages=("pt-br",),
        accepted_channels=("email",),
        skill_levels={},
    )
    assert (
        score_routing_candidate(
            full,
            channel="whatsapp",
            language_code="pt-br",
            required_skill_ids=(skill_id,),
        )
        is None
    )


def test_agent_configuration_normalizes_and_rejects_duplicate_skills() -> None:
    skill_id = uuid4()
    payload = SupportAgentCapacityUpsert(
        languages=[" PT-BR ", "pt-br"],
        accepted_channels=["web", "web", "email"],
    )
    assert payload.languages == ["pt-br"]
    assert payload.accepted_channels == ["web", "email"]

    with pytest.raises(ValidationError):
        SupportAgentCapacityUpsert(
            skills=[
                {"skill_id": skill_id, "proficiency": 3},
                {"skill_id": skill_id, "proficiency": 4},
            ]
        )

from app.modules.support.agent_handoff_service import decide_support_action


def test_urgent_or_breached_ticket_requires_human() -> None:
    assert decide_support_action(
        priority="urgent", breached=False, interaction_count=4, citation_count=2
    ).recommendation == "human_handoff"
    assert decide_support_action(
        priority="normal", breached=True, interaction_count=4, citation_count=2
    ).recommendation == "human_handoff"


def test_agent_never_recommends_response_without_context_and_citation() -> None:
    assert decide_support_action(
        priority="normal", breached=False, interaction_count=0, citation_count=2
    ).recommendation == "request_information"
    assert decide_support_action(
        priority="normal", breached=False, interaction_count=2, citation_count=0
    ).recommendation == "request_information"


def test_agent_recommends_response_only_with_authorized_evidence() -> None:
    decision = decide_support_action(
        priority="high", breached=False, interaction_count=2, citation_count=1
    )
    assert decision.recommendation == "respond"
    assert decision.reason_code == "authorized_context_ready"


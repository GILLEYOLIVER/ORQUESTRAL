from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.support.schemas import (
    SupportInteractionCreate,
    SupportTicketCreate,
    SupportTicketUpdate,
)


def test_support_ticket_normalizes_human_input() -> None:
    ticket = SupportTicketCreate(
        subject="  Erro   ao emitir relatorio  ",
        description="  O relatorio nao conclui.  ",
        priority="high",
    )

    assert ticket.subject == "Erro ao emitir relatorio"
    assert ticket.description == "O relatorio nao conclui."
    assert ticket.channel == "web"


def test_support_payloads_reject_empty_changes_and_messages() -> None:
    with pytest.raises(ValidationError):
        SupportTicketUpdate()
    with pytest.raises(ValidationError):
        SupportInteractionCreate(message="   ")

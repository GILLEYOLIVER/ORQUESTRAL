from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.support.engagement_models import SupportResponseCitation
from app.modules.support.models import SupportInteraction, SupportTicket


@dataclass(frozen=True)
class SupportAgentDecision:
    recommendation: str
    reason_code: str


def decide_support_action(
    *, priority: str, breached: bool, interaction_count: int, citation_count: int
) -> SupportAgentDecision:
    if breached or priority == "urgent":
        return SupportAgentDecision("human_handoff", "sla_or_priority_risk")
    if interaction_count == 0:
        return SupportAgentDecision("request_information", "context_incomplete")
    if citation_count == 0:
        return SupportAgentDecision("request_information", "knowledge_not_cited")
    return SupportAgentDecision("respond", "authorized_context_ready")


async def authorized_context(
    database: AsyncSession, *, company_id: UUID, ticket: SupportTicket
) -> tuple[list[dict[str, str]], int, int]:
    interaction_ids = list(
        await database.scalars(
            select(SupportInteraction.id)
            .where(
                SupportInteraction.company_id == company_id,
                SupportInteraction.ticket_id == ticket.id,
            )
            .order_by(SupportInteraction.created_at.desc())
            .limit(10)
        )
    )
    citation_count = int(
        await database.scalar(
            select(func.count(SupportResponseCitation.id)).where(
                SupportResponseCitation.company_id == company_id,
                SupportResponseCitation.ticket_id == ticket.id,
            )
        )
        or 0
    )
    refs = [{"type": "interaction", "id": str(item_id)} for item_id in interaction_ids]
    return refs, len(interaction_ids), citation_count


from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.sales_governance_schemas import (
    OpportunityTerritoryAssignment,
    RenewalPlanCreate,
    RenewalPlanResponse,
    RenewalStatus,
    RenewalStatusUpdate,
    SalesGoalCreate,
    SalesGoalResponse,
    SalesGovernanceDashboard,
    TerritoryCreate,
    TerritoryResponse,
)
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event

MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")
RENEWAL_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"contacted", "lost"},
    "contacted": {"negotiating", "lost"},
    "negotiating": {"renewed", "lost"},
    "renewed": set(),
    "lost": set(),
}


class SalesGovernanceError(RuntimeError):
    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def progress_percentage(progress: Decimal, target: Decimal) -> Decimal:
    if target <= 0:
        return Decimal("0.00")
    return (progress * Decimal(100) / target).quantize(
        PERCENT,
        rounding=ROUND_HALF_UP,
    )


def validate_renewal_transition(current: str, target: RenewalStatus) -> None:
    if current == target:
        return
    if target not in RENEWAL_TRANSITIONS.get(current, set()):
        raise SalesGovernanceError(
            f"A renovação não pode avançar de {current} para {target}.",
            status_code=409,
        )


async def _ensure_user(
    database: AsyncSession,
    *,
    company_id: UUID,
    user_id: UUID | None,
) -> None:
    if user_id is None:
        return
    exists = await database.scalar(
        text(
            """
            SELECT EXISTS (
              SELECT 1
              FROM company_memberships
              WHERE company_id = :company_id
                AND user_id = :user_id
                AND status = 'active'
            )
            """
        ),
        {"company_id": company_id, "user_id": user_id},
    )
    if not exists:
        raise SalesGovernanceError(
            "A pessoa responsável não pertence à empresa atual."
        )


def _territory_response(row: Any) -> TerritoryResponse:
    return TerritoryResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        region_code=row.region_code,
        owner_user_id=row.owner_user_id,
        status=row.status,
        open_opportunity_count=int(row.open_opportunity_count),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_territories(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[TerritoryResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT territory.*,
                       (
                         SELECT COUNT(*)
                         FROM crm_opportunities AS opportunity
                         WHERE opportunity.company_id = :company_id
                           AND opportunity.territory_id = territory.id
                           AND opportunity.status = 'open'
                           AND opportunity.deleted_at IS NULL
                       ) AS open_opportunity_count
                FROM crm_sales_territories AS territory
                WHERE territory.company_id = :company_id
                ORDER BY territory.status, territory.name, territory.id
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [_territory_response(row) for row in rows]


async def create_territory(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: TerritoryCreate,
) -> TerritoryResponse:
    await _ensure_user(
        database,
        company_id=company_id,
        user_id=payload.owner_user_id,
    )
    territory_id = uuid4()
    try:
        row = (
            await database.execute(
                text(
                    """
                    INSERT INTO crm_sales_territories (
                      id, company_id, name, description, region_code,
                      owner_user_id, created_by_user_id
                    )
                    VALUES (
                      :id, :company_id, :name, :description, :region_code,
                      :owner_user_id, :actor_user_id
                    )
                    RETURNING *, 0::bigint AS open_opportunity_count
                    """
                ),
                {
                    "id": territory_id,
                    "company_id": company_id,
                    "name": payload.name.strip(),
                    "description": payload.description,
                    "region_code": payload.region_code,
                    "owner_user_id": payload.owner_user_id,
                    "actor_user_id": actor_user_id,
                },
            )
        ).one()
    except IntegrityError as error:
        await database.rollback()
        raise SalesGovernanceError(
            "Já existe um território com esse nome.",
            status_code=409,
        ) from error
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.sales_territory.created",
        target_type="crm_sales_territory",
        target_id=territory_id,
        details={"region_code": payload.region_code},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.sales_territory.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"territory_id": str(territory_id)},
        ),
    )
    await database.commit()
    return _territory_response(row)


async def assign_opportunity_territory(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    opportunity_id: UUID,
    payload: OpportunityTerritoryAssignment,
) -> TerritoryResponse | None:
    territory: Any | None = None
    if payload.territory_id is not None:
        territory = (
            await database.execute(
                text(
                    """
                    SELECT territory.*,
                           0::bigint AS open_opportunity_count
                    FROM crm_sales_territories AS territory
                    WHERE territory.company_id = :company_id
                      AND territory.id = :territory_id
                      AND territory.status = 'active'
                    """
                ),
                {
                    "company_id": company_id,
                    "territory_id": payload.territory_id,
                },
            )
        ).one_or_none()
        if territory is None:
            raise SalesGovernanceError("Território ativo não encontrado.")
    updated = (
        await database.execute(
            text(
                """
                UPDATE crm_opportunities
                SET territory_id = :territory_id, updated_at = now()
                WHERE company_id = :company_id
                  AND id = :opportunity_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {
                "company_id": company_id,
                "opportunity_id": opportunity_id,
                "territory_id": payload.territory_id,
            },
        )
    ).one_or_none()
    if updated is None:
        raise SalesGovernanceError(
            "Oportunidade não encontrada.",
            status_code=404,
        )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.opportunity.territory_assigned",
        target_type="crm_opportunity",
        target_id=opportunity_id,
        details={
            "territory_id": (
                str(payload.territory_id)
                if payload.territory_id is not None
                else None
            )
        },
    )
    await database.commit()
    return _territory_response(territory) if territory is not None else None


async def _goal_rows(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[Any]:
    return list(
        (
            await database.execute(
                text(
                    """
                    SELECT goal.*, territory.name AS territory_name,
                           CASE goal.metric
                             WHEN 'revenue' THEN (
                               SELECT COALESCE(SUM(opportunity.amount), 0)
                               FROM crm_opportunities AS opportunity
                               WHERE opportunity.company_id = :company_id
                                 AND opportunity.status = 'won'
                                 AND opportunity.deleted_at IS NULL
                                 AND opportunity.closed_at::date
                                     BETWEEN goal.period_start AND goal.period_end
                                 AND (
                                   goal.territory_id IS NULL
                                   OR opportunity.territory_id = goal.territory_id
                                 )
                             )
                             WHEN 'won_opportunities' THEN (
                               SELECT COUNT(*)::numeric
                               FROM crm_opportunities AS opportunity
                               WHERE opportunity.company_id = :company_id
                                 AND opportunity.status = 'won'
                                 AND opportunity.deleted_at IS NULL
                                 AND opportunity.closed_at::date
                                     BETWEEN goal.period_start AND goal.period_end
                                 AND (
                                   goal.territory_id IS NULL
                                   OR opportunity.territory_id = goal.territory_id
                                 )
                             )
                             ELSE (
                               SELECT COUNT(*)::numeric
                               FROM crm_accounts AS account
                               WHERE account.company_id = :company_id
                                 AND account.deleted_at IS NULL
                                 AND account.created_at::date
                                     BETWEEN goal.period_start AND goal.period_end
                             )
                           END AS progress_value
                    FROM crm_sales_goals AS goal
                    LEFT JOIN crm_sales_territories AS territory
                      ON territory.id = goal.territory_id
                     AND territory.company_id = :company_id
                    WHERE goal.company_id = :company_id
                    ORDER BY goal.period_end, goal.name, goal.id
                    """
                ),
                {"company_id": company_id},
            )
        ).all()
    )


def _goal_response(row: Any) -> SalesGoalResponse:
    progress = Decimal(row.progress_value).quantize(
        MONEY,
        rounding=ROUND_HALF_UP,
    )
    target = Decimal(row.target_value).quantize(MONEY)
    return SalesGoalResponse(
        id=row.id,
        name=row.name,
        metric=row.metric,
        period_start=row.period_start,
        period_end=row.period_end,
        target_value=target,
        progress_value=progress,
        progress_percent=progress_percentage(progress, target),
        territory_id=row.territory_id,
        territory_name=row.territory_name,
        owner_user_id=row.owner_user_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_sales_goals(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[SalesGoalResponse]:
    return [_goal_response(row) for row in await _goal_rows(database, company_id=company_id)]


async def create_sales_goal(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: SalesGoalCreate,
) -> SalesGoalResponse:
    if payload.period_end < payload.period_start:
        raise SalesGovernanceError("O fim da meta deve ocorrer após o início.")
    if payload.metric == "new_accounts" and payload.territory_id is not None:
        raise SalesGovernanceError(
            "Metas de novas contas devem abranger a empresa inteira."
        )
    await _ensure_user(
        database,
        company_id=company_id,
        user_id=payload.owner_user_id,
    )
    if payload.territory_id is not None:
        exists = await database.scalar(
            text(
                """
                SELECT EXISTS (
                  SELECT 1 FROM crm_sales_territories
                  WHERE company_id = :company_id
                    AND id = :territory_id
                    AND status = 'active'
                )
                """
            ),
            {
                "company_id": company_id,
                "territory_id": payload.territory_id,
            },
        )
        if not exists:
            raise SalesGovernanceError("Território ativo não encontrado.")
    goal_id = uuid4()
    await database.execute(
        text(
            """
            INSERT INTO crm_sales_goals (
              id, company_id, territory_id, owner_user_id, name, metric,
              period_start, period_end, target_value, created_by_user_id
            )
            VALUES (
              :id, :company_id, :territory_id, :owner_user_id, :name, :metric,
              :period_start, :period_end, :target_value, :actor_user_id
            )
            """
        ),
        {
            "id": goal_id,
            "company_id": company_id,
            "territory_id": payload.territory_id,
            "owner_user_id": payload.owner_user_id,
            "name": payload.name.strip(),
            "metric": payload.metric,
            "period_start": payload.period_start,
            "period_end": payload.period_end,
            "target_value": payload.target_value,
            "actor_user_id": actor_user_id,
        },
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.sales_goal.created",
        target_type="crm_sales_goal",
        target_id=goal_id,
        details={
            "metric": payload.metric,
            "territory_id": (
                str(payload.territory_id)
                if payload.territory_id is not None
                else None
            ),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.sales_goal.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"goal_id": str(goal_id), "metric": payload.metric},
        ),
    )
    await database.commit()
    goals = await _goal_rows(database, company_id=company_id)
    return _goal_response(next(row for row in goals if row.id == goal_id))


async def _renewal_response(
    database: AsyncSession,
    *,
    company_id: UUID,
    renewal_id: UUID,
) -> RenewalPlanResponse:
    row = (
        await database.execute(
            text(
                """
                SELECT renewal.*, account.name AS account_name
                FROM crm_renewal_plans AS renewal
                JOIN crm_accounts AS account
                  ON account.id = renewal.account_id
                 AND account.company_id = :company_id
                WHERE renewal.company_id = :company_id
                  AND renewal.id = :renewal_id
                """
            ),
            {"company_id": company_id, "renewal_id": renewal_id},
        )
    ).one()
    return RenewalPlanResponse(
        id=row.id,
        account_id=row.account_id,
        account_name=str(row.account_name),
        source_opportunity_id=row.source_opportunity_id,
        owner_user_id=row.owner_user_id,
        title=row.title,
        renewal_date=row.renewal_date,
        expected_amount=Decimal(row.expected_amount).quantize(MONEY),
        status=row.status,
        last_note=row.last_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_renewal_plans(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[RenewalPlanResponse]:
    identifiers = (
        await database.execute(
            text(
                """
                SELECT id
                FROM crm_renewal_plans
                WHERE company_id = :company_id
                ORDER BY renewal_date, id
                """
            ),
            {"company_id": company_id},
        )
    ).scalars()
    return [
        await _renewal_response(
            database,
            company_id=company_id,
            renewal_id=renewal_id,
        )
        for renewal_id in identifiers
    ]


async def create_renewal_plan(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: RenewalPlanCreate,
) -> RenewalPlanResponse:
    await _ensure_user(
        database,
        company_id=company_id,
        user_id=payload.owner_user_id,
    )
    account_exists = await database.scalar(
        text(
            """
            SELECT EXISTS (
              SELECT 1 FROM crm_accounts
              WHERE company_id = :company_id
                AND id = :account_id
                AND deleted_at IS NULL
            )
            """
        ),
        {"company_id": company_id, "account_id": payload.account_id},
    )
    if not account_exists:
        raise SalesGovernanceError("Conta empresarial não encontrada.")
    if payload.source_opportunity_id is not None:
        source_exists = await database.scalar(
            text(
                """
                SELECT EXISTS (
                  SELECT 1 FROM crm_opportunities
                  WHERE company_id = :company_id
                    AND id = :opportunity_id
                    AND account_id = :account_id
                    AND status = 'won'
                    AND deleted_at IS NULL
                )
                """
            ),
            {
                "company_id": company_id,
                "opportunity_id": payload.source_opportunity_id,
                "account_id": payload.account_id,
            },
        )
        if not source_exists:
            raise SalesGovernanceError(
                "A oportunidade de origem deve estar ganha e pertencer à conta."
            )
    renewal_id = uuid4()
    await database.execute(
        text(
            """
            INSERT INTO crm_renewal_plans (
              id, company_id, account_id, source_opportunity_id,
              owner_user_id, title, renewal_date, expected_amount,
              created_by_user_id
            )
            VALUES (
              :id, :company_id, :account_id, :source_opportunity_id,
              :owner_user_id, :title, :renewal_date, :expected_amount,
              :actor_user_id
            )
            """
        ),
        {
            "id": renewal_id,
            "company_id": company_id,
            "account_id": payload.account_id,
            "source_opportunity_id": payload.source_opportunity_id,
            "owner_user_id": payload.owner_user_id,
            "title": payload.title.strip(),
            "renewal_date": payload.renewal_date,
            "expected_amount": payload.expected_amount,
            "actor_user_id": actor_user_id,
        },
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.renewal.created",
        target_type="crm_renewal_plan",
        target_id=renewal_id,
        details={
            "account_id": str(payload.account_id),
            "renewal_date": payload.renewal_date.isoformat(),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.renewal.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "renewal_id": str(renewal_id),
                "account_id": str(payload.account_id),
            },
        ),
    )
    await database.commit()
    return await _renewal_response(
        database,
        company_id=company_id,
        renewal_id=renewal_id,
    )


async def update_renewal_status(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    renewal_id: UUID,
    payload: RenewalStatusUpdate,
) -> RenewalPlanResponse:
    current = (
        await database.execute(
            text(
                """
                SELECT id, status
                FROM crm_renewal_plans
                WHERE company_id = :company_id AND id = :renewal_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "renewal_id": renewal_id},
        )
    ).one_or_none()
    if current is None:
        raise SalesGovernanceError(
            "Plano de renovação não encontrado.",
            status_code=404,
        )
    validate_renewal_transition(current.status, payload.status)
    await database.execute(
        text(
            """
            UPDATE crm_renewal_plans
            SET status = :status, last_note = :note, updated_at = now()
            WHERE company_id = :company_id AND id = :renewal_id
            """
        ),
        {
            "company_id": company_id,
            "renewal_id": renewal_id,
            "status": payload.status,
            "note": payload.note,
        },
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.renewal.status_changed",
        target_type="crm_renewal_plan",
        target_id=renewal_id,
        details={"from": current.status, "to": payload.status},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"crm.renewal.{payload.status}",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"renewal_id": str(renewal_id), "status": payload.status},
        ),
    )
    await database.commit()
    return await _renewal_response(
        database,
        company_id=company_id,
        renewal_id=renewal_id,
    )


async def build_sales_governance_dashboard(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> SalesGovernanceDashboard:
    territories = await list_territories(database, company_id=company_id)
    goals = await list_sales_goals(database, company_id=company_id)
    renewals = await list_renewal_plans(database, company_id=company_id)
    open_renewals = [
        item for item in renewals if item.status not in {"renewed", "lost"}
    ]
    return SalesGovernanceDashboard(
        generated_at=datetime.now(UTC),
        active_territory_count=sum(
            item.status == "active" for item in territories
        ),
        active_goal_count=sum(item.status == "active" for item in goals),
        open_renewal_count=len(open_renewals),
        renewal_pipeline_amount=sum(
            (item.expected_amount for item in open_renewals),
            Decimal(0),
        ).quantize(MONEY),
        territories=territories,
        goals=goals,
        renewals=renewals,
    )

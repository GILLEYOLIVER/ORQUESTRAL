from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.analytics.calculations import percentage_change, target_progress
from app.modules.analytics.models import AnalyticsIndicator, AnalyticsMeasurement
from app.modules.analytics.schemas import (
    AnalyticsOverviewResponse,
    AnalyticsSummary,
    IndicatorCreate,
    IndicatorResponse,
    IndicatorSnapshot,
    IndicatorUpdate,
    MeasurementCreate,
    MeasurementResponse,
    TargetStatus,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
CanViewAnalytics = Annotated[Principal, Depends(require_permission("analytics.view"))]
CanManageIndicators = Annotated[
    Principal, Depends(require_permission("analytics.indicators.manage"))
]
CanRecordMeasurements = Annotated[
    Principal, Depends(require_permission("analytics.measurements.manage"))
]


async def _indicator_or_404(
    database: DatabaseSession, company_id: UUID, indicator_id: UUID
) -> AnalyticsIndicator:
    indicator = await database.scalar(
        select(AnalyticsIndicator).where(
            AnalyticsIndicator.id == indicator_id,
            AnalyticsIndicator.company_id == company_id,
        )
    )
    if indicator is None:
        raise HTTPException(status_code=404, detail="Indicador nao encontrado.")
    return indicator


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def overview(
    principal: CanViewAnalytics,
    database: DatabaseSession,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    category: str | None = Query(default=None, max_length=80),
) -> AnalyticsOverviewResponse:
    context = get_request_context(principal)
    statement = select(AnalyticsIndicator).where(
        AnalyticsIndicator.company_id == context.company_id,
        AnalyticsIndicator.active.is_(True),
    )
    if category:
        statement = statement.where(AnalyticsIndicator.category == category)
    indicators = list(await database.scalars(statement.order_by(AnalyticsIndicator.name)))
    measurements: list[AnalyticsMeasurement] = []
    if indicators:
        values_statement = select(AnalyticsMeasurement).where(
            AnalyticsMeasurement.company_id == context.company_id,
            AnalyticsMeasurement.indicator_id.in_([item.id for item in indicators]),
        )
        if from_date:
            values_statement = values_statement.where(AnalyticsMeasurement.period_end >= from_date)
        if to_date:
            values_statement = values_statement.where(AnalyticsMeasurement.period_start <= to_date)
        measurements = list(
            await database.scalars(
                values_statement.order_by(
                    AnalyticsMeasurement.period_end.desc(),
                    AnalyticsMeasurement.created_at.desc(),
                )
            )
        )
    grouped: dict[UUID, list[AnalyticsMeasurement]] = {}
    for measurement in measurements:
        grouped.setdefault(measurement.indicator_id, []).append(measurement)
    snapshots: list[IndicatorSnapshot] = []
    achieved = 0
    behind = 0
    with_data = 0
    for indicator in indicators:
        values = grouped.get(indicator.id, [])
        latest = values[0] if values else None
        previous = values[1] if len(values) > 1 else None
        progress = None
        target_status: TargetStatus = "no_data"
        change = None
        if latest is not None:
            with_data += 1
            change = percentage_change(latest.value, previous.value if previous else None)
            progress, target_status = target_progress(
                latest.value, indicator.target_value, indicator.direction
            )
            achieved += int(target_status == "achieved")
            behind += int(target_status == "behind")
        snapshots.append(
            IndicatorSnapshot(
                **IndicatorResponse.model_validate(indicator, from_attributes=True).model_dump(),
                latest_value=latest.value if latest else None,
                previous_value=previous.value if previous else None,
                change_percent=change,
                target_progress_percent=progress,
                target_status=target_status,
                measured_at=latest.period_end if latest else None,
            )
        )
    return AnalyticsOverviewResponse(
        summary=AnalyticsSummary(
            active_indicators=len(indicators),
            indicators_with_data=with_data,
            targets_achieved=achieved,
            targets_behind=behind,
        ),
        indicators=snapshots,
        generated_at=datetime.now(UTC),
    )


@router.get("/indicators", response_model=list[IndicatorResponse])
async def list_indicators(
    principal: CanViewAnalytics,
    database: DatabaseSession,
    include_inactive: bool = False,
) -> list[IndicatorResponse]:
    context = get_request_context(principal)
    statement = select(AnalyticsIndicator).where(
        AnalyticsIndicator.company_id == context.company_id
    )
    if not include_inactive:
        statement = statement.where(AnalyticsIndicator.active.is_(True))
    rows = list(await database.scalars(statement.order_by(AnalyticsIndicator.name)))
    return [IndicatorResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/indicators", response_model=IndicatorResponse, status_code=status.HTTP_201_CREATED)
async def create_indicator(
    payload: IndicatorCreate,
    principal: CanManageIndicators,
    database: DatabaseSession,
) -> IndicatorResponse:
    context = get_request_context(principal)
    duplicate = await database.scalar(
        select(AnalyticsIndicator.id).where(
            AnalyticsIndicator.company_id == context.company_id,
            AnalyticsIndicator.code == payload.code,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Ja existe um indicador com este codigo.")
    indicator = AnalyticsIndicator(company_id=context.company_id, **payload.model_dump())
    database.add(indicator)
    await database.commit()
    await database.refresh(indicator)
    return IndicatorResponse.model_validate(indicator, from_attributes=True)


@router.patch("/indicators/{indicator_id}", response_model=IndicatorResponse)
async def update_indicator(
    indicator_id: UUID,
    payload: IndicatorUpdate,
    principal: CanManageIndicators,
    database: DatabaseSession,
) -> IndicatorResponse:
    context = get_request_context(principal)
    indicator = await _indicator_or_404(database, context.company_id, indicator_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(indicator, field, value)
    await database.commit()
    await database.refresh(indicator)
    return IndicatorResponse.model_validate(indicator, from_attributes=True)


@router.delete("/indicators/{indicator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_indicator(
    indicator_id: UUID,
    principal: CanManageIndicators,
    database: DatabaseSession,
) -> None:
    context = get_request_context(principal)
    indicator = await _indicator_or_404(database, context.company_id, indicator_id)
    indicator.active = False
    await database.commit()


@router.get("/indicators/{indicator_id}/measurements", response_model=list[MeasurementResponse])
async def list_measurements(
    indicator_id: UUID,
    principal: CanViewAnalytics,
    database: DatabaseSession,
    limit: int = Query(default=24, ge=1, le=120),
) -> list[MeasurementResponse]:
    context = get_request_context(principal)
    await _indicator_or_404(database, context.company_id, indicator_id)
    rows = list(
        await database.scalars(
            select(AnalyticsMeasurement)
            .where(
                AnalyticsMeasurement.company_id == context.company_id,
                AnalyticsMeasurement.indicator_id == indicator_id,
            )
            .order_by(
                AnalyticsMeasurement.period_end.desc(),
                AnalyticsMeasurement.created_at.desc(),
            )
            .limit(limit)
        )
    )
    return [MeasurementResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post(
    "/indicators/{indicator_id}/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement(
    indicator_id: UUID,
    payload: MeasurementCreate,
    principal: CanRecordMeasurements,
    database: DatabaseSession,
) -> MeasurementResponse:
    context = get_request_context(principal)
    await _indicator_or_404(database, context.company_id, indicator_id)
    duplicate = await database.scalar(
        select(AnalyticsMeasurement.id).where(
            AnalyticsMeasurement.indicator_id == indicator_id,
            AnalyticsMeasurement.period_start == payload.period_start,
            AnalyticsMeasurement.period_end == payload.period_end,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Ja existe uma medicao para este indicador e periodo."
        )
    measurement = AnalyticsMeasurement(
        company_id=context.company_id,
        indicator_id=indicator_id,
        recorded_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(measurement)
    await database.commit()
    await database.refresh(measurement)
    return MeasurementResponse.model_validate(measurement, from_attributes=True)

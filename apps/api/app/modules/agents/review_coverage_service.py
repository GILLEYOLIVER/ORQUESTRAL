from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import cast
from uuid import UUID

from app.modules.agents.runtime_models import AgentDispatchReviewSLAPolicy


@dataclass(frozen=True, slots=True)
class ReviewCoverageIssue:
    code: str
    message: str
    weekday: int | None = None
    hour: int | None = None
    user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ReviewCoverageReport:
    valid: bool
    minimum_coverage: int
    required_slots: int
    covered_slots: int
    issues: tuple[ReviewCoverageIssue, ...]


def _normalized_shifts(policy: AgentDispatchReviewSLAPolicy) -> list[dict[str, object]]:
    if policy.on_call_shifts:
        return list(policy.on_call_shifts)
    return [
        {
            "user_id": value,
            "weekdays": list(policy.on_call_weekdays),
            "start_hour": policy.on_call_start_hour,
            "end_hour": policy.on_call_end_hour,
        }
        for value in policy.on_call_user_ids
    ]


def review_policy_coverage(
    policy: AgentDispatchReviewSLAPolicy,
) -> ReviewCoverageReport:
    shifts = _normalized_shifts(policy)
    minimum = policy.minimum_coverage
    issues: list[ReviewCoverageIssue] = []
    scheduled: dict[tuple[int, int], set[UUID]] = {}
    intervals: dict[tuple[UUID, int], list[tuple[int, int]]] = {}

    for shift in shifts:
        user_id = UUID(str(shift["user_id"]))
        start_hour = int(str(shift["start_hour"]))
        end_hour = int(str(shift["end_hour"]))
        for weekday_value in cast(list[object], shift["weekdays"]):
            weekday = int(str(weekday_value))
            intervals.setdefault((user_id, weekday), []).append((start_hour, end_hour))
            for hour in range(start_hour, end_hour):
                scheduled.setdefault((weekday, hour), set()).add(user_id)

    for (user_id, weekday), windows in intervals.items():
        ordered = sorted(windows)
        for previous, current in pairwise(ordered):
            if current[0] < previous[1]:
                issues.append(
                    ReviewCoverageIssue(
                        code="overlapping_shift",
                        message=(
                            "O mesmo plantonista possui turnos sobrepostos "
                            f"no dia {weekday}, entre {current[0]:02d}:00 e "
                            f"{previous[1]:02d}:00."
                        ),
                        weekday=weekday,
                        hour=current[0],
                        user_id=user_id,
                    )
                )

    required_slots = 0
    covered_slots = 0
    for weekday in policy.on_call_weekdays:
        for hour in range(policy.on_call_start_hour, policy.on_call_end_hour):
            required_slots += 1
            coverage = len(scheduled.get((weekday, hour), set()))
            if coverage >= minimum:
                covered_slots += 1
            else:
                issues.append(
                    ReviewCoverageIssue(
                        code="minimum_coverage_missing",
                        message=(
                            f"Cobertura insuficiente no dia {weekday}, "
                            f"das {hour:02d}:00 às {hour + 1:02d}:00: "
                            f"{coverage} de {minimum} responsável(is)."
                        ),
                        weekday=weekday,
                        hour=hour,
                    )
                )

    for holiday in policy.holiday_calendar:
        if not holiday.get("coverage_required", False):
            continue
        holiday_weekday = __import__("datetime").date.fromisoformat(str(holiday["date"])).weekday()
        for hour in range(policy.on_call_start_hour, policy.on_call_end_hour):
            if len(scheduled.get((holiday_weekday, hour), set())) < minimum:
                issues.append(
                    ReviewCoverageIssue(
                        code="holiday_coverage_missing",
                        message=(
                            f"O feriado {holiday['name']} exige cobertura, "
                            "mas não possui responsáveis suficientes."
                        ),
                        weekday=holiday_weekday,
                        hour=hour,
                    )
                )
                break

    return ReviewCoverageReport(
        valid=not issues,
        minimum_coverage=minimum,
        required_slots=required_slots,
        covered_slots=covered_slots,
        issues=tuple(issues),
    )

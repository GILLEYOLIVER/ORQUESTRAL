from __future__ import annotations

from datetime import date, timedelta
from typing import Any

FIELD_BY_KEY = {
    "automation.executions": "automation_executions",
    "automation.success": "automation_success",
    "automation.failure": "automation_failure",
    "time_saved.minutes": "time_saved_minutes",
    "agent.uses": "agent_uses",
    "agent.tokens": "tokens",
    "agent.cost_usd": "ai_cost_usd",
    "integration.failures": "integration_failures",
    "users.active": "active_users",
    "documents.processed": "documents_processed",
    "approvals.pending": "pending_approvals",
}


def calculate_dashboard(
    rows: list[Any], agent_names: dict[str, str], start: date, end: date
) -> dict[str, Any]:
    totals = {field: 0.0 for field in FIELD_BY_KEY.values()}
    series: dict[date, dict[str, Any]] = {}
    cursor = start
    while cursor <= end:
        series[cursor] = {"date": cursor, **{field: 0.0 for field in FIELD_BY_KEY.values()}}
        cursor += timedelta(days=1)
    agents: dict[str, dict[str, Any]] = {}
    generated_at = None
    for row in rows:
        field = FIELD_BY_KEY.get(row.metric_key)
        if field is None:
            continue
        value = float(row.numeric_value)
        totals[field] += value
        if row.metric_date in series:
            series[row.metric_date][field] += value
        if row.agent_id is not None:
            agent_id = str(row.agent_id)
            item = agents.setdefault(
                agent_id,
                {
                    "id": agent_id,
                    "name": agent_names.get(agent_id, "Agente"),
                    "uses": 0,
                    "tokens": 0,
                    "cost_usd": 0.0,
                },
            )
            if row.metric_key == "agent.uses":
                item["uses"] += int(value)
            elif row.metric_key == "agent.tokens":
                item["tokens"] += int(value)
            elif row.metric_key == "agent.cost_usd":
                item["cost_usd"] += value
        if generated_at is None or row.generated_at > generated_at:
            generated_at = row.generated_at
    integer_fields = {
        "automation_executions",
        "automation_success",
        "automation_failure",
        "agent_uses",
        "tokens",
        "integration_failures",
        "active_users",
        "documents_processed",
        "pending_approvals",
    }
    for field in integer_fields:
        totals[field] = int(totals[field])
        for point in series.values():
            point[field] = int(point[field])
    top_agents = sorted(agents.values(), key=lambda item: (-item["uses"], item["name"]))[:10]
    return {
        "totals": totals,
        "series": list(series.values()),
        "top_agents": top_agents,
        "generated_at": generated_at,
    }

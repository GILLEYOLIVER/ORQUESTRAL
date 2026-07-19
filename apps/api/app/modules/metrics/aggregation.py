from __future__ import annotations

import asyncio
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

INSERTS = (
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, workflow_id, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'workflows', 'automation.executions', workflow_id, COUNT(*)::int, COUNT(*)::numeric
       FROM workflow_executions WHERE DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at), workflow_id""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, workflow_id, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'workflows', 'automation.success', workflow_id, COUNT(*)::int, COUNT(*)::numeric
       FROM workflow_executions WHERE status='success' AND DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at), workflow_id""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, workflow_id, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'workflows', 'automation.failure', workflow_id, COUNT(*)::int, COUNT(*)::numeric
       FROM workflow_executions WHERE status='error' AND DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at), workflow_id""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, workflow_id, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'workflows', 'time_saved.minutes', workflow_id, COUNT(*)::int, (COUNT(*) * 5)::numeric
       FROM workflow_executions WHERE status='success' AND DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at), workflow_id""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, agent_id, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'agents', 'agent.uses', agent_id, COUNT(*)::int, COUNT(*)::numeric
       FROM agent_usage_records WHERE DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at), agent_id""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, agent_id, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'agents', 'agent.tokens', agent_id, COUNT(*)::int, COALESCE(SUM(total_tokens),0)::numeric
       FROM agent_usage_records WHERE DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at), agent_id""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, agent_id, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'agents', 'agent.cost_usd', agent_id, COUNT(*)::int, (COALESCE(SUM(cost_microunits),0)::numeric / 1000000)
       FROM agent_usage_records WHERE DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at), agent_id""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, count_value, numeric_value)
       SELECT company_id, DATE(created_at), 'integrations', 'integration.failures', COUNT(*)::int, COUNT(*)::numeric
       FROM plugin_connection_tests WHERE success=false AND DATE(created_at) >= :start_date GROUP BY company_id, DATE(created_at)""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, count_value, numeric_value)
       SELECT selected_company_id, DATE(last_used_at), 'users', 'users.active', COUNT(DISTINCT user_id)::int, COUNT(DISTINCT user_id)::numeric
       FROM auth_sessions WHERE selected_company_id IS NOT NULL AND revoked_at IS NULL AND DATE(last_used_at) >= :start_date
       GROUP BY selected_company_id, DATE(last_used_at)""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, count_value, numeric_value)
       SELECT company_id, DATE(COALESCE(processed_at, created_at)), 'knowledge', 'documents.processed', COUNT(*)::int, COUNT(*)::numeric
       FROM knowledge_documents WHERE status='ready' AND DATE(COALESCE(processed_at, created_at)) >= :start_date
       GROUP BY company_id, DATE(COALESCE(processed_at, created_at))""",
    """INSERT INTO metric_daily_summaries (company_id, metric_date, module, metric_key, count_value, numeric_value)
       SELECT company_id, CURRENT_DATE, 'agents', 'approvals.pending', COUNT(*)::int, COUNT(*)::numeric
       FROM agent_tool_runs WHERE state='awaiting_confirmation' GROUP BY company_id""",
)


async def aggregate_metrics(*, days: int = 90) -> int:
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    start_date = date.today() - timedelta(days=max(1, min(days, 366)))
    rows = 0
    run_id = None
    try:
        async with engine.begin() as connection:
            run_id = (
                await connection.execute(
                    text(
                        "INSERT INTO metric_aggregation_runs (status) VALUES ('running') RETURNING id"
                    )
                )
            ).scalar_one()
            await connection.execute(
                text("DELETE FROM metric_daily_summaries WHERE metric_date >= :start_date"),
                {"start_date": start_date},
            )
            for statement in INSERTS:
                result = await connection.execute(text(statement), {"start_date": start_date})
                rows += max(0, result.rowcount or 0)
            await connection.execute(
                text(
                    "UPDATE metric_aggregation_runs SET status='success', rows_written=:rows, finished_at=now() WHERE id=:id"
                ),
                {"rows": rows, "id": run_id},
            )
        return rows
    except Exception as exc:
        if run_id is not None:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE metric_aggregation_runs SET status='error', error_summary=:error, finished_at=now() WHERE id=:id"
                    ),
                    {"error": str(exc)[:2000], "id": run_id},
                )
        raise
    finally:
        await engine.dispose()


def aggregate_metrics_sync() -> int:
    return asyncio.run(aggregate_metrics())

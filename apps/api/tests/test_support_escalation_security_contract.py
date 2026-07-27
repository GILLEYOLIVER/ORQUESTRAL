from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_support_escalation_tables_force_tenant_rls() -> None:
    migration = (
        ROOT
        / "app"
        / "migrations"
        / "versions"
        / "20260727_0108_support_sla_escalation_calendar.py"
    ).read_text(encoding="utf-8")

    assert migration.count("_rls(table)") == 1
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_company_id" in migration
    assert "uq_support_escalation_events_idempotency" in migration


def test_worker_schedule_runs_support_sla_maintenance_each_minute() -> None:
    worker = (ROOT.parent / "worker" / "worker" / "main.py").read_text(encoding="utf-8")
    assert '"orkestral.support.maintain_sla_escalations"' in worker
    assert '"schedule": 60.0' in worker

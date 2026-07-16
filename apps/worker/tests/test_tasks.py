from __future__ import annotations

from worker.tasks import diagnostic_ping


def test_diagnostic_task_can_run_eagerly() -> None:
    result = diagnostic_ping.apply()
    assert result.successful()
    assert result.result == {"status": "ok", "service": "orkestral-worker"}

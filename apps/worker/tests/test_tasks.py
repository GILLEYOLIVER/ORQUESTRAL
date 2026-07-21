from __future__ import annotations

from worker.tasks import (
    diagnostic_ping,
    maintain_agent_delegations_task,
    process_agent_delegation_task,
    purge_expired_agent_memories_task,
)


def test_diagnostic_task_can_run_eagerly() -> None:
    result = diagnostic_ping.apply()
    assert result.successful()
    assert result.result == {"status": "ok", "service": "orkestral-worker"}


def test_delegation_tasks_delegate_to_domain_services(monkeypatch) -> None:
    monkeypatch.setattr(
        "worker.tasks.process_delegation_sync",
        lambda value: {"status": "completed", "delegation_id": value},
    )
    monkeypatch.setattr(
        "worker.tasks.maintain_delegations_sync",
        lambda: {"expired": 1, "recovered": 2},
    )
    processed = process_agent_delegation_task.apply(args=["delegation-id"])
    maintained = maintain_agent_delegations_task.apply()
    assert processed.successful()
    assert processed.result == {"status": "completed", "delegation_id": "delegation-id"}
    assert maintained.result == {"status": "ok", "expired": 1, "recovered": 2}


def test_memory_maintenance_delegates_to_domain_service(monkeypatch) -> None:
    monkeypatch.setattr("worker.tasks.purge_expired_agent_memories_sync", lambda: 3)
    result = purge_expired_agent_memories_task.apply()
    assert result.successful()
    assert result.result == {"status": "ok", "deleted": 3}

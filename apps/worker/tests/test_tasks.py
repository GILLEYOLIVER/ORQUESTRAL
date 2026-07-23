from __future__ import annotations

from pytest import MonkeyPatch

from worker.tasks import (
    diagnostic_ping,
    dispatch_agent_runtime_task,
    maintain_agent_delegations_task,
    maintain_agent_dispatch_review_sla_task,
    maintain_agent_memory_reencryption_task,
    process_agent_delegation_task,
    purge_expired_agent_memories_task,
    run_due_agent_memory_response_exercises_task,
)


def test_diagnostic_task_can_run_eagerly() -> None:
    result = diagnostic_ping.apply()
    assert result.successful()
    assert result.result == {"status": "ok", "service": "orkestral-worker"}


def test_delegation_tasks_delegate_to_domain_services(monkeypatch: MonkeyPatch) -> None:
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


def test_agent_runtime_dispatch_delegates_to_domain_service(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "worker.tasks.maintain_agent_runtime_sync",
        lambda: {"scheduled": 1, "triggered": 2, "ready": 2, "blocked": 1},
    )
    result = dispatch_agent_runtime_task.apply()
    assert result.successful()
    assert result.result == {
        "status": "ok",
        "scheduled": 1,
        "triggered": 2,
        "ready": 2,
        "blocked": 1,
    }


def test_agent_review_sla_delegates_to_domain_service(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "worker.tasks.maintain_agent_dispatch_review_sla_sync",
        lambda: {"review_breaches": 2, "notifications": 3},
    )
    result = maintain_agent_dispatch_review_sla_task.apply()
    assert result.successful()
    assert result.result == {
        "status": "ok",
        "review_breaches": 2,
        "notifications": 3,
    }


def test_memory_maintenance_delegates_to_domain_service(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("worker.tasks.purge_expired_agent_memories_sync", lambda: 3)
    result = purge_expired_agent_memories_task.apply()
    assert result.successful()
    assert result.result == {"status": "ok", "deleted": 3}


def test_memory_response_schedule_delegates_to_domain_service(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "worker.tasks.maintain_due_agent_memory_response_exercises_sync",
        lambda: {"processed": 2, "passed": 1, "failed": 1},
    )
    result = run_due_agent_memory_response_exercises_task.apply()
    assert result.successful()
    assert result.result == {"status": "ok", "processed": 2, "passed": 1, "failed": 1}


def test_memory_reencryption_delegates_to_domain_service(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "worker.tasks.maintain_agent_memory_reencryption_jobs_sync",
        lambda: {
            "processed": 1,
            "completed": 1,
            "failed": 0,
            "rotated": 3,
            "purged": 2,
        },
    )
    result = maintain_agent_memory_reencryption_task.apply()
    assert result.successful()
    assert result.result == {
        "status": "ok",
        "processed": 1,
        "completed": 1,
        "failed": 0,
        "rotated": 3,
        "purged": 2,
    }

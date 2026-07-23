from datetime import UTC, datetime, timedelta

from app.modules.agents.dispatch_execution import is_dispatch_stale


def test_interrupted_dispatch_is_reconciled_only_after_runtime_and_grace() -> None:
    now = datetime.now(UTC)
    assert not is_dispatch_stale(
        started_at=now - timedelta(seconds=419),
        max_runtime_seconds=120,
        now=now,
    )
    assert is_dispatch_stale(
        started_at=now - timedelta(seconds=421),
        max_runtime_seconds=120,
        now=now,
    )

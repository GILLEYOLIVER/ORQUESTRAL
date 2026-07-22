from __future__ import annotations

import pytest

from app.modules.workflows.definition import build_default_definition
from app.modules.workflows.provider import FakeWorkflowProvider


@pytest.mark.asyncio
async def test_fake_provider_proves_canonical_workflow_portability() -> None:
    provider = FakeWorkflowProvider()
    definition = build_default_definition()
    reference = await provider.sync_workflow(
        external_workflow_id=None,
        name="Fluxo portavel",
        definition=definition,
        internal_webhook_path="private-entry",
    )
    assert reference.workflow_id.startswith("fake-workflow-")
    assert provider.workflows[reference.workflow_id]["definition"] == definition
    assert "n8n" not in str(provider.workflows[reference.workflow_id]).lower()

    active = await provider.activate_workflow(reference.workflow_id)
    assert active.workflow_id in provider.active
    result = await provider.trigger_workflow("private-entry", {"secret": "never-store"})
    assert result.output == {"accepted": True, "provider": "fake", "entrypoint": True}
    assert "never-store" not in str(provider.workflows)
    assert result.execution_id is not None
    assert await provider.cancel_execution(result.execution_id) is True
    assert result.execution_id in provider.canceled_executions

    await provider.deactivate_workflow(reference.workflow_id)
    assert reference.workflow_id not in provider.active

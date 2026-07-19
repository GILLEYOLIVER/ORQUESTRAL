from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.modules.agents.models import AgentTool
from app.modules.agents.providers.base import ModelMessage, ToolDefinition
from app.modules.agents.providers.local import LocalLanguageModelProvider
from app.modules.agents.tools import (
    ToolAccessError,
    ToolArgumentsError,
    assert_tool_access,
    validate_tool_arguments,
)


@pytest.mark.asyncio
async def test_local_provider_generates_answer_and_usage() -> None:
    provider = LocalLanguageModelProvider()
    result = await provider.generate(
        messages=[ModelMessage(role="user", content="Olá")],
        tools=[],
        model="orkestral-local",
        temperature=0.2,
        max_output_tokens=1024,
    )
    usage = await provider.calculate_usage(result)
    assert "Resposta local segura" in result.content
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens
    assert usage.cost_microunits == 0


@pytest.mark.asyncio
async def test_local_provider_extracts_controlled_tool_call() -> None:
    provider = LocalLanguageModelProvider()
    result = await provider.generate(
        messages=[
            ModelMessage(
                role="user", content='/ferramenta orkestral.workflow.status {"workflow_id":"abc"}'
            )
        ],
        tools=[
            ToolDefinition(
                key="orkestral.workflow.status",
                name="Status",
                description="Consulta status",
                input_schema={"type": "object"},
            )
        ],
        model="orkestral-local",
        temperature=0.2,
        max_output_tokens=1024,
    )
    assert result.tool_calls[0].key == "orkestral.workflow.status"
    assert result.tool_calls[0].arguments == {"workflow_id": "abc"}


def test_tool_arguments_reject_unknown_and_missing_fields() -> None:
    schema = {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    }
    with pytest.raises(ToolArgumentsError, match="obrigatórios"):
        validate_tool_arguments(schema, {})
    with pytest.raises(ToolArgumentsError, match="não permitidos"):
        validate_tool_arguments(schema, {"workflow_id": "id", "code": "not-allowed"})


def test_tool_access_blocks_disabled_or_unauthorized_tool() -> None:
    disabled = cast(AgentTool, SimpleNamespace(enabled=False, required_permission="agents.execute"))
    unauthorized = cast(
        AgentTool, SimpleNamespace(enabled=True, required_permission="workflows.configure")
    )
    with pytest.raises(ToolAccessError, match="desativada"):
        assert_tool_access(disabled, frozenset({"agents.execute"}))
    with pytest.raises(ToolAccessError, match=r"workflows\.configure"):
        assert_tool_access(unauthorized, frozenset({"agents.execute"}))


def test_agents_route_requires_authentication(client: TestClient) -> None:
    assert client.get("/agents").status_code == 401
    assert client.delete("/agents/00000000-0000-0000-0000-000000000000").status_code == 401

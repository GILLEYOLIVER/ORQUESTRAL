from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.agents.models import AgentTool
from app.modules.companies.models import Company
from app.modules.workflows.models import Workflow
from app.modules.workflows.provider import WorkflowProviderError, get_workflow_provider


class ToolAccessError(RuntimeError):
    pass


class ToolArgumentsError(RuntimeError):
    pass


class ToolExecutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BuiltinToolDefinition:
    key: str
    name: str
    description: str
    input_schema: dict[str, Any]
    required_permission: str
    risk_level: str = "low"
    is_sensitive: bool = False


BUILTIN_TOOLS = (
    BuiltinToolDefinition(
        "orkestral.company.summary",
        "Resumo da empresa",
        "Consulta nome, status, idioma e fuso da empresa atual.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        "agents.execute",
    ),
    BuiltinToolDefinition(
        "orkestral.workflow.status",
        "Consultar automação",
        "Consulta o estado de uma automação da empresa.",
        {
            "type": "object",
            "properties": {"workflow_id": {"type": "string"}},
            "required": ["workflow_id"],
            "additionalProperties": False,
        },
        "workflows.view",
    ),
    BuiltinToolDefinition(
        "orkestral.workflow.deactivate",
        "Desativar automação",
        "Desativa uma automação crítica após confirmação humana explícita.",
        {
            "type": "object",
            "properties": {"workflow_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["workflow_id", "reason"],
            "additionalProperties": False,
        },
        "workflows.configure",
        "high",
        True,
    ),
)
TOOL_CATALOG = {tool.key: tool for tool in BUILTIN_TOOLS}


def assert_tool_access(tool: AgentTool, permissions: frozenset[str]) -> None:
    if not tool.enabled:
        raise ToolAccessError("A ferramenta está desativada para este agente.")
    if tool.required_permission and tool.required_permission not in permissions:
        raise ToolAccessError(f"A ferramenta exige a permissão {tool.required_permission}.")


def validate_tool_arguments(schema: Mapping[str, Any], arguments: Mapping[str, Any]) -> None:
    if arguments.get("_invalid_json"):
        raise ToolArgumentsError("Os argumentos da ferramenta não formam um JSON válido.")
    required = schema.get("required") or []
    missing = [key for key in required if key not in arguments]
    if missing:
        raise ToolArgumentsError(f"Argumentos obrigatórios ausentes: {', '.join(missing)}.")
    raw_properties = schema.get("properties")
    properties: Mapping[str, Any] = raw_properties if isinstance(raw_properties, Mapping) else {}
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            raise ToolArgumentsError(f"Argumentos não permitidos: {', '.join(unknown)}.")
    expected_types: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, value in arguments.items():
        property_schema = properties.get(key)
        type_name = property_schema.get("type") if isinstance(property_schema, Mapping) else None
        python_type = expected_types.get(type_name) if isinstance(type_name, str) else None
        if python_type and not isinstance(value, python_type):
            raise ToolArgumentsError(f"O argumento {key} possui tipo inválido.")


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ToolArgumentsError(f"O argumento {field} deve ser um identificador válido.") from exc


async def execute_builtin_tool(
    *,
    tool_key: str,
    arguments: Mapping[str, Any],
    company_id: UUID,
    database: AsyncSession,
    settings: Settings,
) -> dict[str, Any]:
    if tool_key == "orkestral.company.summary":
        company = await database.scalar(
            select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
        )
        if company is None:
            raise ToolExecutionError("A empresa atual não foi encontrada.")
        return {
            "company_id": str(company.id),
            "name": company.trade_name,
            "status": company.status,
            "timezone": company.timezone,
            "language": company.language,
        }
    workflow_id = _uuid(arguments.get("workflow_id"), "workflow_id")
    workflow = await database.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.company_id == company_id)
    )
    if workflow is None:
        raise ToolExecutionError("A automação não foi encontrada nesta empresa.")
    if tool_key == "orkestral.workflow.status":
        return {
            "workflow_id": str(workflow.id),
            "name": workflow.name,
            "status": workflow.status,
            "sync_status": workflow.sync_status,
        }
    if tool_key == "orkestral.workflow.deactivate":
        provider = get_workflow_provider(settings)
        provider_workflow_id = workflow.provider_workflow_id or workflow.n8n_workflow_id
        if provider_workflow_id:
            try:
                await provider.deactivate_workflow(provider_workflow_id)
            except WorkflowProviderError as exc:
                raise ToolExecutionError(str(exc)) from exc
        workflow.status = "inactive"
        return {
            "workflow_id": str(workflow.id),
            "status": workflow.status,
            "reason": str(arguments.get("reason") or "")[:300],
        }
    raise ToolExecutionError("A ferramenta solicitada não possui executor registrado.")

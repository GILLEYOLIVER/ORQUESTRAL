from __future__ import annotations

import json
import re
from collections.abc import Sequence

from app.modules.agents.providers.base import (
    LanguageModelProvider,
    ModelMessage,
    ModelResult,
    ToolCall,
    ToolDefinition,
    UsageEstimate,
)

_TOOL_COMMAND = re.compile(
    r"^/(?:tool|ferramenta)\s+([a-z0-9_.-]+)(?:\s+(\{.*\}))?\s*$", re.I | re.S
)


def _tokens(value: str) -> int:
    return max(1, (len(value) + 3) // 4)


class LocalLanguageModelProvider(LanguageModelProvider):
    """Adaptador determinístico que não envia dados a terceiros."""

    async def generate(
        self,
        *,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolDefinition],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> ModelResult:
        del model, temperature
        user_content = next(
            (message.content for message in reversed(messages) if message.role == "user"), ""
        )
        input_tokens = sum(_tokens(message.content) for message in messages)
        command = _TOOL_COMMAND.match(user_content.strip())
        if command:
            tool_key = command.group(1)
            try:
                arguments = json.loads(command.group(2) or "{}")
            except json.JSONDecodeError:
                arguments = {"_invalid_json": True}
            if not isinstance(arguments, dict):
                arguments = {"_invalid_json": True}
            content = f"Solicitação de ferramenta recebida: {tool_key}."
            return ModelResult(
                content=content,
                tool_calls=(ToolCall(key=tool_key, arguments=arguments),),
                input_tokens=input_tokens,
                output_tokens=min(_tokens(content), max_output_tokens),
            )
        available = ", ".join(tool.key for tool in tools) or "nenhuma"
        content = f"Resposta local segura: recebi sua mensagem. Ferramentas disponíveis: {available}. Use /ferramenta <chave> <json> para solicitar uma ação controlada."
        return ModelResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=min(_tokens(content), max_output_tokens),
        )

    async def calculate_usage(self, result: ModelResult) -> UsageEstimate:
        return UsageEstimate(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.input_tokens + result.output_tokens,
            cost_microunits=0,
        )

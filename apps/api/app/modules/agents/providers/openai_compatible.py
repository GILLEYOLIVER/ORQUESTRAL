from __future__ import annotations

import json
from collections.abc import Sequence

import httpx

from app.modules.agents.providers.base import LanguageModelProvider, LanguageModelProviderError, ModelMessage, ModelResult, ToolCall, ToolDefinition, UsageEstimate


class OpenAICompatibleLanguageModelProvider(LanguageModelProvider):
    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: float, input_cost_per_million_microunits: int, output_cost_per_million_microunits: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._input_price = input_cost_per_million_microunits
        self._output_price = output_cost_per_million_microunits

    async def generate(self, *, messages: Sequence[ModelMessage], tools: Sequence[ToolDefinition], model: str, temperature: float, max_output_tokens: int) -> ModelResult:
        name_map = {tool.key.replace(".", "__"): tool.key for tool in tools}
        payload: dict[str, object] = {"model": model, "messages": [{"role": message.role, "content": message.content} for message in messages], "temperature": temperature, "max_tokens": max_output_tokens}
        if tools:
            payload["tools"] = [{"type": "function", "function": {"name": tool.key.replace(".", "__"), "description": tool.description, "parameters": tool.input_schema}} for tool in tools]
            payload["tool_choice"] = "auto"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/chat/completions", headers={"Authorization": f"Bearer {self._api_key}"}, json=payload)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LanguageModelProviderError("O provedor de linguagem não respondeu com um resultado válido.") from exc
        tool_calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {"_invalid_json": True}
            external_name = str(function.get("name") or "")
            if isinstance(arguments, dict) and external_name:
                tool_calls.append(ToolCall(key=name_map.get(external_name, external_name), arguments=arguments))
        usage = data.get("usage") or {}
        return ModelResult(content=str(message.get("content") or ""), tool_calls=tuple(tool_calls), input_tokens=max(0, int(usage.get("prompt_tokens") or 0)), output_tokens=max(0, int(usage.get("completion_tokens") or 0)), raw_metadata={"request_id": response.headers.get("x-request-id")})

    async def calculate_usage(self, result: ModelResult) -> UsageEstimate:
        cost = (result.input_tokens * self._input_price) // 1_000_000 + (result.output_tokens * self._output_price) // 1_000_000
        return UsageEstimate(input_tokens=result.input_tokens, output_tokens=result.output_tokens, total_tokens=result.input_tokens + result.output_tokens, cost_microunits=cost)

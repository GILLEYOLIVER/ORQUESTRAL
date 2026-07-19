from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

MessageRole = Literal["system", "user", "assistant", "tool"]


class LanguageModelProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    key: str
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    key: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelResult:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UsageEstimate:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_microunits: int


class LanguageModelProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolDefinition],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> ModelResult:
        raise NotImplementedError

    async def stream(
        self,
        *,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolDefinition],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> AsyncIterator[str]:
        result = await self.generate(
            messages=messages,
            tools=tools,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        if result.content:
            yield result.content

    @abstractmethod
    async def calculate_usage(self, result: ModelResult) -> UsageEstimate:
        raise NotImplementedError

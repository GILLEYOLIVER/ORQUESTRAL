from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter


@dataclass(frozen=True, slots=True)
class ModuleMenu:
    label: str
    path: str
    required_permission: str


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    code: str
    name: str
    version: str
    permissions: tuple[str, ...]
    routers: tuple[APIRouter, ...]
    menus: tuple[ModuleMenu, ...]
    configuration_schema: dict[str, Any] = field(default_factory=dict)
    events_published: tuple[str, ...] = ()
    events_consumed: tuple[str, ...] = ()
    migrations: tuple[str, ...] = ()


class ModuleRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ModuleDefinition] = {}

    def register(self, definition: ModuleDefinition) -> None:
        if definition.code in self._definitions:
            raise ValueError(f"Módulo já registrado: {definition.code}")
        self._definitions[definition.code] = definition

    def get(self, code: str) -> ModuleDefinition | None:
        return self._definitions.get(code)

    def installed(self) -> tuple[ModuleDefinition, ...]:
        return tuple(self._definitions[code] for code in sorted(self._definitions))

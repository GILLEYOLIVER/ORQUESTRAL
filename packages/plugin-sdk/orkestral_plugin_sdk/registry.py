from __future__ import annotations

import asyncio
from importlib.metadata import entry_points

from .contracts import ConnectionTestResult, Plugin
from .exceptions import (
    PluginExecutionError,
    PluginNotFoundError,
    PluginSDKError,
)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin, *, replace: bool = False) -> None:
        code = plugin.definition.code
        if code in self._plugins and not replace:
            raise PluginSDKError(f"O plugin {code} já está registrado.")
        self._plugins[code] = plugin

    def discover(self, group: str = "orkestral.plugins") -> None:
        for entry_point in entry_points(group=group):
            loaded = entry_point.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
            if not isinstance(plugin, Plugin):
                raise PluginSDKError(
                    f"O entry point {entry_point.name} não implementa o contrato Orkestral."
                )
            self.register(plugin)

    def get(self, code: str) -> Plugin:
        try:
            return self._plugins[code]
        except KeyError as exc:
            raise PluginNotFoundError(f"O plugin {code} não possui runtime de conexão.") from exc

    def installed(self) -> tuple[Plugin, ...]:
        return tuple(self._plugins.values())

    async def test_connection(
        self,
        code: str,
        credentials: dict[str, object],
        configuration: dict[str, object] | None = None,
        *,
        timeout_seconds: float = 10.0,
    ) -> ConnectionTestResult:
        plugin = self.get(code)
        plugin.validate_credentials(credentials)
        try:
            async with asyncio.timeout(timeout_seconds):
                return await plugin.test_connection(credentials, configuration)
        except PluginSDKError:
            raise
        except TimeoutError as exc:
            raise PluginExecutionError(
                "O teste do plugin excedeu o tempo limite de segurança."
            ) from exc
        except Exception as exc:
            raise PluginExecutionError(
                "O plugin falhou de forma isolada durante o teste de conexão."
            ) from exc

from __future__ import annotations

import asyncio
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    success: bool
    message: str


class PluginAdapterError(ValueError):
    pass


class PluginAdapter(ABC):
    @abstractmethod
    async def test_connection(self, values: dict[str, Any]) -> ConnectionTestResult:
        raise NotImplementedError


class HttpAdapter(PluginAdapter):
    async def test_connection(self, values: dict[str, Any]) -> ConnectionTestResult:
        url = str(values.get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            raise PluginAdapterError("Informe uma URL HTTP ou HTTPS válida.")
        headers = values.get("headers") or {}
        if not isinstance(headers, dict):
            raise PluginAdapterError("O campo headers deve ser um objeto.")
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url, headers={str(k): str(v) for k, v in headers.items()})
        if response.status_code >= 500:
            return ConnectionTestResult(False, f"O destino respondeu com HTTP {response.status_code}.")
        return ConnectionTestResult(True, f"Conexão HTTP validada com status {response.status_code}.")


class SmtpAdapter(PluginAdapter):
    async def test_connection(self, values: dict[str, Any]) -> ConnectionTestResult:
        host = str(values.get("host", "")).strip()
        if not host:
            raise PluginAdapterError("Informe o servidor SMTP.")
        port = int(values.get("port", 587))
        username = str(values.get("username", "")).strip()
        password = str(values.get("password", ""))
        use_tls = bool(values.get("use_tls", True))

        def connect() -> None:
            with smtplib.SMTP(host=host, port=port, timeout=5) as smtp:
                smtp.ehlo()
                if use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if username:
                    smtp.login(username, password)

        await asyncio.to_thread(connect)
        return ConnectionTestResult(True, "Conexão SMTP validada com sucesso.")


_ADAPTERS: dict[str, PluginAdapter] = {
    "api-rest": HttpAdapter(),
    "webhook": HttpAdapter(),
    "smtp": SmtpAdapter(),
}


def get_plugin_adapter(plugin_code: str) -> PluginAdapter:
    try:
        return _ADAPTERS[plugin_code]
    except KeyError as exc:
        raise PluginAdapterError(f"O plugin {plugin_code} não possui adaptador de conexão.") from exc

"""Deterministic HTTP contracts used only by the Phase 14 test environment."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import RLock
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


class ContractState:
    def __init__(self) -> None:
        self.lock = RLock()
        self.sequence = 0
        self.workflows: dict[str, dict[str, Any]] = {}

    def next_id(self, prefix: str) -> str:
        with self.lock:
            self.sequence += 1
            return f"{prefix}-{self.sequence}"


STATE = ContractState()


def runtime_dependencies() -> dict[str, bool]:
    endpoints = {
        "minio": "http://object-storage:9000/minio/health/live",
        "n8n": "http://n8n:5678/healthz",
    }
    result: dict[str, bool] = {}
    for name, endpoint in endpoints.items():
        try:
            with urlopen(endpoint, timeout=2) as response:  # noqa: S310
                result[name] = response.status < 400
        except OSError:
            result[name] = False
    return result


class ContractHandler(BaseHTTPRequestHandler):
    server_version = "OrkestralPhase14Contract/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {"value": value}

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            dependencies = runtime_dependencies()
            healthy = all(dependencies.values())
            self._json(
                HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "status": "ok" if healthy else "waiting",
                    "service": "phase14-contract",
                    "dependencies": dependencies,
                },
            )
            return
        if path == "/plugin/ping":
            self._json(HTTPStatus.OK, {"status": "ok", "adapter": "rest_api"})
            return
        if path == "/api/v1/workflows":
            with STATE.lock:
                rows = list(STATE.workflows.values())
            self._json(HTTPStatus.OK, {"data": rows, "nextCursor": None})
            return
        prefix = "/api/v1/workflows/"
        if path.startswith(prefix):
            workflow_id = path.removeprefix(prefix)
            with STATE.lock:
                workflow = STATE.workflows.get(workflow_id)
            if workflow is None:
                self._json(HTTPStatus.NOT_FOUND, {"message": "Workflow not found"})
                return
            self._json(HTTPStatus.OK, workflow)
            return
        self._json(HTTPStatus.NOT_FOUND, {"message": "Contract route not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._body()
        if path == "/api/v1/workflows":
            workflow_id = STATE.next_id("workflow")
            workflow = {
                **payload,
                "id": workflow_id,
                "versionId": STATE.next_id("version"),
                "active": False,
            }
            with STATE.lock:
                STATE.workflows[workflow_id] = workflow
            self._json(HTTPStatus.OK, workflow)
            return
        if path.endswith("/activate") or path.endswith("/deactivate"):
            action = path.rsplit("/", 1)[-1]
            workflow_id = path.removeprefix("/api/v1/workflows/").rsplit("/", 1)[0]
            with STATE.lock:
                workflow = STATE.workflows.get(workflow_id)
                if workflow is not None:
                    workflow["active"] = action == "activate"
                    workflow["versionId"] = STATE.next_id("version")
            if workflow is None:
                self._json(HTTPStatus.NOT_FOUND, {"message": "Workflow not found"})
                return
            self._json(HTTPStatus.OK, workflow)
            return
        if path.startswith("/webhook/"):
            self._json(
                HTTPStatus.OK,
                {
                    "executionId": STATE.next_id("execution"),
                    "status": "success",
                    "received": payload,
                },
            )
            return
        if path == "/v1/chat/completions":
            self._json(
                HTTPStatus.OK,
                {
                    "id": STATE.next_id("chat"),
                    "object": "chat.completion",
                    "model": str(payload.get("model") or "phase14-contract-model"),
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": "Resposta validada pelo contrato de IA da Fase 14.",
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 9,
                        "total_tokens": 21,
                    },
                },
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"message": "Contract route not found"})

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        prefix = "/api/v1/workflows/"
        if not path.startswith(prefix):
            self._json(HTTPStatus.NOT_FOUND, {"message": "Contract route not found"})
            return
        workflow_id = path.removeprefix(prefix)
        payload = self._body()
        with STATE.lock:
            previous = STATE.workflows.get(workflow_id)
            if previous is not None:
                previous.update(payload)
                previous["versionId"] = STATE.next_id("version")
                workflow = dict(previous)
            else:
                workflow = None
        if workflow is None:
            self._json(HTTPStatus.NOT_FOUND, {"message": "Workflow not found"})
            return
        self._json(HTTPStatus.OK, workflow)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 5678), ContractHandler).serve_forever()  # noqa: S104

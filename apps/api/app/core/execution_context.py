from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from uuid import UUID, uuid4

from app.core.tenancy import RequestContext


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    company_id: UUID
    actor_user_id: UUID | None
    correlation_id: UUID
    source: str
    environment: str

    @classmethod
    def from_request_context(
        cls,
        context: RequestContext,
        *,
        source: str,
        environment: str,
        correlation_id: UUID | None = None,
    ) -> ExecutionContext:
        return cls(
            company_id=context.company_id,
            actor_user_id=context.user_id,
            correlation_id=correlation_id or uuid4(),
            source=source,
            environment=environment,
        )

    def to_job_payload(self) -> dict[str, str | None]:
        values = asdict(self)
        return {key: str(value) if value is not None else None for key, value in values.items()}

    @classmethod
    def from_job_payload(cls, payload: dict[str, str | None]) -> ExecutionContext:
        company_id = payload.get("company_id")
        correlation_id = payload.get("correlation_id")
        source = payload.get("source")
        environment = payload.get("environment")
        if not company_id or not correlation_id or not source or not environment:
            raise ValueError("Contexto de execucao incompleto.")
        actor_user_id = payload.get("actor_user_id")
        return cls(
            company_id=UUID(company_id),
            actor_user_id=UUID(actor_user_id) if actor_user_id else None,
            correlation_id=UUID(correlation_id),
            source=source,
            environment=environment,
        )


_execution_context: ContextVar[ExecutionContext | None] = ContextVar(
    "orkestral_execution_context", default=None
)


def get_execution_context() -> ExecutionContext | None:
    return _execution_context.get()


def require_execution_context() -> ExecutionContext:
    context = get_execution_context()
    if context is None:
        raise RuntimeError("Operacao empresarial sem contexto de execucao.")
    return context


@contextmanager
def bind_execution_context(context: ExecutionContext) -> Iterator[ExecutionContext]:
    token: Token[ExecutionContext | None] = _execution_context.set(context)
    try:
        yield context
    finally:
        _execution_context.reset(token)

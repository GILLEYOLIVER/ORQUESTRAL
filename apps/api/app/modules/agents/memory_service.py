from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.resources import create_resources
from app.core.security import utc_now
from app.modules.agents.memory_models import AgentMemoryEntry, AgentMemoryPolicy
from app.modules.agents.models import AgentDataPolicy
from app.modules.agents.security import (
    CLASSIFICATION_RANK,
    protect_provider_text,
    scan_prompt_injection,
)
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError

DEFAULT_SCOPES = ["conversation", "task", "operational"]
DEFAULT_CLASSIFICATIONS = ["public", "internal"]


@dataclass(frozen=True, slots=True)
class AuthorizedMemoryContext:
    contents: tuple[str, ...]
    retrieved_fingerprints: tuple[str, ...]
    blocked_fingerprints: tuple[str, ...]


def memory_content_fingerprint(
    *,
    secret: str,
    company_id: UUID,
    agent_id: UUID,
    scope: str,
    subject_user_id: UUID | None,
    content: str,
) -> str:
    payload = f"{company_id}:{agent_id}:{scope}:{subject_user_id or '-'}:{content}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_consent_fingerprint(
    *, secret: str, company_id: UUID, agent_id: UUID, subject_user_id: UUID, reference: str
) -> str:
    payload = f"{company_id}:{agent_id}:{subject_user_id}:{reference}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_is_expired(memory: AgentMemoryEntry, *, now: datetime | None = None) -> bool:
    return memory.expires_at <= (now or utc_now())


def memory_policy_values(policy: AgentMemoryPolicy | None) -> dict[str, object]:
    if policy is None:
        return {
            "default_retention_days": 30,
            "max_retention_days": 365,
            "allowed_scopes": DEFAULT_SCOPES,
            "allowed_classifications": DEFAULT_CLASSIFICATIONS,
            "require_consent_for_user_scope": True,
            "retrieval_enabled": False,
            "max_retrieval_entries": 5,
        }
    return {
        "default_retention_days": policy.default_retention_days,
        "max_retention_days": policy.max_retention_days,
        "allowed_scopes": policy.allowed_scopes,
        "allowed_classifications": policy.allowed_classifications,
        "require_consent_for_user_scope": policy.require_consent_for_user_scope,
        "retrieval_enabled": policy.retrieval_enabled,
        "max_retrieval_entries": policy.max_retrieval_entries,
    }


async def retrieve_authorized_memories(
    database: AsyncSession,
    *,
    settings: Settings,
    company_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    provider: str,
    memory_policy: AgentMemoryPolicy | None,
    data_policy: AgentDataPolicy,
) -> AuthorizedMemoryContext:
    if memory_policy is None or not memory_policy.retrieval_enabled:
        return AuthorizedMemoryContext((), (), ())
    maximum_rank = CLASSIFICATION_RANK[data_policy.max_data_classification]
    allowed = [
        classification
        for classification in memory_policy.allowed_classifications
        if CLASSIFICATION_RANK[classification] <= maximum_rank
    ]
    if not allowed:
        return AuthorizedMemoryContext((), (), ())
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == company_id,
                AgentMemoryEntry.agent_id == agent_id,
                AgentMemoryEntry.expires_at > utc_now(),
                AgentMemoryEntry.classification.in_(allowed),
                or_(
                    AgentMemoryEntry.scope != "user",
                    AgentMemoryEntry.subject_user_id == user_id,
                ),
            )
            .order_by(AgentMemoryEntry.created_at.desc())
            .limit(memory_policy.max_retrieval_entries)
        )
    )
    vault = CredentialVault(settings.encryption_key)
    contents: list[str] = []
    retrieved: list[str] = []
    blocked: list[str] = []
    for row in rows:
        try:
            content = vault.decrypt(row.encrypted_content).get("content")
        except CredentialVaultError:
            blocked.append(row.content_fingerprint)
            continue
        if not isinstance(content, str):
            blocked.append(row.content_fingerprint)
            continue
        assessment = scan_prompt_injection(content)
        if assessment.detected:
            blocked.append(row.content_fingerprint)
            continue
        contents.append(protect_provider_text(data_policy, provider=provider, text=content)[0])
        retrieved.append(row.content_fingerprint)
    return AuthorizedMemoryContext(tuple(contents), tuple(retrieved), tuple(blocked))


async def purge_expired_agent_memories(database: AsyncSession, *, limit: int = 1_000) -> int:
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(AgentMemoryEntry.expires_at <= utc_now())
            .order_by(AgentMemoryEntry.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for row in rows:
        await database.delete(row)
    await database.commit()
    return len(rows)


async def _purge_expired_agent_memories_once(settings: Settings) -> int:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            return await purge_expired_agent_memories(database)
    finally:
        await resources.close()


def purge_expired_agent_memories_sync() -> int:
    import asyncio

    return asyncio.run(_purge_expired_agent_memories_once(get_settings()))

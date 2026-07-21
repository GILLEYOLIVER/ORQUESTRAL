from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.resources import create_resources
from app.core.security import utc_now
from app.modules.agents.coordination_models import AgentDelegation
from app.modules.agents.memory_models import (
    AgentMemoryEntry,
    AgentMemoryLegalHold,
    AgentMemoryPolicy,
    AgentMemoryPurposePolicy,
    AgentMemoryScopePolicy,
    AgentTaskMemoryAccessGrant,
)
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
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class SharedTaskMemoryItem:
    memory_id: UUID
    owner_agent_id: UUID
    classification: str
    purpose: str
    content: str
    truncated: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SharedTaskMemoryContext:
    items: tuple[SharedTaskMemoryItem, ...]
    total_characters: int
    blocked_items: int


def memory_content_fingerprint(
    *,
    secret: str,
    company_id: UUID,
    agent_id: UUID,
    scope: str,
    purpose: str,
    subject_user_id: UUID | None,
    content: str,
    task_delegation_id: UUID | None = None,
) -> str:
    payload = (
        f"{company_id}:{agent_id}:{scope}:{purpose}:{subject_user_id or '-'}:"
        f"{task_delegation_id or '-'}:{content}"
    ).encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_consent_fingerprint(
    *, secret: str, company_id: UUID, agent_id: UUID, subject_user_id: UUID, reference: str
) -> str:
    payload = f"{company_id}:{agent_id}:{subject_user_id}:{reference}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_legal_reference_fingerprint(
    *, secret: str, company_id: UUID, agent_id: UUID, delegation_id: UUID, reference: str
) -> str:
    payload = f"{company_id}:{agent_id}:{delegation_id}:{reference}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_access_revocation_fingerprint(
    *, secret: str, company_id: UUID, grant_id: UUID, reason: str
) -> str:
    payload = f"{company_id}:{grant_id}:{reason}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_is_expired(memory: AgentMemoryEntry, *, now: datetime | None = None) -> bool:
    return memory.expires_at <= (now or utc_now())


def estimate_memory_tokens(content: str) -> int:
    return max(1, (len(content) + 3) // 4)


def memory_policy_values(
    policy: AgentMemoryPolicy | None,
    scope_policies: Sequence[AgentMemoryScopePolicy] = (),
    purpose_policies: Sequence[AgentMemoryPurposePolicy] = (),
) -> dict[str, object]:
    if policy is None:
        return {
            "default_retention_days": 30,
            "max_retention_days": 365,
            "allowed_scopes": DEFAULT_SCOPES,
            "allowed_classifications": DEFAULT_CLASSIFICATIONS,
            "require_consent_for_user_scope": True,
            "retrieval_enabled": False,
            "max_retrieval_entries": 5,
            "max_context_tokens": 1000,
            "scope_policies": [
                {
                    "scope": scope,
                    "retention_days": 30,
                    "retrieval_enabled": True,
                }
                for scope in DEFAULT_SCOPES
            ],
            "purpose_policies": [
                {
                    "purpose": "operations",
                    "retention_days": 30,
                    "enabled": True,
                }
            ],
        }
    configured = {item.scope: item for item in scope_policies}
    effective_scopes = [
        {
            "scope": scope,
            "retention_days": configured[scope].retention_days
            if scope in configured
            else policy.default_retention_days,
            "retrieval_enabled": configured[scope].retrieval_enabled
            if scope in configured
            else True,
        }
        for scope in policy.allowed_scopes
    ]
    effective_purposes = [
        {
            "purpose": item.purpose,
            "retention_days": item.retention_days,
            "enabled": item.enabled,
        }
        for item in purpose_policies
    ] or [
        {
            "purpose": "operations",
            "retention_days": policy.default_retention_days,
            "enabled": True,
        }
    ]
    return {
        "default_retention_days": policy.default_retention_days,
        "max_retention_days": policy.max_retention_days,
        "allowed_scopes": policy.allowed_scopes,
        "allowed_classifications": policy.allowed_classifications,
        "require_consent_for_user_scope": policy.require_consent_for_user_scope,
        "retrieval_enabled": policy.retrieval_enabled,
        "max_retrieval_entries": policy.max_retrieval_entries,
        "max_context_tokens": policy.max_context_tokens,
        "scope_policies": effective_scopes,
        "purpose_policies": effective_purposes,
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
    scope_policies: Sequence[AgentMemoryScopePolicy],
    data_policy: AgentDataPolicy,
) -> AuthorizedMemoryContext:
    if memory_policy is None or not memory_policy.retrieval_enabled:
        return AuthorizedMemoryContext((), (), (), 0)
    maximum_rank = CLASSIFICATION_RANK[data_policy.max_data_classification]
    allowed = [
        classification
        for classification in memory_policy.allowed_classifications
        if CLASSIFICATION_RANK[classification] <= maximum_rank
    ]
    if not allowed:
        return AuthorizedMemoryContext((), (), (), 0)
    values = memory_policy_values(memory_policy, scope_policies)
    effective_scope_policies = cast(list[dict[str, object]], values["scope_policies"])
    retrieval_scopes = [
        str(item["scope"]) for item in effective_scope_policies if bool(item["retrieval_enabled"])
    ]
    if not retrieval_scopes:
        return AuthorizedMemoryContext((), (), (), 0)
    active_task_ids = select(AgentDelegation.id).where(
        AgentDelegation.company_id == company_id,
        AgentDelegation.status.in_(("queued", "in_progress", "awaiting_approval")),
    )
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == company_id,
                AgentMemoryEntry.agent_id == agent_id,
                AgentMemoryEntry.expires_at > utc_now(),
                AgentMemoryEntry.classification.in_(allowed),
                AgentMemoryEntry.scope.in_(retrieval_scopes),
                or_(
                    AgentMemoryEntry.scope != "user",
                    AgentMemoryEntry.subject_user_id == user_id,
                ),
                or_(
                    AgentMemoryEntry.scope != "task",
                    AgentMemoryEntry.task_delegation_id.in_(active_task_ids),
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
    estimated_tokens = 0
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
        protected = protect_provider_text(data_policy, provider=provider, text=content)[0]
        content_tokens = estimate_memory_tokens(protected)
        if estimated_tokens + content_tokens > memory_policy.max_context_tokens:
            continue
        contents.append(protected)
        retrieved.append(row.content_fingerprint)
        estimated_tokens += content_tokens
    return AuthorizedMemoryContext(
        tuple(contents), tuple(retrieved), tuple(blocked), estimated_tokens
    )


async def retrieve_shared_task_memories(
    database: AsyncSession,
    *,
    settings: Settings,
    company_id: UUID,
    grant: AgentTaskMemoryAccessGrant,
) -> SharedTaskMemoryContext:
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == company_id,
                AgentMemoryEntry.agent_id == grant.owner_agent_id,
                AgentMemoryEntry.scope == "task",
                AgentMemoryEntry.task_delegation_id == grant.task_delegation_id,
                AgentMemoryEntry.classification.in_(grant.allowed_classifications),
                AgentMemoryEntry.expires_at > utc_now(),
            )
            .order_by(AgentMemoryEntry.created_at.desc())
            .limit(grant.max_entries)
        )
    )
    vault = CredentialVault(settings.encryption_key)
    items: list[SharedTaskMemoryItem] = []
    remaining_characters = grant.max_content_characters
    blocked_items = 0
    for row in rows:
        try:
            content = vault.decrypt(row.encrypted_content).get("content")
        except CredentialVaultError:
            blocked_items += 1
            continue
        if not isinstance(content, str) or scan_prompt_injection(content).detected:
            blocked_items += 1
            continue
        if remaining_characters <= 0:
            break
        minimized = content[:remaining_characters]
        if not minimized:
            continue
        items.append(
            SharedTaskMemoryItem(
                memory_id=row.id,
                owner_agent_id=row.agent_id,
                classification=row.classification,
                purpose=row.purpose,
                content=minimized,
                truncated=len(minimized) < len(content),
                created_at=row.created_at,
            )
        )
        remaining_characters -= len(minimized)
    return SharedTaskMemoryContext(
        items=tuple(items),
        total_characters=grant.max_content_characters - remaining_characters,
        blocked_items=blocked_items,
    )


async def has_active_memory_legal_hold(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    delegation_id: UUID,
) -> bool:
    hold_id = await database.scalar(
        select(AgentMemoryLegalHold.id).where(
            AgentMemoryLegalHold.company_id == company_id,
            AgentMemoryLegalHold.agent_id == agent_id,
            AgentMemoryLegalHold.task_delegation_id == delegation_id,
            AgentMemoryLegalHold.status == "approved",
            AgentMemoryLegalHold.expires_at > utc_now(),
        )
    )
    return hold_id is not None


async def purge_terminal_task_memories(
    database: AsyncSession, *, company_id: UUID, delegation_id: UUID
) -> int:
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == company_id,
                AgentMemoryEntry.scope == "task",
                AgentMemoryEntry.task_delegation_id == delegation_id,
            )
            .with_for_update()
        )
    )
    deleted = 0
    for row in rows:
        if await has_active_memory_legal_hold(
            database,
            company_id=company_id,
            agent_id=row.agent_id,
            delegation_id=delegation_id,
        ):
            continue
        await database.delete(row)
        deleted += 1
    return deleted


async def purge_expired_agent_memories(database: AsyncSession, *, limit: int = 1_000) -> int:
    terminal_task_ids = select(AgentDelegation.id).where(
        AgentDelegation.status.in_(("completed", "failed", "cancelled"))
    )
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                or_(
                    AgentMemoryEntry.expires_at <= utc_now(),
                    AgentMemoryEntry.task_delegation_id.in_(terminal_task_ids),
                )
            )
            .order_by(AgentMemoryEntry.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    deleted = 0
    for row in rows:
        if row.task_delegation_id is not None and await has_active_memory_legal_hold(
            database,
            company_id=row.company_id,
            agent_id=row.agent_id,
            delegation_id=row.task_delegation_id,
        ):
            continue
        await database.delete(row)
        deleted += 1
    await database.commit()
    return deleted


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

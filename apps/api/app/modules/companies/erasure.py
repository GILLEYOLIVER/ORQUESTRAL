from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import utc_now
from app.modules.audit.models import AuditEvent
from app.modules.authentication.models import AuthAttempt, AuthSession
from app.modules.companies.models import Company
from app.modules.knowledge.models import KnowledgeDocument
from app.modules.knowledge.processing import storage
from app.modules.users.models import CompanyUser, User


class ErasureBlockedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ErasureResult:
    company_id: UUID
    removed_objects: int
    removed_orphan_users: int
    revoked_sessions: int


async def _remove_storage_objects(settings: Settings, documents: list[KnowledgeDocument]) -> int:
    if not documents:
        return 0
    if not settings.object_storage_enabled:
        raise ErasureBlockedError(
            "Existem arquivos externos, mas o armazenamento está desativado. "
            "Ative a conexão segura antes da eliminação para não deixar resíduos."
        )
    client = storage(settings)
    for document in documents:
        await asyncio.to_thread(
            client.remove_object,
            settings.storage_bucket,
            document.storage_key,
        )
    return len(documents)


async def _remove_cache(redis: Redis, company_id: UUID) -> None:
    keys: list[bytes | str] = []
    async for key in redis.scan_iter(match=f"*{company_id}*", count=500):
        keys.append(key)
        if len(keys) >= 500:
            await redis.unlink(*keys)
            keys.clear()
    if keys:
        await redis.unlink(*keys)


async def purge_company_data(
    database: AsyncSession,
    redis: Redis,
    settings: Settings,
    company: Company,
) -> ErasureResult:
    company_id = company.id
    await _remove_cache(redis, company_id)
    documents = list(
        await database.scalars(
            select(KnowledgeDocument).where(KnowledgeDocument.company_id == company_id)
        )
    )
    removed_objects = await _remove_storage_objects(settings, documents)

    memberships = list(
        await database.scalars(select(CompanyUser).where(CompanyUser.company_id == company_id))
    )
    user_ids = {membership.user_id for membership in memberships}
    users = (
        list(await database.scalars(select(User).where(User.id.in_(user_ids)))) if user_ids else []
    )
    emails = {user.email.lower() for user in users}

    revoked_sessions = 0
    if user_ids:
        revoked_session_ids = list(
            await database.scalars(
                update(AuthSession)
                .where(
                    AuthSession.user_id.in_(user_ids),
                    AuthSession.selected_company_id == company_id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=utc_now())
                .returning(AuthSession.id)
            )
        )
        revoked_sessions = len(revoked_session_ids)

    await database.execute(delete(AuditEvent).where(AuditEvent.company_id == company_id))
    if emails:
        await database.execute(delete(AuthAttempt).where(func.lower(AuthAttempt.email).in_(emails)))

    await database.delete(company)
    await database.flush()

    removed_orphan_users = 0
    for user in users:
        membership_count = await database.scalar(
            select(func.count(CompanyUser.id)).where(CompanyUser.user_id == user.id)
        )
        if not membership_count and not user.is_platform_admin:
            await database.delete(user)
            removed_orphan_users += 1

    await database.commit()
    return ErasureResult(
        company_id=company_id,
        removed_objects=removed_objects,
        removed_orphan_users=removed_orphan_users,
        revoked_sessions=revoked_sessions,
    )

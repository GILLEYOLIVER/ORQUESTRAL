from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import DatabaseProcessRole, Settings
from app.core.database import create_database_engine, create_session_factory


@dataclass(slots=True)
class ApplicationResources:
    database: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    redis: Redis

    async def close(self) -> None:
        await self.redis.aclose()
        await self.database.dispose()


def create_resources(
    settings: Settings,
    *,
    database_role: DatabaseProcessRole | None = None,
) -> ApplicationResources:
    database_url = (
        settings.database_url_for(database_role)
        if database_role is not None
        else settings.effective_database_url
    )
    database = create_database_engine(database_url)
    return ApplicationResources(
        database=database,
        sessions=create_session_factory(database),
        redis=Redis.from_url(str(settings.redis_url), decode_responses=True),
    )

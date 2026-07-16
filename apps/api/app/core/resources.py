from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.database import create_database_engine, create_session_factory


@dataclass(slots=True)
class ApplicationResources:
    database: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    redis: Redis

    async def close(self) -> None:
        await self.redis.aclose()
        await self.database.dispose()


def create_resources(settings: Settings) -> ApplicationResources:
    database = create_database_engine(settings.database_url)
    return ApplicationResources(
        database=database,
        sessions=create_session_factory(database),
        redis=Redis.from_url(str(settings.redis_url), decode_responses=True),
    )

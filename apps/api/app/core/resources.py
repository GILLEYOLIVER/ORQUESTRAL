from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.database import create_database_engine


@dataclass(slots=True)
class ApplicationResources:
    database: AsyncEngine
    redis: Redis

    async def close(self) -> None:
        await self.redis.aclose()
        await self.database.dispose()


def create_resources(settings: Settings) -> ApplicationResources:
    return ApplicationResources(
        database=create_database_engine(settings.database_url),
        redis=Redis.from_url(str(settings.redis_url), decode_responses=True),
    )

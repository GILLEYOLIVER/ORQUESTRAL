from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.resources.sessions() as session:
        yield session


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.resources.redis)


def get_request_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
RedisClient = Annotated[Redis, Depends(get_redis)]
RequestSettings = Annotated[Settings, Depends(get_request_settings)]

import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import create_database_engine

MIGRATION_LOCK_ID = 6_275_737_261


async def migrate() -> None:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.execute(
            text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID}
        )
        try:
            config = Config("alembic.ini")
            await asyncio.to_thread(command.upgrade, config, "head")
        finally:
            await connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())

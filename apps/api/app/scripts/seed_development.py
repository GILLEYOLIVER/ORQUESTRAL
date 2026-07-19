import asyncio

from app.core.config import get_settings
from app.scripts.bootstrap import bootstrap


async def seed() -> None:
    settings = get_settings()
    if settings.app_env != "development" or not settings.remote_development_enabled:
        raise RuntimeError("O seed remoto só pode executar em APP_ENV=development.")
    if not settings.bootstrap_enabled:
        raise RuntimeError("BOOTSTRAP_ENABLED deve estar ativo para executar o seed.")
    await bootstrap()


if __name__ == "__main__":
    asyncio.run(seed())

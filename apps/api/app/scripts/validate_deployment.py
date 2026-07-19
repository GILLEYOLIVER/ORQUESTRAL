from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.readiness_is_configured:
        raise RuntimeError("Dependências obrigatórias não foram configuradas.")
    print(
        "Configuração validada:",
        f"environment={settings.app_env}",
        f"version={settings.app_version}",
        f"commit={settings.deployed_commit}",
        f"remote={settings.remote_development_enabled}",
    )


if __name__ == "__main__":
    main()

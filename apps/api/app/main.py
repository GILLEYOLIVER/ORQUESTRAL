from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import ObservabilityMiddleware, SecurityMiddleware
from app.core.resources import create_resources
from app.core.schemas import ProblemDetails
from app.modules.agents.routes import router as agents_router
from app.modules.audit.routes import router as audit_router
from app.modules.authentication.routes import router as authentication_router
from app.modules.authorization.routes import router as authorization_router
from app.modules.billing.routes import router as billing_router
from app.modules.companies.routes import router as companies_router
from app.modules.knowledge.routes import router as knowledge_router
from app.modules.metrics.routes import router as metrics_router
from app.modules.modularity.registry import module_registry
from app.modules.modularity.routes import router as modules_router
from app.modules.plugins.routes import router as plugins_router
from app.modules.users.routes import router as users_router
from app.modules.workflows.routes import router as workflows_router
from app.modules.workflows.routes import webhook_router as workflow_webhooks_router
from app.routes.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.resources = create_resources(resolved_settings)
        try:
            yield
        finally:
            await app.state.resources.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
        responses={
            400: {"model": ProblemDetails, "description": "Solicitação inválida"},
            422: {"model": ProblemDetails, "description": "Dados inválidos"},
            500: {"model": ProblemDetails, "description": "Erro interno"},
        },
    )
    application.state.settings = resolved_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    application.add_middleware(SecurityMiddleware)
    application.add_middleware(ObservabilityMiddleware)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(agents_router)
    application.include_router(authentication_router)
    application.include_router(audit_router)
    application.include_router(authorization_router)
    application.include_router(billing_router)
    application.include_router(companies_router)
    application.include_router(knowledge_router)
    application.include_router(metrics_router)
    application.include_router(users_router)
    application.include_router(modules_router)
    application.include_router(plugins_router)
    application.include_router(workflows_router)
    application.include_router(workflow_webhooks_router)
    for module in module_registry.installed():
        for module_router in module.routers:
            application.include_router(module_router)
    return application


app = create_app()

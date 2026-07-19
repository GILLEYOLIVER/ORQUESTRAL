from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.dependencies import DatabaseSession, RedisClient, RequestSettings
from app.core.security import WeakPasswordError
from app.core.tenancy import CurrentPrincipal
from app.modules.authentication.schemas import (
    AcceptInvitationRequest,
    AccessTokenResponse,
    AuthSessionResponse,
    CompanySummary,
    DevelopmentAccessResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MembershipResponse,
    MeResponse,
    MessageResponse,
    ResetPasswordRequest,
    SelectCompanyRequest,
    UserResponse,
)
from app.modules.authentication.service import (
    AuthenticationService,
    CompanyAccessError,
    InvalidCredentialsError,
    InvalidOneTimeTokenError,
    InvalidRefreshTokenError,
    IssuedTokens,
    LoginRateLimitedError,
)
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/auth", tags=["authentication"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_refresh_cookie(response: Response, token: str, settings: RequestSettings) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.refresh_token_days * 86_400,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


def _token_response(issued: IssuedTokens) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=issued.access_token,
        expires_at=issued.access_expires_at,
    )


def _development_access_enabled(settings: RequestSettings) -> bool:
    return bool(
        settings.app_env == "local"
        and settings.development_expose_tokens
        and settings.bootstrap_enabled
        and settings.bootstrap_admin_email
        and settings.effective_bootstrap_admin_password
    )


@router.get("/development-access", response_model=DevelopmentAccessResponse)
async def development_access(settings: RequestSettings) -> DevelopmentAccessResponse:
    return DevelopmentAccessResponse(enabled=_development_access_enabled(settings))


@router.post("/development-login", response_model=AccessTokenResponse)
async def development_login(
    request: Request,
    response: Response,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> AccessTokenResponse:
    if not _development_access_enabled(settings):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")
    assert settings.bootstrap_admin_email is not None
    password = settings.effective_bootstrap_admin_password
    assert password is not None
    try:
        issued = await AuthenticationService(database, redis, settings).login(
            email=settings.bootstrap_admin_email,
            password=password,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=503,
            detail="Administrador local indisponível. Execute o bootstrap novamente.",
        ) from exc
    except LoginRateLimitedError as exc:
        raise HTTPException(
            status_code=429, detail="Acesso local temporariamente bloqueado."
        ) from exc
    _set_refresh_cookie(response, issued.refresh_token, settings)
    return _token_response(issued)


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> AccessTokenResponse:
    service = AuthenticationService(database, redis, settings)
    try:
        issued = await service.login(
            email=str(payload.email),
            password=payload.password,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.") from exc
    except LoginRateLimitedError as exc:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde alguns minutos e tente novamente.",
        ) from exc
    _set_refresh_cookie(response, issued.refresh_token, settings)
    return _token_response(issued)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> AccessTokenResponse:
    refresh_token = request.cookies.get(settings.auth_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Sessão não encontrada.")
    try:
        issued = await AuthenticationService(database, redis, settings).refresh(refresh_token)
    except InvalidRefreshTokenError as exc:
        response.delete_cookie(settings.auth_cookie_name, path="/")
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.") from exc
    _set_refresh_cookie(response, issued.refresh_token, settings)
    return _token_response(issued)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> None:
    refresh_token = request.cookies.get(settings.auth_cookie_name)
    await AuthenticationService(database, redis, settings).logout(refresh_token)
    response.delete_cookie(settings.auth_cookie_name, path="/")


@router.get("/sessions", response_model=list[AuthSessionResponse])
async def list_sessions(
    principal: CurrentPrincipal,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> list[AuthSessionResponse]:
    sessions = await AuthenticationService(database, redis, settings).active_sessions(
        principal.user.id
    )
    return [
        AuthSessionResponse(
            id=session.id,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            expires_at=session.expires_at,
            last_used_at=session.last_used_at,
            created_at=session.created_at,
            current=session.id == principal.session.id,
        )
        for session in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    response: Response,
    principal: CurrentPrincipal,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> None:
    revoked = await AuthenticationService(database, redis, settings).revoke_session(
        user_id=principal.user.id,
        session_id=session_id,
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    if session_id == principal.session.id:
        response.delete_cookie(settings.auth_cookie_name, path="/")


@router.post("/select-company", response_model=AccessTokenResponse)
async def select_company(
    payload: SelectCompanyRequest,
    response: Response,
    principal: CurrentPrincipal,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> AccessTokenResponse:
    try:
        issued = await AuthenticationService(database, redis, settings).select_company(
            auth_session=principal.session,
            user=principal.user,
            company_id=payload.company_id,
        )
    except CompanyAccessError as exc:
        raise HTTPException(status_code=403, detail="Acesso à empresa não autorizado.") from exc
    return _token_response(issued)


@router.post("/forgot-password", response_model=MessageResponse, status_code=202)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> MessageResponse:
    token = await AuthenticationService(database, redis, settings).forgot_password(
        email=str(payload.email), ip_address=_client_ip(request)
    )
    return MessageResponse(
        message="Se o e-mail estiver cadastrado, as instruções serão enviadas.",
        development_token=token if settings.development_expose_tokens else None,
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> MessageResponse:
    try:
        await AuthenticationService(database, redis, settings).reset_password(
            token=payload.token, password=payload.password
        )
    except WeakPasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidOneTimeTokenError as exc:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.") from exc
    return MessageResponse(message="Senha redefinida. Entre novamente.")


@router.post("/accept-invitation", response_model=MessageResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> MessageResponse:
    try:
        await AuthenticationService(database, redis, settings).accept_invitation(
            token=payload.token,
            name=payload.name,
            password=payload.password,
        )
    except WeakPasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidOneTimeTokenError as exc:
        raise HTTPException(status_code=400, detail="Convite inválido ou expirado.") from exc
    return MessageResponse(message="Convite aceito. Você já pode entrar.")


@router.get("/me", response_model=MeResponse)
async def me(principal: CurrentPrincipal, database: DatabaseSession) -> MeResponse:
    rows = (
        await database.execute(
            select(CompanyUser, Company)
            .join(Company, Company.id == CompanyUser.company_id)
            .where(
                CompanyUser.user_id == principal.user.id,
                CompanyUser.status == "active",
                Company.status.in_(("active", "trial")),
                Company.deleted_at.is_(None),
            )
            .order_by(Company.trade_name)
        )
    ).all()
    memberships = [
        MembershipResponse(
            id=membership.id,
            company=CompanySummary.model_validate(company, from_attributes=True),
            role_id=membership.role_id,
            status=membership.status,
            is_owner=membership.is_owner,
        )
        for membership, company in rows
    ]
    current_company = (
        CompanySummary.model_validate(principal.company, from_attributes=True)
        if principal.company
        else None
    )
    return MeResponse(
        user=UserResponse.model_validate(principal.user, from_attributes=True),
        current_company=current_company,
        memberships=memberships,
        permissions=sorted(principal.permissions),
        requires_company_selection=current_company is None and len(memberships) > 1,
    )

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import apply_tenant_database_context
from app.core.dependencies import DatabaseSession, RedisClient, RequestSettings
from app.core.schemas import StrictSchema
from app.core.security import verify_password
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.erasure import ErasureBlockedError, purge_company_data
from app.modules.companies.models import Company
from app.modules.companies.schemas import CompanyCreate, CompanyResponse, CompanyUpdate
from app.modules.users.models import CompanyUser, User

router = APIRouter(prefix="/companies", tags=["companies"])

CanViewCompanies = Annotated[Principal, Depends(require_permission("platform.companies.view"))]
CanCreateCompanies = Annotated[Principal, Depends(require_permission("platform.companies.create"))]
CanUpdateCompanies = Annotated[Principal, Depends(require_permission("platform.companies.update"))]


class CompanyErasureRequest(StrictSchema):
    confirmation: str = Field(min_length=8, max_length=240)
    account_password: str = Field(min_length=1, max_length=512)
    acknowledge_backup_expiration: bool


class CompanyErasureResponse(StrictSchema):
    status: str
    company_id: UUID
    removed_objects: int
    removed_orphan_users: int
    revoked_sessions: int


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    _: CanViewCompanies,
    database: DatabaseSession,
) -> list[CompanyResponse]:
    companies = (
        await database.scalars(
            select(Company).where(Company.deleted_at.is_(None)).order_by(Company.trade_name)
        )
    ).all()
    return [CompanyResponse.model_validate(company, from_attributes=True) for company in companies]


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    principal: CanCreateCompanies,
    database: DatabaseSession,
) -> CompanyResponse:
    context = get_request_context(principal)
    company = Company(**payload.model_dump())
    database.add(company)
    try:
        await database.flush()
        # A permissão de plataforma já foi validada. A partir deste ponto, as
        # escritas de bootstrap pertencem à nova empresa e devem passar pela
        # mesma política RLS usada por qualquer outro tenant.
        await apply_tenant_database_context(
            database,
            company_id=company.id,
            access_mode="standard",
        )
        owner_role, _ = await ensure_company_system_roles(database, company.id)
        database.add(
            CompanyUser(
                company_id=company.id,
                user_id=context.user_id,
                role_id=owner_role.id,
                status="active",
                is_owner=True,
            )
        )
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Slug ou documento já cadastrado.") from exc
    return CompanyResponse.model_validate(company, from_attributes=True)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    _: CanUpdateCompanies,
    database: DatabaseSession,
) -> CompanyResponse:
    company = await database.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await database.commit()
    await database.refresh(company)
    return CompanyResponse.model_validate(company, from_attributes=True)


@router.post("/{company_id}/purge", response_model=CompanyErasureResponse)
async def purge_company(
    company_id: UUID,
    payload: CompanyErasureRequest,
    principal: CanUpdateCompanies,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> CompanyErasureResponse:
    context = get_request_context(principal)
    company = await database.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    expected_confirmation = f"PURGE:{company.slug}"
    if payload.confirmation != expected_confirmation:
        raise HTTPException(
            status_code=422,
            detail=f"Confirmação inválida. Informe exatamente {expected_confirmation}.",
        )
    if not payload.acknowledge_backup_expiration:
        raise HTTPException(
            status_code=422,
            detail="Confirme a política de expiração dos backups antes da eliminação.",
        )
    actor = await database.get(User, context.user_id)
    if actor is None or not verify_password(actor.password_hash, payload.account_password):
        raise HTTPException(status_code=403, detail="Reautenticação inválida.")
    try:
        result = await purge_company_data(database, redis, settings, company)
    except ErasureBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CompanyErasureResponse(
        status="purged",
        company_id=result.company_id,
        removed_objects=result.removed_objects,
        removed_orphan_users=result.removed_orphan_users,
        revoked_sessions=result.revoked_sessions,
    )

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.tenancy import PlatformAdmin
from app.modules.companies.models import Company
from app.modules.companies.schemas import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    _: PlatformAdmin,
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
    _: PlatformAdmin,
    database: DatabaseSession,
) -> CompanyResponse:
    company = Company(**payload.model_dump())
    database.add(company)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Slug ou documento já cadastrado.") from exc
    return CompanyResponse.model_validate(company, from_attributes=True)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    _: PlatformAdmin,
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

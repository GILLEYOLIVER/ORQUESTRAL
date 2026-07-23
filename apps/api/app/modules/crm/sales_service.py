from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.customer_data_service import sync_customer_profile
from app.modules.crm.models import (
    CRMAccount,
    CRMContact,
    CRMLead,
    CRMOpportunity,
    CRMOpportunityActivity,
    CRMPipeline,
    CRMPipelineStage,
)
from app.modules.crm.sales_schemas import (
    CRMAccountCreate,
    CRMAccountResponse,
    CRMLeadConversionCreate,
    CRMLeadConversionResponse,
    CRMLeadCreate,
    CRMLeadQualification,
    CRMLeadResponse,
    CRMLeadUpdate,
)
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.users.models import CompanyUser


class SalesServiceError(RuntimeError):
    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def calculate_lead_score(values: dict[str, Any]) -> int:
    score = 10
    score += 25 if values.get("email") else 0
    score += 20 if values.get("phone") else 0
    score += 20 if values.get("company_name") else 0
    score += 15 if values.get("job_title") else 0
    score += 10 if values.get("source") else 0
    return min(score, 100)


def _account_response(account: CRMAccount) -> CRMAccountResponse:
    return CRMAccountResponse.model_validate(account, from_attributes=True)


def _lead_response(lead: CRMLead) -> CRMLeadResponse:
    return CRMLeadResponse.model_validate(lead, from_attributes=True)


async def _validate_owner(
    database: AsyncSession, *, company_id: UUID, owner_user_id: UUID | None
) -> None:
    if owner_user_id is None:
        return
    membership = await database.scalar(
        select(CompanyUser.id).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == owner_user_id,
            CompanyUser.status == "active",
        )
    )
    if membership is None:
        raise SalesServiceError("Responsável inválido para a empresa atual.")


async def list_accounts(
    database: AsyncSession, *, company_id: UUID
) -> list[CRMAccountResponse]:
    accounts = list(
        await database.scalars(
            select(CRMAccount)
            .where(
                CRMAccount.company_id == company_id,
                CRMAccount.deleted_at.is_(None),
            )
            .order_by(CRMAccount.name)
        )
    )
    return [_account_response(account) for account in accounts]


async def create_account(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CRMAccountCreate,
) -> CRMAccountResponse:
    await _validate_owner(
        database, company_id=company_id, owner_user_id=payload.owner_user_id
    )
    existing = await database.scalar(
        select(CRMAccount).where(
            CRMAccount.company_id == company_id,
            CRMAccount.name == payload.name.strip(),
            CRMAccount.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise SalesServiceError("Já existe uma conta com este nome.", status_code=409)
    values = payload.model_dump()
    values["name"] = payload.name.strip()
    values["currency"] = payload.currency.upper()
    account = CRMAccount(company_id=company_id, **values)
    database.add(account)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.account.created",
        target_type="crm_account",
        target_id=account.id,
        details={"status": account.status, "industry": account.industry},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.account.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"account_id": str(account.id), "status": account.status},
        ),
    )
    await database.commit()
    await database.refresh(account)
    return _account_response(account)


async def list_leads(
    database: AsyncSession,
    *,
    company_id: UUID,
    status_filter: str | None = None,
) -> list[CRMLeadResponse]:
    query = select(CRMLead).where(
        CRMLead.company_id == company_id,
        CRMLead.deleted_at.is_(None),
    )
    if status_filter:
        query = query.where(CRMLead.status == status_filter)
    leads = list(await database.scalars(query.order_by(CRMLead.created_at.desc())))
    return [_lead_response(lead) for lead in leads]


async def create_lead(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CRMLeadCreate,
) -> CRMLeadResponse:
    await _validate_owner(
        database, company_id=company_id, owner_user_id=payload.owner_user_id
    )
    values = payload.model_dump()
    values["name"] = payload.name.strip()
    values["email"] = payload.email.strip().casefold() if payload.email else None
    values["phone"] = payload.phone.strip() if payload.phone else None
    lead = CRMLead(
        company_id=company_id,
        score=calculate_lead_score(values),
        **values,
    )
    database.add(lead)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.lead.created",
        target_type="crm_lead",
        target_id=lead.id,
        details={"score": lead.score, "source": lead.source},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.lead.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"lead_id": str(lead.id), "score": lead.score},
        ),
    )
    await database.commit()
    await database.refresh(lead)
    return _lead_response(lead)


async def update_lead(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    lead_id: UUID,
    payload: CRMLeadUpdate,
) -> CRMLeadResponse:
    lead = await database.scalar(
        select(CRMLead).where(
            CRMLead.id == lead_id,
            CRMLead.company_id == company_id,
            CRMLead.deleted_at.is_(None),
        )
    )
    if lead is None:
        raise SalesServiceError("Lead não encontrado.", status_code=404)
    if lead.status in {"converted", "qualified"}:
        raise SalesServiceError(
            "Leads qualificados ou convertidos não podem ser editados.", status_code=409
        )
    changes = payload.model_dump(exclude_unset=True)
    if "owner_user_id" in changes:
        await _validate_owner(
            database,
            company_id=company_id,
            owner_user_id=changes["owner_user_id"],
        )
    if changes.get("email"):
        changes["email"] = changes["email"].strip().casefold()
    if changes.get("phone"):
        changes["phone"] = changes["phone"].strip()
    for field, value in changes.items():
        setattr(lead, field, value)
    lead.score = calculate_lead_score(
        {
            "email": lead.email,
            "phone": lead.phone,
            "company_name": lead.company_name,
            "job_title": lead.job_title,
            "source": lead.source,
        }
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.lead.updated",
        target_type="crm_lead",
        target_id=lead.id,
        details={"fields": sorted(changes), "score": lead.score},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.lead.updated",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"lead_id": str(lead.id), "score": lead.score},
        ),
    )
    await database.commit()
    await database.refresh(lead)
    return _lead_response(lead)


async def qualify_lead(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    lead_id: UUID,
    payload: CRMLeadQualification,
) -> CRMLeadResponse:
    lead = await database.scalar(
        select(CRMLead)
        .where(
            CRMLead.id == lead_id,
            CRMLead.company_id == company_id,
            CRMLead.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if lead is None:
        raise SalesServiceError("Lead não encontrado.", status_code=404)
    if lead.status == "converted":
        raise SalesServiceError("O lead já foi convertido.", status_code=409)
    lead.status = payload.decision
    lead.qualification_note = payload.note
    lead.qualified_at = utc_now() if payload.decision == "qualified" else None
    event_type = f"crm.lead.{payload.decision}"
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=event_type,
        target_type="crm_lead",
        target_id=lead.id,
        details={"decision": payload.decision, "score": lead.score},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=event_type,
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"lead_id": str(lead.id), "score": lead.score},
        ),
    )
    await database.commit()
    await database.refresh(lead)
    return _lead_response(lead)


async def convert_lead(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    lead_id: UUID,
    payload: CRMLeadConversionCreate,
) -> CRMLeadConversionResponse:
    lead = await database.scalar(
        select(CRMLead)
        .where(
            CRMLead.id == lead_id,
            CRMLead.company_id == company_id,
            CRMLead.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if lead is None:
        raise SalesServiceError("Lead não encontrado.", status_code=404)
    if lead.status == "converted":
        if lead.converted_contact_id is None or lead.converted_opportunity_id is None:
            raise SalesServiceError("A conversão anterior está inconsistente.", status_code=409)
        return CRMLeadConversionResponse(
            lead_id=lead.id,
            account_id=lead.converted_account_id,
            contact_id=lead.converted_contact_id,
            opportunity_id=lead.converted_opportunity_id,
            status="converted",
            idempotent=True,
        )
    if lead.status != "qualified":
        raise SalesServiceError(
            "Qualifique o lead antes de convertê-lo.", status_code=409
        )

    pipeline = await database.scalar(
        select(CRMPipeline).where(
            CRMPipeline.id == payload.pipeline_id,
            CRMPipeline.company_id == company_id,
        )
    )
    stage = await database.scalar(
        select(CRMPipelineStage).where(
            CRMPipelineStage.id == payload.stage_id,
            CRMPipelineStage.pipeline_id == payload.pipeline_id,
            CRMPipelineStage.company_id == company_id,
        )
    )
    if pipeline is None or stage is None:
        raise SalesServiceError("Funil ou etapa inválidos para esta empresa.")

    account: CRMAccount | None = None
    if payload.account_id is not None:
        account = await database.scalar(
            select(CRMAccount).where(
                CRMAccount.id == payload.account_id,
                CRMAccount.company_id == company_id,
                CRMAccount.deleted_at.is_(None),
            )
        )
        if account is None:
            raise SalesServiceError("Conta inválida para esta empresa.")
    elif payload.create_account and lead.company_name:
        account = await database.scalar(
            select(CRMAccount).where(
                CRMAccount.company_id == company_id,
                CRMAccount.name == lead.company_name.strip(),
                CRMAccount.deleted_at.is_(None),
            )
        )
        if account is None:
            account = CRMAccount(
                company_id=company_id,
                name=lead.company_name.strip(),
                owner_user_id=lead.owner_user_id,
                status="prospect",
            )
            database.add(account)
            await database.flush()

    contact = CRMContact(
        company_id=company_id,
        account_id=account.id if account else None,
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        company_name=account.name if account else lead.company_name,
        job_title=lead.job_title,
        source=lead.source,
        status="prospect",
        assigned_user_id=lead.owner_user_id,
    )
    database.add(contact)
    await database.flush()
    profile = await sync_customer_profile(
        database,
        contact=contact,
        actor_user_id=actor_user_id,
    )

    opportunity = CRMOpportunity(
        company_id=company_id,
        pipeline_id=pipeline.id,
        stage_id=stage.id,
        contact_id=contact.id,
        account_id=account.id if account else None,
        assigned_user_id=lead.owner_user_id,
        title=payload.opportunity_title,
        amount=payload.amount,
        probability=stage.probability,
        expected_close_date=payload.expected_close_date,
        source=lead.source,
        status="open",
    )
    database.add(opportunity)
    await database.flush()
    database.add(
        CRMOpportunityActivity(
            company_id=company_id,
            opportunity_id=opportunity.id,
            contact_id=contact.id,
            actor_user_id=actor_user_id,
            activity_type="status_change",
            subject="Oportunidade criada pela conversão de lead",
        )
    )
    lead.status = "converted"
    lead.converted_at = utc_now()
    lead.converted_account_id = account.id if account else None
    lead.converted_contact_id = contact.id
    lead.converted_opportunity_id = opportunity.id

    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.lead.converted",
        target_type="crm_lead",
        target_id=lead.id,
        details={
            "account_id": str(account.id) if account else None,
            "contact_id": str(contact.id),
            "opportunity_id": str(opportunity.id),
            "profile_id": str(profile.id),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.lead.converted",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "lead_id": str(lead.id),
                "account_id": str(account.id) if account else None,
                "contact_id": str(contact.id),
                "opportunity_id": str(opportunity.id),
                "profile_id": str(profile.id),
            },
        ),
    )
    await database.commit()
    return CRMLeadConversionResponse(
        lead_id=lead.id,
        account_id=account.id if account else None,
        contact_id=contact.id,
        opportunity_id=opportunity.id,
        status="converted",
        idempotent=False,
    )

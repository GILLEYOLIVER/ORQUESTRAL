from __future__ import annotations

from math import ceil
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.models import CRMContact, CRMContactTag, CRMTag
from app.modules.crm.schemas import (
    CRMContactCreate,
    CRMContactPage,
    CRMContactResponse,
    CRMContactUpdate,
    CRMTagCreate,
    CRMTagResponse,
)
from app.modules.modularity.dependencies import require_active_module
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/crm", tags=["crm"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanViewContacts = Annotated[Principal, Depends(require_permission("crm.contacts.view"))]
CanCreateContacts = Annotated[Principal, Depends(require_permission("crm.contacts.create"))]
CanUpdateContacts = Annotated[Principal, Depends(require_permission("crm.contacts.update"))]
CanDeleteContacts = Annotated[Principal, Depends(require_permission("crm.contacts.delete"))]


async def _validate_assignment(
    database: DatabaseSession, company_id: UUID, user_id: UUID | None
) -> None:
    if user_id is None:
        return
    membership = await database.scalar(
        select(CompanyUser.id).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
            CompanyUser.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=422, detail="Responsável inválido para a empresa atual.")


async def _validate_tags(
    database: DatabaseSession, company_id: UUID, tag_ids: list[UUID]
) -> list[CRMTag]:
    unique_ids = set(tag_ids)
    tags = list(
        await database.scalars(
            select(CRMTag).where(
                CRMTag.company_id == company_id,
                CRMTag.id.in_(unique_ids),
            )
        )
    )
    if len(tags) != len(unique_ids):
        raise HTTPException(status_code=422, detail="Uma ou mais etiquetas são inválidas.")
    return tags


async def _tags_by_contact(
    database: DatabaseSession, contact_ids: list[UUID]
) -> dict[UUID, list[CRMTagResponse]]:
    if not contact_ids:
        return {}
    rows = (
        await database.execute(
            select(CRMContactTag.contact_id, CRMTag)
            .join(CRMTag, CRMTag.id == CRMContactTag.tag_id)
            .where(CRMContactTag.contact_id.in_(contact_ids))
            .order_by(CRMTag.name)
        )
    ).all()
    result: dict[UUID, list[CRMTagResponse]] = {}
    for contact_id, tag in rows:
        result.setdefault(contact_id, []).append(
            CRMTagResponse.model_validate(tag, from_attributes=True)
        )
    return result


def _contact_response(contact: CRMContact, tags: list[CRMTagResponse]) -> CRMContactResponse:
    return CRMContactResponse(
        id=contact.id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        company_name=contact.company_name,
        job_title=contact.job_title,
        source=contact.source,
        status=contact.status,
        assigned_user_id=contact.assigned_user_id,
        tags=tags,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


async def _get_contact(database: DatabaseSession, company_id: UUID, contact_id: UUID) -> CRMContact:
    contact = await database.scalar(
        select(CRMContact).where(
            CRMContact.id == contact_id,
            CRMContact.company_id == company_id,
            CRMContact.deleted_at.is_(None),
        )
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    return contact


@router.get("/contacts", response_model=CRMContactPage)
async def list_contacts(
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=160)] = None,
    contact_status: Annotated[
        Literal["lead", "prospect", "customer", "inactive"] | None,
        Query(alias="status"),
    ] = None,
    source: Annotated[str | None, Query(max_length=80)] = None,
    assigned_user_id: UUID | None = None,
    tag_id: UUID | None = None,
    sort_by: Literal["name", "company_name", "status", "created_at", "updated_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> CRMContactPage:
    context = get_request_context(principal)
    filters = [
        CRMContact.company_id == context.company_id,
        CRMContact.deleted_at.is_(None),
    ]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                CRMContact.name.ilike(pattern),
                CRMContact.email.ilike(pattern),
                CRMContact.phone.ilike(pattern),
                CRMContact.company_name.ilike(pattern),
            )
        )
    if contact_status:
        filters.append(CRMContact.status == contact_status)
    if source:
        filters.append(CRMContact.source == source)
    if assigned_user_id:
        filters.append(CRMContact.assigned_user_id == assigned_user_id)
    if tag_id:
        filters.append(
            CRMContact.id.in_(
                select(CRMContactTag.contact_id).where(CRMContactTag.tag_id == tag_id)
            )
        )

    total = int(
        await database.scalar(select(func.count()).select_from(CRMContact).where(*filters)) or 0
    )
    sort_columns = {
        "name": CRMContact.name,
        "company_name": CRMContact.company_name,
        "status": CRMContact.status,
        "created_at": CRMContact.created_at,
        "updated_at": CRMContact.updated_at,
    }
    sort_column = sort_columns[sort_by]
    order = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    contacts = list(
        await database.scalars(
            select(CRMContact)
            .where(*filters)
            .order_by(order, CRMContact.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    tags = await _tags_by_contact(database, [contact.id for contact in contacts])
    return CRMContactPage(
        items=[_contact_response(contact, tags.get(contact.id, [])) for contact in contacts],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


@router.post("/contacts", response_model=CRMContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: CRMContactCreate,
    principal: CanCreateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMContactResponse:
    context = get_request_context(principal)
    await _validate_assignment(database, context.company_id, payload.assigned_user_id)
    tags = await _validate_tags(database, context.company_id, payload.tag_ids)
    contact = CRMContact(
        company_id=context.company_id,
        **payload.model_dump(exclude={"tag_ids"}),
    )
    database.add(contact)
    await database.flush()
    database.add_all(CRMContactTag(contact_id=contact.id, tag_id=tag.id) for tag in tags)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="crm.contact.created",
        target_type="crm_contact",
        target_id=contact.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    tag_responses = [CRMTagResponse.model_validate(tag, from_attributes=True) for tag in tags]
    return _contact_response(contact, tag_responses)


@router.get("/contacts/{contact_id}", response_model=CRMContactResponse)
async def get_contact(
    contact_id: UUID,
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMContactResponse:
    context = get_request_context(principal)
    contact = await _get_contact(database, context.company_id, contact_id)
    tags = await _tags_by_contact(database, [contact.id])
    return _contact_response(contact, tags.get(contact.id, []))


@router.patch("/contacts/{contact_id}", response_model=CRMContactResponse)
async def update_contact(
    contact_id: UUID,
    payload: CRMContactUpdate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMContactResponse:
    context = get_request_context(principal)
    contact = await _get_contact(database, context.company_id, contact_id)
    if "assigned_user_id" in payload.model_fields_set:
        await _validate_assignment(database, context.company_id, payload.assigned_user_id)

    tag_models: list[CRMTag] | None = None
    if payload.tag_ids is not None:
        tag_models = await _validate_tags(database, context.company_id, payload.tag_ids)
        await database.execute(delete(CRMContactTag).where(CRMContactTag.contact_id == contact.id))
        database.add_all(CRMContactTag(contact_id=contact.id, tag_id=tag.id) for tag in tag_models)
    for field, value in payload.model_dump(exclude_unset=True, exclude={"tag_ids"}).items():
        setattr(contact, field, value)
    contact.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="crm.contact.updated",
        target_type="crm_contact",
        target_id=contact.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(contact)
    tags = await _tags_by_contact(database, [contact.id])
    return _contact_response(contact, tags.get(contact.id, []))


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: UUID,
    principal: CanDeleteContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    contact = await _get_contact(database, context.company_id, contact_id)
    contact.deleted_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="crm.contact.deleted",
        target_type="crm_contact",
        target_id=contact.id,
        details={},
    )
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tags", response_model=list[CRMTagResponse])
async def list_tags(
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CRMTagResponse]:
    context = get_request_context(principal)
    tags = list(
        await database.scalars(
            select(CRMTag).where(CRMTag.company_id == context.company_id).order_by(CRMTag.name)
        )
    )
    return [CRMTagResponse.model_validate(tag, from_attributes=True) for tag in tags]


@router.post("/tags", response_model=CRMTagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: CRMTagCreate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMTagResponse:
    context = get_request_context(principal)
    tag = CRMTag(company_id=context.company_id, name=payload.name)
    database.add(tag)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Essa etiqueta já existe.") from exc
    return CRMTagResponse.model_validate(tag, from_attributes=True)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    tag = await database.scalar(
        select(CRMTag).where(CRMTag.id == tag_id, CRMTag.company_id == context.company_id)
    )
    if tag is None:
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada.")
    await database.delete(tag)
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, text

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.models import CRMContact
from app.modules.marketing.audience_schemas import (
    MarketingAudienceCreate,
    MarketingAudienceMemberCreate,
    MarketingAudienceMemberResponse,
    MarketingAudienceResponse,
    MarketingAudienceSyncResponse,
)
from app.modules.marketing.models import MarketingAudience, MarketingAudienceMember
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/marketing/audiences",
    tags=["marketing-audiences"],
    dependencies=[Depends(require_active_module("marketing"))],
)
CanView = Annotated[Principal, Depends(require_permission("marketing.view"))]
CanManage = Annotated[Principal, Depends(require_permission("marketing.audience.manage"))]


def _response(audience: MarketingAudience) -> MarketingAudienceResponse:
    return MarketingAudienceResponse.model_validate(audience, from_attributes=True)


async def _audience(
    database: DatabaseSession, *, audience_id: UUID, company_id: UUID
) -> MarketingAudience:
    audience = await database.scalar(
        select(MarketingAudience).where(
            MarketingAudience.id == audience_id,
            MarketingAudience.company_id == company_id,
            MarketingAudience.archived_at.is_(None),
        )
    )
    if audience is None:
        raise HTTPException(status_code=404, detail="Público não encontrado nesta empresa.")
    return audience


@router.get("", response_model=list[MarketingAudienceResponse])
async def list_audiences(
    principal: CanView, database: DatabaseSession
) -> list[MarketingAudienceResponse]:
    context = get_request_context(principal)
    rows = (
        await database.scalars(
            select(MarketingAudience)
            .where(
                MarketingAudience.company_id == context.company_id,
                MarketingAudience.archived_at.is_(None),
            )
            .order_by(MarketingAudience.updated_at.desc())
        )
    ).all()
    return [_response(row) for row in rows]


@router.post("", response_model=MarketingAudienceResponse, status_code=status.HTTP_201_CREATED)
async def create_audience(
    payload: MarketingAudienceCreate, principal: CanManage, database: DatabaseSession
) -> MarketingAudienceResponse:
    context = get_request_context(principal)
    if payload.segment_id is not None:
        published = await database.scalar(
            text(
                "SELECT count(*) FROM customer_segments "
                "WHERE id = :segment_id AND company_id = :company_id AND status = 'published'"
            ),
            {"segment_id": payload.segment_id, "company_id": context.company_id},
        )
        if not published:
            raise HTTPException(
                status_code=422, detail="Use um segmento publicado da empresa atual."
            )
    audience = MarketingAudience(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(audience)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.audience.created",
        target_type="marketing_audience",
        target_id=audience.id,
        details={"kind": audience.kind, "segment_id": str(audience.segment_id or "")},
    )
    await database.commit()
    await database.refresh(audience)
    return _response(audience)


@router.get("/{audience_id}/members", response_model=list[MarketingAudienceMemberResponse])
async def list_members(
    audience_id: UUID, principal: CanView, database: DatabaseSession
) -> list[MarketingAudienceMemberResponse]:
    context = get_request_context(principal)
    await _audience(database, audience_id=audience_id, company_id=context.company_id)
    rows = (
        await database.scalars(
            select(MarketingAudienceMember)
            .where(
                MarketingAudienceMember.company_id == context.company_id,
                MarketingAudienceMember.audience_id == audience_id,
            )
            .order_by(MarketingAudienceMember.added_at.desc())
        )
    ).all()
    return [
        MarketingAudienceMemberResponse.model_validate(row, from_attributes=True)
        for row in rows
    ]


@router.post(
    "/{audience_id}/members",
    response_model=MarketingAudienceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    audience_id: UUID,
    payload: MarketingAudienceMemberCreate,
    principal: CanManage,
    database: DatabaseSession,
) -> MarketingAudienceMemberResponse:
    context = get_request_context(principal)
    audience = await _audience(database, audience_id=audience_id, company_id=context.company_id)
    if audience.kind != "static":
        raise HTTPException(status_code=409, detail="Sincronize públicos dinâmicos pelo segmento.")
    contact = await database.scalar(
        select(CRMContact).where(
            CRMContact.id == payload.contact_id,
            CRMContact.company_id == context.company_id,
        )
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contato não encontrado nesta empresa.")
    existing = await database.scalar(
        select(MarketingAudienceMember).where(
            MarketingAudienceMember.audience_id == audience.id,
            MarketingAudienceMember.contact_id == payload.contact_id,
        )
    )
    if existing is not None:
        return MarketingAudienceMemberResponse.model_validate(existing, from_attributes=True)
    member = MarketingAudienceMember(
        company_id=context.company_id,
        audience_id=audience.id,
        contact_id=payload.contact_id,
        source="manual",
    )
    database.add(member)
    await database.flush()
    audience.member_count = int(
        await database.scalar(
            select(func.count(MarketingAudienceMember.id)).where(
                MarketingAudienceMember.audience_id == audience.id
            )
        )
        or 0
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.audience.member_added",
        target_type="marketing_audience",
        target_id=audience.id,
        details={"contact_id": str(payload.contact_id)},
    )
    await database.commit()
    await database.refresh(member)
    return MarketingAudienceMemberResponse.model_validate(member, from_attributes=True)


@router.delete("/{audience_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    audience_id: UUID, member_id: UUID, principal: CanManage, database: DatabaseSession
) -> None:
    context = get_request_context(principal)
    audience = await _audience(database, audience_id=audience_id, company_id=context.company_id)
    if audience.kind != "static":
        raise HTTPException(status_code=409, detail="Sincronize públicos dinâmicos pelo segmento.")
    removed = await database.scalar(
        delete(MarketingAudienceMember)
        .where(
            MarketingAudienceMember.id == member_id,
            MarketingAudienceMember.audience_id == audience.id,
            MarketingAudienceMember.company_id == context.company_id,
        )
        .returning(MarketingAudienceMember.id)
    )
    if removed is None:
        raise HTTPException(status_code=404, detail="Membro não encontrado neste público.")
    audience.member_count = max(audience.member_count - 1, 0)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.audience.member_removed",
        target_type="marketing_audience",
        target_id=audience.id,
        details={"member_id": str(member_id)},
    )
    await database.commit()


@router.post("/{audience_id}/sync", response_model=MarketingAudienceSyncResponse)
async def sync_audience(
    audience_id: UUID, principal: CanManage, database: DatabaseSession
) -> MarketingAudienceSyncResponse:
    context = get_request_context(principal)
    audience = await _audience(database, audience_id=audience_id, company_id=context.company_id)
    if audience.kind != "dynamic" or audience.segment_id is None:
        raise HTTPException(status_code=409, detail="Somente públicos dinâmicos são sincronizados.")
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"marketing-audience:{context.company_id}:{audience.id}"},
    )
    counts = (
        await database.execute(
            text(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE restriction.id IS NOT NULL) AS restricted,
                       count(*) FILTER (
                           WHERE restriction.id IS NULL AND NOT EXISTS (
                               SELECT 1 FROM customer_consents consent
                               WHERE consent.company_id = member.company_id
                                 AND consent.profile_id = member.profile_id
                                 AND consent.purpose = 'marketing'
                                 AND consent.status = 'granted'
                                 AND (consent.expires_at IS NULL OR consent.expires_at > now())
                           )
                       ) AS no_consent
                FROM customer_segment_members member
                LEFT JOIN customer_processing_restrictions restriction
                  ON restriction.company_id = member.company_id
                 AND restriction.profile_id = member.profile_id
                 AND restriction.status = 'active'
                WHERE member.company_id = :company_id
                  AND member.segment_id = :segment_id
                  AND member.contact_id IS NOT NULL
                """
            ),
            {"company_id": context.company_id, "segment_id": audience.segment_id},
        )
    ).one()
    old_count = audience.member_count
    await database.execute(
        delete(MarketingAudienceMember).where(
            MarketingAudienceMember.company_id == context.company_id,
            MarketingAudienceMember.audience_id == audience.id,
            MarketingAudienceMember.source == "segment",
        )
    )
    added = int(
        (
            await database.execute(
                text(
                    """
                    WITH inserted AS (
                    INSERT INTO marketing_audience_members
                        (id, company_id, audience_id, contact_id, source)
                    SELECT gen_random_uuid(), member.company_id, :audience_id,
                           member.contact_id, 'segment'
                    FROM customer_segment_members member
                    WHERE member.company_id = :company_id
                      AND member.segment_id = :segment_id
                      AND member.contact_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM customer_processing_restrictions restriction
                          WHERE restriction.company_id = member.company_id
                            AND restriction.profile_id = member.profile_id
                            AND restriction.status = 'active'
                      )
                      AND EXISTS (
                          SELECT 1 FROM customer_consents consent
                          WHERE consent.company_id = member.company_id
                            AND consent.profile_id = member.profile_id
                            AND consent.purpose = 'marketing'
                            AND consent.status = 'granted'
                            AND (consent.expires_at IS NULL OR consent.expires_at > now())
                      )
                    ON CONFLICT (audience_id, contact_id) DO NOTHING
                    RETURNING id
                    )
                    SELECT count(*) FROM inserted
                    """
                ),
                {
                    "company_id": context.company_id,
                    "segment_id": audience.segment_id,
                    "audience_id": audience.id,
                },
            )
        ).scalar_one()
        or 0
    )
    synchronized_at = utc_now()
    audience.member_count = added
    audience.synchronized_at = synchronized_at
    audience.status = "active"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.audience.synchronized",
        target_type="marketing_audience",
        target_id=audience.id,
        details={
            "member_count": added,
            "excluded_restricted": int(counts.restricted or 0),
            "excluded_no_consent": int(counts.no_consent or 0),
        },
    )
    await database.commit()
    return MarketingAudienceSyncResponse(
        audience_id=audience.id,
        member_count=added,
        added_count=max(added - old_count, 0),
        removed_count=max(old_count - added, 0),
        excluded_restricted_count=int(counts.restricted or 0),
        excluded_no_consent_count=int(counts.no_consent or 0),
        synchronized_at=synchronized_at,
    )

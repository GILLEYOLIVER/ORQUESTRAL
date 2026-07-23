from __future__ import annotations

import re
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.crm.models import (
    CRMContact,
    CRMOpportunity,
    CRMOpportunityActivity,
    CustomerConsent,
    CustomerDataSource,
    CustomerIdentity,
    CustomerProfile,
    CustomerProfileContact,
)
from app.modules.crm.schemas import (
    CRMCustomer360Response,
    CustomerActivityResponse,
    CustomerConsentResponse,
    CustomerDataSourceResponse,
    CustomerIdentityResponse,
)

CRM_SOURCE_CODE = "orkestral_crm"


def contact_quality(contact: CRMContact) -> tuple[int, list[str]]:
    checks = (
        ("Nome", contact.name, 20),
        ("E-mail", contact.email, 20),
        ("Telefone", contact.phone, 15),
        ("Empresa", contact.company_name, 15),
        ("Cargo", contact.job_title, 10),
        ("Origem", contact.source, 10),
        ("Responsável", contact.assigned_user_id, 10),
    )
    score = sum(weight for _, value, weight in checks if value)
    issues = [f"{label} não informado" for label, value, _ in checks if not value]
    return score, issues


def _identity_material(contact: CRMContact) -> list[tuple[str, str, str]]:
    material: list[tuple[str, str, str]] = []
    if contact.email:
        normalized = str(contact.email).strip().casefold()
        local, _, domain = normalized.partition("@")
        hint = f"{local[:1]}***@{domain}" if domain else "***"
        material.append(("email", sha256(normalized.encode()).hexdigest(), hint))
    if contact.phone:
        normalized_phone = re.sub(r"\D", "", contact.phone)
        if normalized_phone:
            material.append(
                (
                    "phone",
                    sha256(normalized_phone.encode()).hexdigest(),
                    f"***{normalized_phone[-4:]}",
                )
            )
    return material


async def _crm_source(database: AsyncSession, company_id: UUID) -> CustomerDataSource:
    source = await database.scalar(
        select(CustomerDataSource).where(
            CustomerDataSource.company_id == company_id,
            CustomerDataSource.code == CRM_SOURCE_CODE,
        )
    )
    if source is None:
        source = CustomerDataSource(
            company_id=company_id,
            code=CRM_SOURCE_CODE,
            name="CRM Orkestral",
            mode="system_of_record",
            status="active",
        )
        database.add(source)
        await database.flush()
    return source


async def sync_customer_profile(
    database: AsyncSession,
    *,
    contact: CRMContact,
    actor_user_id: UUID,
) -> CustomerProfile:
    source = await _crm_source(database, contact.company_id)
    material = _identity_material(contact)
    existing_link = await database.scalar(
        select(CustomerProfileContact).where(
            CustomerProfileContact.company_id == contact.company_id,
            CustomerProfileContact.contact_id == contact.id,
        )
    )
    matching_profile_ids = set(
        await database.scalars(
            select(CustomerIdentity.profile_id).where(
                CustomerIdentity.company_id == contact.company_id,
                CustomerIdentity.value_hash.in_([item[1] for item in material]),
            )
        )
    )
    if existing_link is not None:
        profile = await database.scalar(
            select(CustomerProfile).where(
                CustomerProfile.id == existing_link.profile_id,
                CustomerProfile.company_id == contact.company_id,
            )
        )
        if profile is None:
            raise RuntimeError("Perfil canônico vinculado não foi encontrado.")
    elif len(matching_profile_ids) == 1:
        profile_id = next(iter(matching_profile_ids))
        profile = await database.scalar(
            select(CustomerProfile).where(
                CustomerProfile.id == profile_id,
                CustomerProfile.company_id == contact.company_id,
            )
        )
        if profile is None:
            raise RuntimeError("Perfil canônico correspondente não foi encontrado.")
        database.add(
            CustomerProfileContact(
                company_id=contact.company_id,
                profile_id=profile.id,
                contact_id=contact.id,
                link_role="matched",
                match_confidence=100,
            )
        )
    else:
        quality_score, _ = contact_quality(contact)
        profile = CustomerProfile(
            company_id=contact.company_id,
            master_contact_id=contact.id,
            display_name=contact.name,
            profile_type="person",
            lifecycle_status=contact.status,
            quality_score=quality_score,
            created_by_user_id=actor_user_id,
        )
        database.add(profile)
        await database.flush()
        database.add(
            CustomerProfileContact(
                company_id=contact.company_id,
                profile_id=profile.id,
                contact_id=contact.id,
                link_role="master",
                match_confidence=100 if not matching_profile_ids else 50,
            )
        )

    if profile.master_contact_id == contact.id:
        profile.display_name = contact.name
        profile.lifecycle_status = contact.status
        profile.quality_score = contact_quality(contact)[0]
        profile.updated_at = utc_now()

    for identity_type, value_hash, display_hint in material:
        existing_identity = await database.scalar(
            select(CustomerIdentity).where(
                CustomerIdentity.company_id == contact.company_id,
                CustomerIdentity.identity_type == identity_type,
                CustomerIdentity.value_hash == value_hash,
            )
        )
        if existing_identity is None:
            database.add(
                CustomerIdentity(
                    company_id=contact.company_id,
                    profile_id=profile.id,
                    data_source_id=source.id,
                    identity_type=identity_type,
                    value_hash=value_hash,
                    display_hint=display_hint,
                    verified=False,
                )
            )
    await database.flush()
    return profile


async def customer_profile_for_contact(
    database: AsyncSession, *, company_id: UUID, contact_id: UUID
) -> CustomerProfile:
    profile = await database.scalar(
        select(CustomerProfile)
        .join(
            CustomerProfileContact,
            CustomerProfileContact.profile_id == CustomerProfile.id,
        )
        .where(
            CustomerProfile.company_id == company_id,
            CustomerProfileContact.company_id == company_id,
            CustomerProfileContact.contact_id == contact_id,
        )
    )
    if profile is None:
        raise RuntimeError("O contato ainda não possui perfil canônico.")
    return profile


async def customer_360(database: AsyncSession, *, contact: CRMContact) -> CRMCustomer360Response:
    profile = await customer_profile_for_contact(
        database, company_id=contact.company_id, contact_id=contact.id
    )
    linked_contact_ids = list(
        await database.scalars(
            select(CustomerProfileContact.contact_id)
            .where(
                CustomerProfileContact.company_id == contact.company_id,
                CustomerProfileContact.profile_id == profile.id,
            )
            .order_by(CustomerProfileContact.linked_at)
        )
    )
    identities = list(
        await database.scalars(
            select(CustomerIdentity)
            .where(
                CustomerIdentity.company_id == contact.company_id,
                CustomerIdentity.profile_id == profile.id,
            )
            .order_by(CustomerIdentity.identity_type, CustomerIdentity.created_at)
        )
    )
    source_ids = {identity.data_source_id for identity in identities}
    sources = (
        list(
            await database.scalars(
                select(CustomerDataSource).where(
                    CustomerDataSource.company_id == contact.company_id,
                    CustomerDataSource.id.in_(source_ids),
                )
            )
        )
        if source_ids
        else []
    )
    source_by_id = {source.id: source for source in sources}
    consents = list(
        await database.scalars(
            select(CustomerConsent)
            .where(
                CustomerConsent.company_id == contact.company_id,
                CustomerConsent.profile_id == profile.id,
            )
            .order_by(CustomerConsent.captured_at.desc())
        )
    )
    opportunity_count, open_value = (
        await database.execute(
            select(
                func.count(CRMOpportunity.id),
                func.coalesce(func.sum(CRMOpportunity.amount), Decimal("0")),
            ).where(
                CRMOpportunity.company_id == contact.company_id,
                CRMOpportunity.contact_id.in_(linked_contact_ids),
                CRMOpportunity.deleted_at.is_(None),
                CRMOpportunity.status == "open",
            )
        )
    ).one()
    activities = list(
        await database.scalars(
            select(CRMOpportunityActivity)
            .where(
                CRMOpportunityActivity.company_id == contact.company_id,
                CRMOpportunityActivity.contact_id.in_(linked_contact_ids),
            )
            .order_by(CRMOpportunityActivity.occurred_at.desc())
            .limit(20)
        )
    )
    material = _identity_material(contact)
    candidate_profile_ids = set(
        await database.scalars(
            select(CustomerIdentity.profile_id).where(
                CustomerIdentity.company_id == contact.company_id,
                CustomerIdentity.value_hash.in_([item[1] for item in material]),
                CustomerIdentity.profile_id != profile.id,
            )
        )
    )
    _, quality_issues = contact_quality(contact)
    return CRMCustomer360Response(
        profile_id=profile.id,
        display_name=profile.display_name,
        profile_type=profile.profile_type,
        lifecycle_status=profile.lifecycle_status,
        quality_score=profile.quality_score,
        quality_issues=quality_issues,
        master_contact_id=profile.master_contact_id,
        linked_contact_ids=linked_contact_ids,
        duplicate_candidate_profile_ids=sorted(candidate_profile_ids, key=str),
        identities=[
            CustomerIdentityResponse(
                id=identity.id,
                identity_type=identity.identity_type,
                display_hint=identity.display_hint,
                verified=identity.verified,
                source_code=source_by_id[identity.data_source_id].code,
                source_name=source_by_id[identity.data_source_id].name,
            )
            for identity in identities
            if identity.data_source_id in source_by_id
        ],
        sources=[
            CustomerDataSourceResponse.model_validate(source, from_attributes=True)
            for source in sources
        ],
        consents=[
            CustomerConsentResponse.model_validate(consent, from_attributes=True)
            for consent in consents
        ],
        opportunity_count=int(opportunity_count or 0),
        open_opportunity_value=Decimal(open_value or 0),
        recent_activities=[
            CustomerActivityResponse.model_validate(activity, from_attributes=True)
            for activity in activities
        ],
    )

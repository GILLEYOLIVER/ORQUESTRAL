from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, overload
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import apply_tenant_database_context
from app.core.dependencies import (
    DatabaseSession,
    RedisClient,
    RequestSettings,
)
from app.core.field_encryption import FieldDecryptionError, decrypt_text, encrypt_text
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.support.channels_schemas import (
    SupportChannelEndpointCreate,
    SupportChannelEndpointResponse,
    SupportChannelEndpointUpdate,
    SupportChannelIngressEventResponse,
    SupportChannelIngressRequest,
    SupportChannelIngressResponse,
    SupportChannelSecretResponse,
)
from app.modules.support.channels_security import (
    new_channel_public_key,
    new_channel_secret,
    protected_reference,
    secret_fingerprint,
    valid_idempotency_key,
    verify_channel_request,
)
from app.modules.support.models import (
    SupportChannelEndpoint,
    SupportChannelIngressEvent,
    SupportQueue,
    SupportTicket,
)

router = APIRouter(prefix="/support/channels", tags=["support-channels"])
ingress_router = APIRouter(prefix="/support/ingress", tags=["support-ingress"])

CanViewTickets = Annotated[Principal, Depends(require_permission("support.tickets.view"))]
CanUpdateTickets = Annotated[Principal, Depends(require_permission("support.tickets.update"))]

_CHANNEL_TO_TICKET = {
    "email": "email",
    "chat": "web",
    "whatsapp": "whatsapp",
    "form": "web",
    "portal": "web",
}


def _associated_data(company_id: UUID, public_key: str) -> str:
    return f"support-channel-secret:{company_id}:{public_key}"


def _webhook_path(endpoint: SupportChannelEndpoint) -> str:
    return f"/api/support/ingress/{endpoint.company_id}/{endpoint.public_key}"


@overload
def _endpoint_response(
    endpoint: SupportChannelEndpoint,
    *,
    secret: str,
) -> SupportChannelSecretResponse: ...


@overload
def _endpoint_response(
    endpoint: SupportChannelEndpoint,
    *,
    secret: None = None,
) -> SupportChannelEndpointResponse: ...


def _endpoint_response(
    endpoint: SupportChannelEndpoint,
    *,
    secret: str | None = None,
) -> SupportChannelEndpointResponse | SupportChannelSecretResponse:
    values = {
        "id": endpoint.id,
        "name": endpoint.name,
        "channel": endpoint.channel,
        "status": endpoint.status,
        "default_queue_id": endpoint.default_queue_id,
        "default_priority": endpoint.default_priority,
        "consent_required": endpoint.consent_required,
        "secret_fingerprint": endpoint.secret_fingerprint,
        "webhook_path": _webhook_path(endpoint),
        "last_received_at": endpoint.last_received_at,
        "created_at": endpoint.created_at,
        "updated_at": endpoint.updated_at,
    }
    if secret is not None:
        return SupportChannelSecretResponse(**values, webhook_secret=secret)
    return SupportChannelEndpointResponse(**values)


async def _validated_queue_id(
    database: DatabaseSession,
    *,
    company_id: UUID,
    queue_id: UUID | None,
) -> UUID | None:
    if queue_id is None:
        return None
    found = await database.scalar(
        select(SupportQueue.id).where(
            SupportQueue.company_id == company_id,
            SupportQueue.id == queue_id,
            SupportQueue.is_active.is_(True),
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Fila de suporte não encontrada.")
    return found


@router.get("", response_model=list[SupportChannelEndpointResponse])
async def list_support_channels(
    principal: CanViewTickets,
    database: DatabaseSession,
) -> list[SupportChannelEndpointResponse]:
    context = get_request_context(principal)
    endpoints = list(
        await database.scalars(
            select(SupportChannelEndpoint)
            .where(SupportChannelEndpoint.company_id == context.company_id)
            .order_by(SupportChannelEndpoint.created_at.desc())
        )
    )
    return [_endpoint_response(endpoint) for endpoint in endpoints]


@router.post(
    "",
    response_model=SupportChannelSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_support_channel(
    payload: SupportChannelEndpointCreate,
    principal: CanUpdateTickets,
    database: DatabaseSession,
    settings: RequestSettings,
) -> SupportChannelSecretResponse:
    context = get_request_context(principal)
    queue_id = await _validated_queue_id(
        database,
        company_id=context.company_id,
        queue_id=payload.default_queue_id,
    )
    public_key = new_channel_public_key()
    secret = new_channel_secret()
    endpoint = SupportChannelEndpoint(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
        name=payload.name,
        channel=payload.channel,
        public_key=public_key,
        encrypted_secret=encrypt_text(
            settings,
            secret,
            associated_data=_associated_data(context.company_id, public_key),
        ),
        secret_fingerprint=secret_fingerprint(secret),
        default_queue_id=queue_id,
        default_priority=payload.default_priority,
        consent_required=payload.consent_required,
    )
    database.add(endpoint)
    try:
        await database.flush()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe um canal com esse nome e tipo.",
        ) from exc
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.channel.created",
        target_type="support_channel_endpoint",
        target_id=endpoint.id,
        details={"channel": endpoint.channel, "fingerprint": endpoint.secret_fingerprint},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.channel.configuration_updated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"endpoint_id": str(endpoint.id), "operation": "created"},
        ),
    )
    await database.commit()
    await database.refresh(endpoint)
    return _endpoint_response(endpoint, secret=secret)


@router.patch("/{endpoint_id}", response_model=SupportChannelEndpointResponse)
async def update_support_channel(
    endpoint_id: UUID,
    payload: SupportChannelEndpointUpdate,
    principal: CanUpdateTickets,
    database: DatabaseSession,
) -> SupportChannelEndpointResponse:
    context = get_request_context(principal)
    endpoint = await database.scalar(
        select(SupportChannelEndpoint).where(
            SupportChannelEndpoint.company_id == context.company_id,
            SupportChannelEndpoint.id == endpoint_id,
        )
    )
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado.")
    values = payload.model_dump(exclude_unset=True)
    if "default_queue_id" in values:
        values["default_queue_id"] = await _validated_queue_id(
            database,
            company_id=context.company_id,
            queue_id=payload.default_queue_id,
        )
    for field, value in values.items():
        setattr(endpoint, field, value)
    endpoint.updated_by_user_id = context.user_id
    endpoint.updated_at = datetime.now(UTC)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.channel.updated",
        target_type="support_channel_endpoint",
        target_id=endpoint.id,
        details={"fields": sorted(values)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.channel.configuration_updated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"endpoint_id": str(endpoint.id), "operation": "updated"},
        ),
    )
    await database.commit()
    await database.refresh(endpoint)
    return _endpoint_response(endpoint)


@router.post(
    "/{endpoint_id}/rotate-secret",
    response_model=SupportChannelSecretResponse,
)
async def rotate_support_channel_secret(
    endpoint_id: UUID,
    principal: CanUpdateTickets,
    database: DatabaseSession,
    settings: RequestSettings,
) -> SupportChannelSecretResponse:
    context = get_request_context(principal)
    endpoint = await database.scalar(
        select(SupportChannelEndpoint).where(
            SupportChannelEndpoint.company_id == context.company_id,
            SupportChannelEndpoint.id == endpoint_id,
        )
    )
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado.")
    secret = new_channel_secret()
    endpoint.encrypted_secret = encrypt_text(
        settings,
        secret,
        associated_data=_associated_data(context.company_id, endpoint.public_key),
    )
    endpoint.secret_fingerprint = secret_fingerprint(secret)
    endpoint.updated_by_user_id = context.user_id
    endpoint.updated_at = datetime.now(UTC)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.channel.secret_rotated",
        target_type="support_channel_endpoint",
        target_id=endpoint.id,
        details={"fingerprint": endpoint.secret_fingerprint},
    )
    await database.commit()
    await database.refresh(endpoint)
    return _endpoint_response(endpoint, secret=secret)


@router.get(
    "/{endpoint_id}/events",
    response_model=list[SupportChannelIngressEventResponse],
)
async def list_support_channel_events(
    endpoint_id: UUID,
    principal: CanViewTickets,
    database: DatabaseSession,
) -> list[SupportChannelIngressEvent]:
    context = get_request_context(principal)
    endpoint_exists = await database.scalar(
        select(SupportChannelEndpoint.id).where(
            SupportChannelEndpoint.company_id == context.company_id,
            SupportChannelEndpoint.id == endpoint_id,
        )
    )
    if endpoint_exists is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado.")
    return list(
        await database.scalars(
            select(SupportChannelIngressEvent)
            .where(
                SupportChannelIngressEvent.company_id == context.company_id,
                SupportChannelIngressEvent.endpoint_id == endpoint_id,
            )
            .order_by(SupportChannelIngressEvent.received_at.desc())
            .limit(50)
        )
    )


@ingress_router.post(
    "/{company_id}/{public_key}",
    response_model=SupportChannelIngressResponse,
    name="receive_support_channel_ingress",
)
async def receive_support_channel_ingress(
    company_id: UUID,
    public_key: str,
    request: Request,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
    x_orkestral_timestamp: Annotated[str | None, Header()] = None,
    x_orkestral_signature: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> SupportChannelIngressResponse:
    body = await request.body()
    if len(body) > settings.support_ingress_max_payload_bytes:
        raise HTTPException(status_code=413, detail="O payload excede o limite permitido.")
    if not valid_idempotency_key(idempotency_key):
        raise HTTPException(
            status_code=400,
            detail="Envie uma chave Idempotency-Key válida.",
        )
    external_event_id = (idempotency_key or "").strip()
    external_event_hash = protected_reference(settings.encryption_key, external_event_id)
    if external_event_hash is None:
        raise HTTPException(status_code=400, detail="Chave idempotente inválida.")
    client_ip = request.client.host if request.client else "unknown"
    count = int(await redis.incr(f"rate:support-ingress:{public_key}:{client_ip}"))
    if count == 1:
        await redis.expire(f"rate:support-ingress:{public_key}:{client_ip}", 60)
    if count > settings.support_ingress_rate_limit:
        raise HTTPException(status_code=429, detail="Limite de chamadas excedido.")

    await apply_tenant_database_context(
        database,
        company_id=company_id,
        access_mode="standard",
    )
    endpoint = await database.scalar(
        select(SupportChannelEndpoint).where(
            SupportChannelEndpoint.company_id == company_id,
            SupportChannelEndpoint.public_key == public_key,
            SupportChannelEndpoint.status == "active",
        )
    )
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado.")
    try:
        secret = decrypt_text(
            settings,
            endpoint.encrypted_secret,
            associated_data=_associated_data(company_id, public_key),
        )
    except FieldDecryptionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Canal temporariamente indisponível.",
        ) from exc
    if not verify_channel_request(
        secret,
        x_orkestral_timestamp,
        body,
        x_orkestral_signature,
        max_age_seconds=settings.support_ingress_signature_max_age_seconds,
    ):
        raise HTTPException(status_code=401, detail="Assinatura inválida ou expirada.")
    try:
        raw_payload = json.loads(body.decode("utf-8"))
        payload = SupportChannelIngressRequest.model_validate(raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Payload de atendimento inválido.") from exc
    if endpoint.consent_required and payload.consent_granted is not True:
        raise HTTPException(status_code=422, detail="O consentimento é obrigatório neste canal.")

    existing = await database.scalar(
        select(SupportChannelIngressEvent).where(
            SupportChannelIngressEvent.company_id == company_id,
            SupportChannelIngressEvent.endpoint_id == endpoint.id,
            SupportChannelIngressEvent.external_event_id == external_event_hash,
        )
    )
    if existing is not None:
        return SupportChannelIngressResponse(
            duplicate=True,
            event_id=existing.id,
            ticket_id=existing.ticket_id,
        )

    ticket = SupportTicket(
        company_id=company_id,
        created_by_user_id=endpoint.created_by_user_id,
        subject=payload.subject,
        description=payload.message,
        status="open",
        priority=endpoint.default_priority,
        channel=_CHANNEL_TO_TICKET[endpoint.channel],
        queue_id=endpoint.default_queue_id,
        language_code=payload.language_code,
    )
    database.add(ticket)
    await database.flush()
    ingress_event = SupportChannelIngressEvent(
        company_id=company_id,
        endpoint_id=endpoint.id,
        ticket_id=ticket.id,
        external_event_id=external_event_hash,
        payload_hash=hashlib.sha256(body).hexdigest(),
        sender_reference_hash=protected_reference(
            settings.encryption_key,
            payload.sender_reference,
        ),
        source_ip_hash=protected_reference(settings.encryption_key, client_ip),
    )
    database.add(ingress_event)
    endpoint.last_received_at = datetime.now(UTC)
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=endpoint.created_by_user_id,
        action="support.channel.ingress.accepted",
        target_type="support_ticket",
        target_id=ticket.id,
        details={
            "channel": endpoint.channel,
            "endpoint_id": str(endpoint.id),
            "event_id": str(ingress_event.id),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.channel.message_received",
            company_id=company_id,
            actor_user_id=endpoint.created_by_user_id,
            classification="internal",
            payload={
                "channel": endpoint.channel,
                "endpoint_id": str(endpoint.id),
                "ticket_id": str(ticket.id),
            },
        ),
    )
    try:
        await database.commit()
    except IntegrityError:
        await database.rollback()
        await apply_tenant_database_context(
            database,
            company_id=company_id,
            access_mode="standard",
        )
        duplicate = await database.scalar(
            select(SupportChannelIngressEvent).where(
                SupportChannelIngressEvent.company_id == company_id,
                SupportChannelIngressEvent.endpoint_id == endpoint.id,
                SupportChannelIngressEvent.external_event_id == external_event_hash,
            )
        )
        if duplicate is None:
            raise
        return SupportChannelIngressResponse(
            duplicate=True,
            event_id=duplicate.id,
            ticket_id=duplicate.ticket_id,
        )
    return SupportChannelIngressResponse(event_id=ingress_event.id, ticket_id=ticket.id)

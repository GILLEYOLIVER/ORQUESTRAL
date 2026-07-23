from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.customer_governance_schemas import (
    CustomerLineageCreate,
    CustomerLineageResponse,
    CustomerMatchRuleCreate,
    CustomerMatchRuleResponse,
    CustomerMatchScanResponse,
    CustomerMergeCaseResponse,
)

_MERGE_TABLES = (
    ("customer_profile_contacts", "contact_id"),
    ("customer_identities", "id"),
    ("customer_consents", "id"),
    ("customer_field_lineage", "id"),
)
_MERGE_SELECT_QUERIES = {
    "customer_profile_contacts": text(
        """
        SELECT contact_id AS item_id FROM customer_profile_contacts
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        FOR UPDATE
        """
    ),
    "customer_identities": text(
        """
        SELECT id AS item_id FROM customer_identities
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        FOR UPDATE
        """
    ),
    "customer_consents": text(
        """
        SELECT id AS item_id FROM customer_consents
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        FOR UPDATE
        """
    ),
    "customer_field_lineage": text(
        """
        SELECT id AS item_id FROM customer_field_lineage
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        FOR UPDATE
        """
    ),
}
_MERGE_UPDATE_QUERIES = {
    "customer_profile_contacts": text(
        """
        UPDATE customer_profile_contacts SET profile_id = :primary_profile_id
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        """
    ),
    "customer_identities": text(
        """
        UPDATE customer_identities SET profile_id = :primary_profile_id
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        """
    ),
    "customer_consents": text(
        """
        UPDATE customer_consents SET profile_id = :primary_profile_id
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        """
    ),
    "customer_field_lineage": text(
        """
        UPDATE customer_field_lineage SET profile_id = :primary_profile_id
        WHERE company_id = :company_id AND profile_id = :secondary_profile_id
        """
    ),
}
_MERGE_REVERT_QUERIES = {
    "customer_profile_contacts": text(
        """
        UPDATE customer_profile_contacts SET profile_id = :from_profile_id
        WHERE company_id = :company_id AND contact_id = :item_id
          AND profile_id = :to_profile_id
        """
    ),
    "customer_identities": text(
        """
        UPDATE customer_identities SET profile_id = :from_profile_id
        WHERE company_id = :company_id AND id = :item_id
          AND profile_id = :to_profile_id
        """
    ),
    "customer_consents": text(
        """
        UPDATE customer_consents SET profile_id = :from_profile_id
        WHERE company_id = :company_id AND id = :item_id
          AND profile_id = :to_profile_id
        """
    ),
    "customer_field_lineage": text(
        """
        UPDATE customer_field_lineage SET profile_id = :from_profile_id
        WHERE company_id = :company_id AND id = :item_id
          AND profile_id = :to_profile_id
        """
    ),
}


def _normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(character for character in decomposed if not unicodedata.combining(character))
        .casefold()
        .split()
    )


def name_similarity(left: str, right: str) -> float:
    normalized_left = _normalized_name(left)
    normalized_right = _normalized_name(right)
    if not normalized_left or not normalized_right:
        return 0
    return round(SequenceMatcher(None, normalized_left, normalized_right).ratio(), 4)


def _rule(row: Any) -> CustomerMatchRuleResponse:
    values = row._mapping
    return CustomerMatchRuleResponse(
        id=values["id"],
        version=values["version"],
        name=values["name"],
        status=values["status"],
        threshold=float(values["threshold"]),
        rules=values["rules"],
        created_at=values["created_at"],
        published_at=values["published_at"],
    )


def _merge_case(row: Any) -> CustomerMergeCaseResponse:
    values = row._mapping
    return CustomerMergeCaseResponse(
        id=values["id"],
        primary_profile_id=values["primary_profile_id"],
        secondary_profile_id=values["secondary_profile_id"],
        primary_name=values["primary_name"],
        secondary_name=values["secondary_name"],
        status=values["status"],
        score=float(values["score"]),
        reasons=list(values["reasons"]),
        rule_version=values["rule_version"],
        decision_note=values["decision_note"],
        created_at=values["created_at"],
        reviewed_at=values["reviewed_at"],
        reverted_at=values["reverted_at"],
    )


async def _audit(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    subject_type: str,
    subject_id: UUID,
    payload: dict[str, Any],
) -> None:
    await database.execute(
        text(
            """
            INSERT INTO customer_data_governance_events (
                company_id, actor_user_id, event_type, subject_type, subject_id, payload
            ) VALUES (
                :company_id, :actor_user_id, :event_type, :subject_type, :subject_id,
                CAST(:payload AS jsonb)
            )
            """
        ),
        {
            "company_id": company_id,
            "actor_user_id": actor_user_id,
            "event_type": event_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "payload": json.dumps(payload),
        },
    )


async def list_match_rules(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerMatchRuleResponse]:
    rows = await database.execute(
        text(
            """
            SELECT id, version, name, status, threshold, rules, created_at, published_at
            FROM customer_match_rules
            WHERE company_id = :company_id
            ORDER BY version DESC
            """
        ),
        {"company_id": company_id},
    )
    return [_rule(row) for row in rows]


async def create_match_rule(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CustomerMatchRuleCreate,
) -> CustomerMatchRuleResponse:
    row = (
        await database.execute(
            text(
                """
                INSERT INTO customer_match_rules (
                    company_id, version, name, status, threshold, rules, created_by_user_id
                )
                SELECT
                    :company_id,
                    COALESCE(MAX(version), 0) + 1,
                    :name,
                    'draft',
                    :threshold,
                    CAST(:rules AS jsonb),
                    :actor_user_id
                FROM customer_match_rules
                WHERE company_id = :company_id
                RETURNING id, version, name, status, threshold, rules, created_at, published_at
                """
            ),
            {
                "company_id": company_id,
                "name": payload.name,
                "threshold": payload.threshold,
                "rules": json.dumps(payload.rules),
                "actor_user_id": actor_user_id,
            },
        )
    ).one()
    response = _rule(row)
    await _audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.match_rule.created",
        subject_type="match_rule",
        subject_id=response.id,
        payload={"version": response.version, "threshold": response.threshold},
    )
    return response


async def publish_match_rule(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    rule_id: UUID,
) -> CustomerMatchRuleResponse:
    locked = (
        await database.execute(
            text(
                """
                SELECT id, status
                FROM customer_match_rules
                WHERE company_id = :company_id AND id = :rule_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "rule_id": rule_id},
        )
    ).one_or_none()
    if locked is None:
        raise LookupError("Regra de correspondência não encontrada.")
    if locked.status != "draft":
        raise ValueError("Somente uma regra em rascunho pode ser publicada.")
    await database.execute(
        text(
            """
            UPDATE customer_match_rules
            SET status = 'retired'
            WHERE company_id = :company_id AND status = 'published'
            """
        ),
        {"company_id": company_id},
    )
    row = (
        await database.execute(
            text(
                """
                UPDATE customer_match_rules
                SET status = 'published', published_at = now()
                WHERE company_id = :company_id AND id = :rule_id
                RETURNING id, version, name, status, threshold, rules, created_at, published_at
                """
            ),
            {"company_id": company_id, "rule_id": rule_id},
        )
    ).one()
    response = _rule(row)
    await _audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.match_rule.published",
        subject_type="match_rule",
        subject_id=response.id,
        payload={"version": response.version},
    )
    return response


async def scan_match_candidates(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
) -> CustomerMatchScanResponse:
    rule_row = (
        await database.execute(
            text(
                """
                SELECT id, version, threshold, rules
                FROM customer_match_rules
                WHERE company_id = :company_id AND status = 'published'
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"company_id": company_id},
        )
    ).one_or_none()
    if rule_row is None:
        raise ValueError("Publique uma regra de correspondência antes de analisar os perfis.")

    profile_rows = (
        await database.execute(
            text(
                """
                SELECT id, display_name
                FROM customer_profiles
                WHERE company_id = :company_id
                  AND status = 'active'
                  AND merged_into_profile_id IS NULL
                ORDER BY created_at
                LIMIT 500
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    identity_rows = (
        await database.execute(
            text(
                """
                SELECT profile_id, identity_type, value_hash
                FROM customer_identities
                WHERE company_id = :company_id
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    identities: dict[UUID, set[tuple[str, str]]] = defaultdict(set)
    for identity in identity_rows:
        identities[identity.profile_id].add((identity.identity_type, identity.value_hash))

    minimum_name_length = int(rule_row.rules.get("minimum_name_length", 4))
    threshold = float(rule_row.threshold)
    created = 0
    for index, primary in enumerate(profile_rows):
        for secondary in profile_rows[index + 1 :]:
            reasons: list[str] = []
            exact_identity = bool(identities[primary.id] & identities[secondary.id])
            similarity = name_similarity(primary.display_name, secondary.display_name)
            if exact_identity:
                score = 1.0
                reasons.append("Identidade exata encontrada em duas fontes.")
            else:
                score = similarity
            if (
                len(_normalized_name(primary.display_name)) >= minimum_name_length
                and similarity >= threshold
            ):
                reasons.append(f"Nomes semelhantes ({similarity:.0%}).")
            if score < threshold or not reasons:
                continue
            result = await database.execute(
                text(
                    """
                    INSERT INTO customer_profile_merge_cases (
                        company_id, primary_profile_id, secondary_profile_id,
                        status, score, reasons, match_rule_id, rule_version,
                        requested_by_user_id
                    )
                    SELECT
                        :company_id, :primary_profile_id, :secondary_profile_id,
                        'pending', :score, CAST(:reasons AS jsonb), :match_rule_id,
                        :rule_version, :actor_user_id
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM customer_profile_merge_cases
                        WHERE company_id = :company_id
                          AND status = 'pending'
                          AND (
                            (
                                primary_profile_id = :primary_profile_id
                                AND secondary_profile_id = :secondary_profile_id
                            )
                            OR (
                                primary_profile_id = :secondary_profile_id
                                AND secondary_profile_id = :primary_profile_id
                            )
                          )
                    )
                    RETURNING id
                    """
                ),
                {
                    "company_id": company_id,
                    "primary_profile_id": primary.id,
                    "secondary_profile_id": secondary.id,
                    "score": score,
                    "reasons": json.dumps(reasons),
                    "match_rule_id": rule_row.id,
                    "rule_version": rule_row.version,
                    "actor_user_id": actor_user_id,
                },
            )
            if result.one_or_none() is not None:
                created += 1

    scan_id = rule_row.id
    await _audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.match_scan.completed",
        subject_type="match_rule",
        subject_id=scan_id,
        payload={
            "rule_version": rule_row.version,
            "scanned_profiles": len(profile_rows),
            "candidates_created": created,
        },
    )
    return CustomerMatchScanResponse(
        rule_version=rule_row.version,
        scanned_profiles=len(profile_rows),
        candidates_created=created,
    )


async def list_merge_cases(
    database: AsyncSession,
    *,
    company_id: UUID,
    case_status: str | None,
) -> list[CustomerMergeCaseResponse]:
    rows = await database.execute(
        text(
            """
            SELECT
                merge_case.id,
                merge_case.primary_profile_id,
                merge_case.secondary_profile_id,
                primary_profile.display_name AS primary_name,
                secondary_profile.display_name AS secondary_name,
                merge_case.status,
                merge_case.score,
                merge_case.reasons,
                merge_case.rule_version,
                merge_case.decision_note,
                merge_case.created_at,
                merge_case.reviewed_at,
                merge_case.reverted_at
            FROM customer_profile_merge_cases AS merge_case
            JOIN customer_profiles AS primary_profile
              ON primary_profile.id = merge_case.primary_profile_id
             AND primary_profile.company_id = merge_case.company_id
            JOIN customer_profiles AS secondary_profile
              ON secondary_profile.id = merge_case.secondary_profile_id
             AND secondary_profile.company_id = merge_case.company_id
            WHERE merge_case.company_id = :company_id
              AND (
                CAST(:case_status AS VARCHAR) IS NULL
                OR merge_case.status = CAST(:case_status AS VARCHAR)
              )
            ORDER BY merge_case.created_at DESC
            LIMIT 200
            """
        ),
        {"company_id": company_id, "case_status": case_status},
    )
    return [_merge_case(row) for row in rows]


async def decide_merge_case(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    case_id: UUID,
    decision: str,
    note: str,
) -> CustomerMergeCaseResponse:
    merge_case = (
        await database.execute(
            text(
                """
                SELECT *
                FROM customer_profile_merge_cases
                WHERE company_id = :company_id AND id = :case_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "case_id": case_id},
        )
    ).one_or_none()
    if merge_case is None:
        raise LookupError("Caso de possível duplicidade não encontrado.")
    if merge_case.status != "pending":
        raise ValueError("Este caso já recebeu uma decisão.")

    if decision == "approved":
        for table_name, _item_column in _MERGE_TABLES:
            item_rows = (
                await database.execute(
                    _MERGE_SELECT_QUERIES[table_name],
                    {
                        "company_id": company_id,
                        "secondary_profile_id": merge_case.secondary_profile_id,
                    },
                )
            ).all()
            for item in item_rows:
                await database.execute(
                    text(
                        """
                        INSERT INTO customer_profile_merge_items (
                            company_id, merge_case_id, item_type, item_id,
                            from_profile_id, to_profile_id
                        ) VALUES (
                            :company_id, :case_id, :item_type, :item_id,
                            :from_profile_id, :to_profile_id
                        )
                        """
                    ),
                    {
                        "company_id": company_id,
                        "case_id": case_id,
                        "item_type": table_name,
                        "item_id": item.item_id,
                        "from_profile_id": merge_case.secondary_profile_id,
                        "to_profile_id": merge_case.primary_profile_id,
                    },
                )
            await database.execute(
                _MERGE_UPDATE_QUERIES[table_name],
                {
                    "company_id": company_id,
                    "primary_profile_id": merge_case.primary_profile_id,
                    "secondary_profile_id": merge_case.secondary_profile_id,
                },
            )
        await database.execute(
            text(
                """
                UPDATE customer_profiles
                SET status = 'merged',
                    merged_into_profile_id = :primary_profile_id,
                    updated_at = now()
                WHERE company_id = :company_id AND id = :secondary_profile_id
                """
            ),
            {
                "company_id": company_id,
                "primary_profile_id": merge_case.primary_profile_id,
                "secondary_profile_id": merge_case.secondary_profile_id,
            },
        )

    await database.execute(
        text(
            """
            UPDATE customer_profile_merge_cases
            SET status = :decision,
                decision_note = :note,
                reviewed_by_user_id = :actor_user_id,
                reviewed_at = now()
            WHERE company_id = :company_id AND id = :case_id
            """
        ),
        {
            "company_id": company_id,
            "case_id": case_id,
            "decision": decision,
            "note": note,
            "actor_user_id": actor_user_id,
        },
    )
    await _audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type=f"customer.merge.{decision}",
        subject_type="merge_case",
        subject_id=case_id,
        payload={"decision": decision, "note": note},
    )
    cases = await list_merge_cases(database, company_id=company_id, case_status=None)
    return next(item for item in cases if item.id == case_id)


async def revert_merge_case(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    case_id: UUID,
    note: str,
) -> CustomerMergeCaseResponse:
    merge_case = (
        await database.execute(
            text(
                """
                SELECT *
                FROM customer_profile_merge_cases
                WHERE company_id = :company_id AND id = :case_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "case_id": case_id},
        )
    ).one_or_none()
    if merge_case is None:
        raise LookupError("Caso de fusão não encontrado.")
    if merge_case.status != "approved":
        raise ValueError("Somente uma fusão aprovada pode ser desfeita.")

    items = (
        await database.execute(
            text(
                """
                SELECT item_type, item_id, from_profile_id, to_profile_id
                FROM customer_profile_merge_items
                WHERE company_id = :company_id AND merge_case_id = :case_id
                ORDER BY created_at DESC
                """
            ),
            {"company_id": company_id, "case_id": case_id},
        )
    ).all()
    for item in items:
        await database.execute(
            _MERGE_REVERT_QUERIES[item.item_type],
            {
                "company_id": company_id,
                "from_profile_id": item.from_profile_id,
                "to_profile_id": item.to_profile_id,
                "item_id": item.item_id,
            },
        )
    await database.execute(
        text(
            """
            UPDATE customer_profiles
            SET status = 'active', merged_into_profile_id = NULL, updated_at = now()
            WHERE company_id = :company_id AND id = :secondary_profile_id
            """
        ),
        {
            "company_id": company_id,
            "secondary_profile_id": merge_case.secondary_profile_id,
        },
    )
    await database.execute(
        text(
            """
            UPDATE customer_profile_merge_cases
            SET status = 'reverted',
                decision_note = decision_note || E'\nReversão: ' || :note,
                reverted_by_user_id = :actor_user_id,
                reverted_at = now()
            WHERE company_id = :company_id AND id = :case_id
            """
        ),
        {
            "company_id": company_id,
            "case_id": case_id,
            "actor_user_id": actor_user_id,
            "note": note,
        },
    )
    await _audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.merge.reverted",
        subject_type="merge_case",
        subject_id=case_id,
        payload={"note": note},
    )
    cases = await list_merge_cases(database, company_id=company_id, case_status=None)
    return next(item for item in cases if item.id == case_id)


async def record_lineage(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    profile_id: UUID,
    payload: CustomerLineageCreate,
) -> CustomerLineageResponse:
    exists = (
        await database.execute(
            text(
                """
                SELECT id
                FROM customer_profiles
                WHERE company_id = :company_id AND id = :profile_id
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    ).one_or_none()
    if exists is None:
        raise LookupError("Perfil de cliente não encontrado.")
    fingerprint = hashlib.sha256(payload.observed_value.encode("utf-8")).hexdigest()
    if payload.selected:
        await database.execute(
            text(
                """
                UPDATE customer_field_lineage
                SET selected = false
                WHERE company_id = :company_id
                  AND profile_id = :profile_id
                  AND field_name = :field_name
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "field_name": payload.field_name,
            },
        )
    row = (
        await database.execute(
            text(
                """
                INSERT INTO customer_field_lineage (
                    company_id, profile_id, field_name, value_fingerprint,
                    source_id, source_record_id, classification, selected,
                    recorded_by_user_id
                ) VALUES (
                    :company_id, :profile_id, :field_name, :value_fingerprint,
                    :source_id, :source_record_id, :classification, :selected,
                    :actor_user_id
                )
                RETURNING id, profile_id, field_name, value_fingerprint, source_id,
                          source_record_id, classification, selected, observed_at,
                          recorded_by_user_id
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "field_name": payload.field_name,
                "value_fingerprint": fingerprint,
                "source_id": payload.source_id,
                "source_record_id": payload.source_record_id,
                "classification": payload.classification,
                "selected": payload.selected,
                "actor_user_id": actor_user_id,
            },
        )
    ).one()
    await _audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.lineage.recorded",
        subject_type="customer_profile",
        subject_id=profile_id,
        payload={
            "field_name": payload.field_name,
            "classification": payload.classification,
            "selected": payload.selected,
        },
    )
    values = row._mapping
    return CustomerLineageResponse(
        id=values["id"],
        profile_id=values["profile_id"],
        field_name=values["field_name"],
        value_fingerprint=f"{values['value_fingerprint'][:12]}…",
        source_id=values["source_id"],
        source_record_id=values["source_record_id"],
        classification=values["classification"],
        selected=values["selected"],
        observed_at=values["observed_at"],
        recorded_by_user_id=values["recorded_by_user_id"],
    )


async def list_lineage(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
) -> list[CustomerLineageResponse]:
    rows = await database.execute(
        text(
            """
            SELECT id, profile_id, field_name, value_fingerprint, source_id,
                   source_record_id, classification, selected, observed_at,
                   recorded_by_user_id
            FROM customer_field_lineage
            WHERE company_id = :company_id AND profile_id = :profile_id
            ORDER BY field_name, selected DESC, observed_at DESC
            """
        ),
        {"company_id": company_id, "profile_id": profile_id},
    )
    return [
        CustomerLineageResponse(
            id=row.id,
            profile_id=row.profile_id,
            field_name=row.field_name,
            value_fingerprint=f"{row.value_fingerprint[:12]}…",
            source_id=row.source_id,
            source_record_id=row.source_record_id,
            classification=row.classification,
            selected=row.selected,
            observed_at=row.observed_at,
            recorded_by_user_id=row.recorded_by_user_id,
        )
        for row in rows
    ]

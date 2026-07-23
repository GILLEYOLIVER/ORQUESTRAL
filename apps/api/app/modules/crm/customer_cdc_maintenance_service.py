from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from app.core.config import get_settings
from app.core.resources import ApplicationResources, create_resources
from app.modules.crm.customer_cdc_schemas import CustomerCdcRetentionPurgeRequest
from app.modules.crm.customer_cdc_service import purge_expired_customer_cdc_events


@dataclass(frozen=True, slots=True)
class CustomerCdcMaintenanceResult:
    companies_discovered: int
    companies_processed: int
    companies_failed: int
    deleted_events: int


async def _discover_retention_companies(
    resources: ApplicationResources,
    *,
    company_limit: int,
) -> list[UUID]:
    async with resources.sessions() as database:
        rows = (
            await database.execute(
                text(
                    """
                    SELECT company_id
                    FROM orkestral_cdc_retention_companies(:company_limit)
                    """
                ),
                {"company_limit": company_limit},
            )
        ).all()
        await database.commit()
    return [row.company_id for row in rows]


async def maintain_customer_cdc_retention(
    *,
    company_limit: int = 100,
    max_delete_per_company: int = 1_000,
) -> CustomerCdcMaintenanceResult:
    settings = get_settings()
    resources = create_resources(settings, database_role="worker")
    processed = 0
    failed = 0
    deleted = 0
    try:
        company_ids = await _discover_retention_companies(
            resources,
            company_limit=company_limit,
        )
        for company_id in company_ids:
            try:
                async with resources.sessions() as database:
                    await database.execute(
                        text(
                            """
                            SELECT set_config(
                                'app.current_company_id',
                                :company_id,
                                true
                            )
                            """
                        ),
                        {"company_id": str(company_id)},
                    )
                    result = await purge_expired_customer_cdc_events(
                        database,
                        company_id=company_id,
                        actor_user_id=None,
                        payload=CustomerCdcRetentionPurgeRequest(
                            confirmation="PURGE_EXPIRED_CDC_EVENTS",
                            max_delete=max_delete_per_company,
                        ),
                        execution_source="scheduled",
                    )
                    await database.commit()
                    deleted += result.deleted_events
                    processed += 1
            except Exception:
                failed += 1
        return CustomerCdcMaintenanceResult(
            companies_discovered=len(company_ids),
            companies_processed=processed,
            companies_failed=failed,
            deleted_events=deleted,
        )
    finally:
        await resources.close()


async def _maintain_customer_cdc_retention() -> dict[str, int]:
    result = await maintain_customer_cdc_retention()
    return {
        "companies_discovered": result.companies_discovered,
        "companies_processed": result.companies_processed,
        "companies_failed": result.companies_failed,
        "deleted_events": result.deleted_events,
    }


def maintain_customer_cdc_retention_sync() -> dict[str, int]:
    return asyncio.run(_maintain_customer_cdc_retention())


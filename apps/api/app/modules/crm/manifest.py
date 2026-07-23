from __future__ import annotations

from app.modules.crm.customer_cdc_routes import router as customer_cdc_router
from app.modules.crm.customer_governance_routes import router as customer_governance_router
from app.modules.crm.customer_ingestion_routes import router as customer_ingestion_router
from app.modules.crm.customer_sync_routes import router as customer_sync_router
from app.modules.crm.customer_sync_scheduler_routes import (
    router as customer_sync_scheduler_router,
)
from app.modules.crm.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

crm_module = ModuleDefinition(
    code="crm",
    name="CRM e Vendas",
    version="0.7.0",
    permissions=(
        "crm.contacts.view",
        "crm.contacts.create",
        "crm.contacts.update",
        "crm.contacts.delete",
        "crm.pipeline.view",
        "crm.pipeline.manage",
        "crm.opportunities.create",
        "crm.opportunities.update",
        "crm.opportunities.delete",
        "crm.activities.manage",
    ),
    routers=(
        router,
        customer_governance_router,
        customer_ingestion_router,
        customer_cdc_router,
        customer_sync_router,
        customer_sync_scheduler_router,
    ),
    menus=(
        ModuleMenu(
            label="CRM e Vendas",
            path="/app/crm/contatos",
            required_permission="crm.contacts.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "crm.contact.created",
        "crm.contact.updated",
        "crm.contact.deleted",
        "crm.pipeline.created",
        "crm.pipeline.stage.updated",
        "crm.opportunity.created",
        "crm.opportunity.updated",
        "crm.opportunity.deleted",
        "crm.opportunity.activity.created",
        "customer.match_rule.published",
        "customer.merge.approved",
        "customer.merge.rejected",
        "customer.merge.reverted",
        "customer.lineage.recorded",
        "customer.quality_rule.published",
        "customer.ingestion.completed",
        "customer.ingestion.reprocessed",
        "customer.sync_connector.created",
        "customer.sync_connector.active",
        "customer.sync_connector.paused",
        "customer.sync.completed",
        "customer.sync.failed",
        "customer.sync_adapter.health_checked",
        "customer.sync_dispatch.queued",
        "customer.sync_dispatch.acknowledged",
        "customer.sync_dispatch.retry_scheduled",
        "customer.sync_dispatch.dead_letter",
        "customer.sync_dispatch.requeued",
    ),
    migrations=(
        "20260716_0004",
        "20260720_0024",
        "20260723_0091",
        "20260723_0092",
        "20260723_0093",
        "20260723_0094",
        "20260723_0095",
        "20260723_0096",
        "20260723_0097",
        "20260723_0098",
        "20260723_0099",
    ),
)

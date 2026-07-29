from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.analytics.semantic_models import AnalyticsMetricDefinition
from app.modules.analytics.semantic_schemas import MetricCreate, SemanticFilter
from app.modules.analytics.semantic_service import SemanticQueryError, compile_semantic_query


def metric(code: str, dataset: str, aggregation: str, field: str | None):
    return AnalyticsMetricDefinition(
        company_id=uuid4(),
        code=code,
        name=code,
        dataset=dataset,
        aggregation=aggregation,
        value_field=field,
        unit="number",
        filters=[],
        created_by_user_id=uuid4(),
    )


def test_compiler_uses_bind_parameters_and_tenant_filter() -> None:
    company_id = uuid4()
    query, params, columns = compile_semantic_query(
        dataset="commerce.orders",
        dimensions=["status"],
        metrics=[metric("receita", "commerce.orders", "sum", "total")],
        filters=[SemanticFilter(field="status", operator="eq", value="fulfilled")],
        company_id=company_id,
    )
    assert "company_id = :company_id" in query
    assert "status = :filter_0" in query
    assert params == {"company_id": company_id, "filter_0": "fulfilled"}
    assert columns == ["status", "receita"]


def test_compiler_rejects_unlisted_fields() -> None:
    with pytest.raises(SemanticQueryError):
        compile_semantic_query(
            dataset="commerce.orders",
            dimensions=["password_hash"],
            metrics=[metric("total", "commerce.orders", "sum", "total")],
            filters=[],
            company_id=uuid4(),
        )


def test_metric_requires_value_for_sum() -> None:
    with pytest.raises(ValidationError):
        MetricCreate(
            code="receita",
            name="Receita",
            dataset="commerce.orders",
            aggregation="sum",
            value_field=None,
        )

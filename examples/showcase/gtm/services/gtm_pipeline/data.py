"""GTM pipeline data access using Cube for aggregate reads and Postgres for detail reads."""
from __future__ import annotations

import json
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
import urllib.error
import urllib.request

import psycopg
from psycopg.rows import dict_row


DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://anip:anip@localhost:5434/anip_gtm",
)
DEFAULT_QUARTER = os.getenv("GTM_DEFAULT_QUARTER", "2017-Q2")
CUBE_API_URL = os.getenv(
    "CUBE_API_URL",
    "http://localhost:4000/cubejs-api/v1/load",
)
CUBE_API_SECRET = os.getenv("CUBE_API_SECRET", "")


def _connect():
    return psycopg.connect(DEFAULT_DATABASE_URL, row_factory=dict_row)


def _scope_clause(scope: str | None) -> tuple[str, tuple[Any, ...]]:
    if not scope or scope in {"all", "company"}:
        return "", ()
    return " and regional_office = %s", (scope,)


def _cube_load(query: dict[str, Any]) -> list[dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    if CUBE_API_SECRET:
        headers["Authorization"] = CUBE_API_SECRET
    request = urllib.request.Request(
        CUBE_API_URL,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cube request failed: {exc}") from exc
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("Cube response did not include a data array")
    return data


def _number(value: Any, default: float | int = 0) -> float | int:
    if value in {None, ""}:
        return default
    return float(value)


def _round_2(value: Any, default: float | int = 0) -> float:
    if value in {None, ""}:
        return float(default)
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def get_pipeline_summary(quarter: str, owner_scope: str | None = None) -> dict[str, Any]:
    filters = [
        {
            "member": "PipelineHealth.engageQuarter",
            "operator": "equals",
            "values": [quarter],
        }
    ]
    if owner_scope and owner_scope not in {"all", "company"}:
        filters.append(
            {
                "member": "PipelineHealth.regionalOffice",
                "operator": "equals",
                "values": [owner_scope],
            }
        )
    rows = _cube_load(
        {
            "measures": [
                "PipelineHealth.opportunityCount",
                "PipelineHealth.openOpportunityCount",
                "PipelineHealth.wonOpportunityCount",
                "PipelineHealth.lostOpportunityCount",
                "PipelineHealth.wonRevenue",
                "PipelineHealth.openPipelineValue",
                "PipelineHealth.averageOpenRiskScore",
                "PipelineHealth.averageOpenDays",
            ],
            "dimensions": ["PipelineHealth.dealStage"],
            "filters": filters,
            "order": {"PipelineHealth.dealStage": "asc"},
        }
    )

    normalized_rows = [
        {
            "deal_stage": row["PipelineHealth.dealStage"],
            "opportunity_count": int(_number(row.get("PipelineHealth.opportunityCount"), 0)),
            "open_opportunity_count": int(_number(row.get("PipelineHealth.openOpportunityCount"), 0)),
            "won_opportunity_count": int(_number(row.get("PipelineHealth.wonOpportunityCount"), 0)),
            "lost_opportunity_count": int(_number(row.get("PipelineHealth.lostOpportunityCount"), 0)),
            "won_revenue": _round_2(row.get("PipelineHealth.wonRevenue"), 0),
            "open_pipeline_value": _round_2(row.get("PipelineHealth.openPipelineValue"), 0),
            "average_open_risk_score": None
            if row.get("PipelineHealth.averageOpenRiskScore") in {None, ""}
            else _round_2(row["PipelineHealth.averageOpenRiskScore"], 0),
            "average_open_days": None
            if row.get("PipelineHealth.averageOpenDays") in {None, ""}
            else _round_2(row["PipelineHealth.averageOpenDays"], 0),
        }
        for row in rows
    ]

    totals = {
        "opportunity_count": sum(row["opportunity_count"] or 0 for row in normalized_rows),
        "open_pipeline_value": round(sum(float(row["open_pipeline_value"] or 0) for row in normalized_rows), 2),
        "won_revenue": round(sum(float(row["won_revenue"] or 0) for row in normalized_rows), 2),
    }
    return {
        "quarter": quarter,
        "owner_scope": owner_scope or "company",
        "by_stage": normalized_rows,
        "totals": totals,
    }


def get_stalled_opportunities(
    quarter: str,
    min_days_open: int = 30,
    owner_scope: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    scope_sql, params = _scope_clause(owner_scope)
    query = f"""
        select
            opportunity_id,
            account_name,
            sales_agent_name,
            regional_office,
            deal_stage,
            product_name,
            engage_date,
            days_since_engage,
            risk_score
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = %s
          and is_open = true
          and days_since_engage >= %s
          {scope_sql}
        order by risk_score desc nulls last, days_since_engage desc, opportunity_id
        limit %s
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, (quarter, min_days_open, *params, limit))
        return cur.fetchall()


def get_account_risk_summary(
    quarter: str,
    top_n: int = 10,
    owner_scope: str | None = None,
) -> list[dict[str, Any]]:
    scope_sql, params = _scope_clause(owner_scope)
    query = f"""
        select
            account_name,
            regional_office,
            count(*) as open_opportunity_count,
            round(sum(coalesce(close_value, sales_price)), 2) as open_pipeline_value,
            round(avg(risk_score), 2) as average_risk_score,
            max(days_since_engage) as max_days_open,
            string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) as sales_agents
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = %s
          and is_open = true
          {scope_sql}
          and account_name is not null
          and trim(account_name) <> ''
        group by account_name, regional_office
        order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
        limit %s
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, (quarter, *params, top_n))
        return cur.fetchall()

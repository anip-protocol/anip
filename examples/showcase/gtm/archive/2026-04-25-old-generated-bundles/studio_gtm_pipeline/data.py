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


def get_pipeline_forecast_summary(
    quarter: str,
    owner_scope: str | None = None,
    forecast_mode: str = "risk_adjusted",
    limit: int = 5,
) -> dict[str, Any]:
    filters = [
        {
            "member": "Opportunities.engageQuarter",
            "operator": "equals",
            "values": [quarter],
        },
        {
            "member": "Opportunities.isOpen",
            "operator": "equals",
            "values": ["true"],
        },
    ]
    if owner_scope and owner_scope not in {"all", "company"}:
        filters.append(
            {
                "member": "Opportunities.regionalOffice",
                "operator": "equals",
                "values": [owner_scope],
            }
        )
    by_stage_rows = _cube_load(
        {
            "measures": [
                "Opportunities.openOpportunityCount",
                "Opportunities.forecastBaseValue",
                "Opportunities.likelyForecastValue",
                "Opportunities.bestCaseForecastValue",
                "Opportunities.riskAdjustedForecastValue",
                "Opportunities.averageRiskScore",
            ],
            "dimensions": ["Opportunities.dealStage"],
            "filters": filters,
            "order": {"Opportunities.dealStage": "asc"},
        }
    )
    top_contributors = _cube_load(
        {
            "measures": [
                "Opportunities.openOpportunityCount",
                "Opportunities.forecastBaseValue",
                "Opportunities.likelyForecastValue",
                "Opportunities.bestCaseForecastValue",
                "Opportunities.riskAdjustedForecastValue",
                "Opportunities.averageRiskScore",
            ],
            "dimensions": ["Opportunities.accountName", "Opportunities.regionalOffice"],
            "filters": filters,
            "order": {f"Opportunities.{_forecast_measure_name(forecast_mode)}": "desc"},
            "limit": min(max(int(limit or 5), 1), 10),
        }
    )

    stage_rows = [_normalize_forecast_stage_row(row, forecast_mode) for row in by_stage_rows]
    contributor_rows = [_normalize_forecast_account_row(row, forecast_mode) for row in top_contributors]
    totals = {
        "open_opportunity_count": sum(row["open_opportunity_count"] for row in stage_rows),
        "open_pipeline_value": round(sum(float(row["open_pipeline_value"] or 0) for row in stage_rows), 2),
        "likely_revenue": round(sum(float(row["likely_revenue"] or 0) for row in stage_rows), 2),
        "best_case_revenue": round(sum(float(row["best_case_revenue"] or 0) for row in stage_rows), 2),
        "risk_adjusted_revenue": round(sum(float(row["risk_adjusted_revenue"] or 0) for row in stage_rows), 2),
    }
    totals["selected_forecast_value"] = totals[_forecast_total_key(forecast_mode)]
    return {
        "quarter": quarter,
        "owner_scope": owner_scope or "company",
        "forecast_mode": forecast_mode,
        "by_stage": stage_rows,
        "totals": totals,
        "top_contributors": contributor_rows,
    }


def get_stage_bottleneck_summary(
    quarter: str,
    owner_scope: str | None = None,
    slice_by: str = "regional_office",
    limit: int = 10,
) -> dict[str, Any]:
    filters = [
        {
            "member": "Opportunities.engageQuarter",
            "operator": "equals",
            "values": [quarter],
        },
        {
            "member": "Opportunities.isOpen",
            "operator": "equals",
            "values": ["true"],
        },
    ]
    if owner_scope and owner_scope not in {"all", "company"}:
        filters.append(
            {
                "member": "Opportunities.regionalOffice",
                "operator": "equals",
                "values": [owner_scope],
            }
        )
    slice_dimension = _bottleneck_dimension_name(slice_by)
    rows = _cube_load(
        {
            "measures": [
                "Opportunities.openOpportunityCount",
                "Opportunities.openPipelineValue",
                "Opportunities.averageDaysSinceEngage",
                "Opportunities.averageRiskScore",
            ],
            "dimensions": ["Opportunities.dealStage", f"Opportunities.{slice_dimension}"],
            "filters": filters,
        }
    )
    normalized_rows = [_normalize_bottleneck_row(row, slice_by) for row in rows]
    normalized_rows = [row for row in normalized_rows if row["open_opportunity_count"] > 0]
    normalized_rows.sort(
        key=lambda row: (
            -float(row["average_open_days"] or 0),
            -float(row["average_risk_score"] or 0),
            -int(row["open_opportunity_count"] or 0),
            row["slice_value"],
            row["deal_stage"],
        )
    )
    for index, row in enumerate(normalized_rows, start=1):
        row["bottleneck_rank"] = index
    return {
        "quarter": quarter,
        "owner_scope": owner_scope or "company",
        "slice_by": slice_by,
        "bottlenecks": normalized_rows[: min(max(int(limit or 10), 1), 15)],
    }


def get_sales_team_performance_summary(
    quarter: str,
    owner_scope: str | None = None,
    slice_by: str = "manager_name",
    limit: int = 10,
) -> dict[str, Any]:
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
    slice_dimension = _team_dimension_name(slice_by)
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
            "dimensions": [f"PipelineHealth.{slice_dimension}"],
            "filters": filters,
        }
    )
    normalized_rows = [_normalize_team_performance_row(row, slice_by) for row in rows]
    normalized_rows.sort(
        key=lambda row: (
            -float(row["open_pipeline_value"] or 0),
            -int(row["won_opportunity_count"] or 0),
            -float(row["average_open_risk_score"] or 0),
            row["slice_value"],
        )
    )
    return {
        "quarter": quarter,
        "owner_scope": owner_scope or "company",
        "slice_by": slice_by,
        "performance_rows": normalized_rows[: min(max(int(limit or 10), 1), 15)],
    }


def get_product_pipeline_summary(
    quarter: str,
    owner_scope: str | None = None,
    product_scope: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    filters = [
        {
            "member": "Opportunities.engageQuarter",
            "operator": "equals",
            "values": [quarter],
        }
    ]
    if owner_scope and owner_scope not in {"all", "company"}:
        filters.append(
            {
                "member": "Opportunities.regionalOffice",
                "operator": "equals",
                "values": [owner_scope],
            }
        )
    if product_scope:
        filters.append(
            {
                "member": "Opportunities.productName",
                "operator": "equals",
                "values": [product_scope],
            }
        )
    rows = _cube_load(
        {
            "measures": [
                "Opportunities.openOpportunityCount",
                "Opportunities.wonOpportunityCount",
                "Opportunities.lostOpportunityCount",
                "Opportunities.openPipelineValue",
                "Opportunities.wonRevenue",
                "Opportunities.averageRiskScore",
            ],
            "dimensions": ["Opportunities.productName"],
            "filters": filters,
        }
    )
    normalized_rows = [_normalize_product_pipeline_row(row) for row in rows]
    normalized_rows.sort(
        key=lambda row: (
            -float(row["open_pipeline_value"] or 0),
            -float(row["won_revenue"] or 0),
            -int(row["open_opportunity_count"] or 0),
            row["product_name"],
        )
    )
    return {
        "quarter": quarter,
        "owner_scope": owner_scope or "company",
        "product_scope": product_scope,
        "products": normalized_rows[: min(max(int(limit or 10), 1), 15)],
    }


def get_reassignment_plan_preview(
    quarter: str,
    owner_scope: str | None = None,
    selection_basis: str = "manager_capacity",
    limit: int = 5,
) -> dict[str, Any]:
    scope_sql, params = _scope_clause(owner_scope)
    manager_load_query = f"""
        select
            manager_name,
            regional_office,
            count(*)::int as open_opportunity_count,
            round(avg(risk_score), 2) as average_risk_score
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = %s
          and is_open = true
          {scope_sql}
        group by manager_name, regional_office
    """
    opportunity_query = f"""
        select
            opportunity_id,
            account_name,
            sales_agent_name,
            manager_name,
            regional_office,
            deal_stage,
            product_name,
            days_since_engage,
            round(risk_score, 2) as risk_score
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = %s
          and is_open = true
          {scope_sql}
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(manager_load_query, (quarter, *params))
        manager_rows = cur.fetchall()
        cur.execute(opportunity_query, (quarter, *params))
        opportunity_rows = cur.fetchall()

    manager_loads: dict[tuple[str, str], dict[str, Any]] = {}
    targets_by_region: dict[str, list[dict[str, Any]]] = {}
    for row in manager_rows:
        manager_name = str(row["manager_name"] or "__none__")
        regional_office = str(row["regional_office"] or "__none__")
        normalized = {
            "manager_name": manager_name,
            "regional_office": regional_office,
            "open_opportunity_count": int(row["open_opportunity_count"] or 0),
            "average_risk_score": _round_2(row["average_risk_score"], 0),
        }
        manager_loads[(regional_office, manager_name)] = normalized
        targets_by_region.setdefault(regional_office, []).append(normalized)

    for regional_office, items in targets_by_region.items():
        items.sort(
            key=lambda row: (
                int(row["open_opportunity_count"] or 0),
                float(row["average_risk_score"] or 0),
                row["manager_name"],
            )
        )

    def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        regional_office = str(row["regional_office"] or "__none__")
        manager_name = str(row["manager_name"] or "__none__")
        manager_load = manager_loads.get((regional_office, manager_name), {})
        if selection_basis == "stalled_risk_mix":
            return (
                -float(row["risk_score"] or 0),
                -int(row["days_since_engage"] or 0),
                -int(manager_load.get("open_opportunity_count") or 0),
                row["opportunity_id"],
            )
        return (
            -int(manager_load.get("open_opportunity_count") or 0),
            -int(row["days_since_engage"] or 0),
            -float(row["risk_score"] or 0),
            row["opportunity_id"],
        )

    normalized_opportunities = sorted(opportunity_rows, key=_candidate_sort_key)
    suggestions: list[dict[str, Any]] = []
    for row in normalized_opportunities:
        regional_office = str(row["regional_office"] or "__none__")
        source_manager = str(row["manager_name"] or "__none__")
        source_load = manager_loads.get((regional_office, source_manager), {})
        target_candidates = [
            item
            for item in targets_by_region.get(regional_office, [])
            if item["manager_name"] != source_manager
        ]
        if not target_candidates:
            continue
        target = target_candidates[0]
        reason = (
            f"{source_manager} is carrying {source_load.get('open_opportunity_count', 0)} open opportunities"
            f" in {regional_office}; this opportunity has been open {row['days_since_engage']} days"
            f" with risk score {row['risk_score']}."
        )
        suggestions.append(
            {
                "opportunity_id": row["opportunity_id"],
                "account_name": row["account_name"] or "__none__",
                "sales_agent_name": row["sales_agent_name"] or "__none__",
                "deal_stage": row["deal_stage"] or "__none__",
                "product_name": row["product_name"] or "__none__",
                "source_manager": source_manager,
                "source_region": regional_office,
                "source_open_load": int(source_load.get("open_opportunity_count") or 0),
                "target_manager": target["manager_name"],
                "target_region": target["regional_office"],
                "target_open_load": int(target.get("open_opportunity_count") or 0),
                "days_since_engage": int(row["days_since_engage"] or 0),
                "risk_score": _round_2(row["risk_score"], 0),
                "reason": reason,
                "expected_impact": (
                    f"Reduce {source_manager}'s open load by one and move a high-attention opportunity"
                    f" to {target['manager_name']} within {regional_office}."
                ),
            }
        )
        if len(suggestions) >= min(max(int(limit or 5), 1), 10):
            break

    return {
        "quarter": quarter,
        "owner_scope": owner_scope or "company",
        "selection_basis": selection_basis,
        "requires_approval": True,
        "reassignments": suggestions,
        "summary": {
            "proposed_reassignment_count": len(suggestions),
            "source_managers": sorted({item["source_manager"] for item in suggestions}),
            "target_managers": sorted({item["target_manager"] for item in suggestions}),
        },
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
            round(sum(close_value), 2) as open_pipeline_value,
            round(avg(risk_score), 2) as average_risk_score,
            max(days_since_engage) as max_days_open,
            string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) as sales_agents
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = %s
          and is_open = true
          {scope_sql}
        group by account_name, regional_office
        order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
        limit %s
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, (quarter, *params, top_n))
        return cur.fetchall()


def _forecast_measure_name(forecast_mode: str) -> str:
    if forecast_mode == "best_case":
        return "bestCaseForecastValue"
    if forecast_mode == "likely":
        return "likelyForecastValue"
    return "riskAdjustedForecastValue"


def _forecast_total_key(forecast_mode: str) -> str:
    if forecast_mode == "best_case":
        return "best_case_revenue"
    if forecast_mode == "likely":
        return "likely_revenue"
    return "risk_adjusted_revenue"


def _normalize_forecast_stage_row(row: dict[str, Any], forecast_mode: str) -> dict[str, Any]:
    normalized = {
        "deal_stage": row["Opportunities.dealStage"],
        "open_opportunity_count": int(_number(row.get("Opportunities.openOpportunityCount"), 0)),
        "open_pipeline_value": _round_2(row.get("Opportunities.forecastBaseValue"), 0),
        "likely_revenue": _round_2(row.get("Opportunities.likelyForecastValue"), 0),
        "best_case_revenue": _round_2(row.get("Opportunities.bestCaseForecastValue"), 0),
        "risk_adjusted_revenue": _round_2(row.get("Opportunities.riskAdjustedForecastValue"), 0),
        "average_risk_score": None
        if row.get("Opportunities.averageRiskScore") in {None, ""}
        else _round_2(row["Opportunities.averageRiskScore"], 0),
    }
    normalized["selected_forecast_value"] = normalized[_forecast_total_key(forecast_mode)]
    return normalized


def _normalize_forecast_account_row(row: dict[str, Any], forecast_mode: str) -> dict[str, Any]:
    normalized = {
        "account_name": row["Opportunities.accountName"],
        "regional_office": row["Opportunities.regionalOffice"],
        "open_opportunity_count": int(_number(row.get("Opportunities.openOpportunityCount"), 0)),
        "open_pipeline_value": _round_2(row.get("Opportunities.forecastBaseValue"), 0),
        "likely_revenue": _round_2(row.get("Opportunities.likelyForecastValue"), 0),
        "best_case_revenue": _round_2(row.get("Opportunities.bestCaseForecastValue"), 0),
        "risk_adjusted_revenue": _round_2(row.get("Opportunities.riskAdjustedForecastValue"), 0),
        "average_risk_score": None
        if row.get("Opportunities.averageRiskScore") in {None, ""}
        else _round_2(row["Opportunities.averageRiskScore"], 0),
    }
    normalized["selected_forecast_value"] = normalized[_forecast_total_key(forecast_mode)]
    return normalized


def _bottleneck_dimension_name(slice_by: str) -> str:
    if slice_by == "manager_name":
        return "managerName"
    if slice_by == "product_name":
        return "productName"
    return "regionalOffice"


def _normalize_bottleneck_row(row: dict[str, Any], slice_by: str) -> dict[str, Any]:
    dimension_name = _bottleneck_dimension_name(slice_by)
    return {
        "slice_by": slice_by,
        "slice_value": row.get(f"Opportunities.{dimension_name}") or "__none__",
        "deal_stage": row["Opportunities.dealStage"],
        "open_opportunity_count": int(_number(row.get("Opportunities.openOpportunityCount"), 0)),
        "open_pipeline_value": _round_2(row.get("Opportunities.openPipelineValue"), 0),
        "average_open_days": None
        if row.get("Opportunities.averageDaysSinceEngage") in {None, ""}
        else _round_2(row["Opportunities.averageDaysSinceEngage"], 0),
        "average_risk_score": None
        if row.get("Opportunities.averageRiskScore") in {None, ""}
        else _round_2(row["Opportunities.averageRiskScore"], 0),
    }


def _team_dimension_name(slice_by: str) -> str:
    if slice_by == "regional_office":
        return "regionalOffice"
    return "managerName"


def _normalize_team_performance_row(row: dict[str, Any], slice_by: str) -> dict[str, Any]:
    dimension_name = _team_dimension_name(slice_by)
    return {
        "slice_by": slice_by,
        "slice_value": row.get(f"PipelineHealth.{dimension_name}") or "__none__",
        "opportunity_count": int(_number(row.get("PipelineHealth.opportunityCount"), 0)),
        "open_opportunity_count": int(_number(row.get("PipelineHealth.openOpportunityCount"), 0)),
        "won_opportunity_count": int(_number(row.get("PipelineHealth.wonOpportunityCount"), 0)),
        "lost_opportunity_count": int(_number(row.get("PipelineHealth.lostOpportunityCount"), 0)),
        "open_pipeline_value": _round_2(row.get("PipelineHealth.openPipelineValue"), 0),
        "won_revenue": _round_2(row.get("PipelineHealth.wonRevenue"), 0),
        "average_open_risk_score": None
        if row.get("PipelineHealth.averageOpenRiskScore") in {None, ""}
        else _round_2(row["PipelineHealth.averageOpenRiskScore"], 0),
        "average_open_days": None
        if row.get("PipelineHealth.averageOpenDays") in {None, ""}
        else _round_2(row["PipelineHealth.averageOpenDays"], 0),
    }


def _normalize_product_pipeline_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_name": row.get("Opportunities.productName") or "__none__",
        "open_opportunity_count": int(_number(row.get("Opportunities.openOpportunityCount"), 0)),
        "won_opportunity_count": int(_number(row.get("Opportunities.wonOpportunityCount"), 0)),
        "lost_opportunity_count": int(_number(row.get("Opportunities.lostOpportunityCount"), 0)),
        "open_pipeline_value": _round_2(row.get("Opportunities.openPipelineValue"), 0),
        "won_revenue": _round_2(row.get("Opportunities.wonRevenue"), 0),
        "average_open_risk_score": None
        if row.get("Opportunities.averageRiskScore") in {None, ""}
        else _round_2(row["Opportunities.averageRiskScore"], 0),
    }

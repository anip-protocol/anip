"""Postgres-backed data access for the GTM enrichment service."""
from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row


DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://anip:anip@localhost:5434/anip_gtm",
)


def _connect():
    return psycopg.connect(DEFAULT_DATABASE_URL, row_factory=dict_row)


def _parse_account_names(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _scope_clause(scope: str | None) -> tuple[str, tuple[Any, ...]]:
    if not scope or scope in {"all", "company"}:
        return "", ()
    return " and regional_office = %s", (scope,)


def get_account_enrichment_summary(
    account_names: str | list[str] | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    names = _parse_account_names(account_names)
    if not names:
        return []
    query = """
        select
            account_name,
            sector,
            office_location,
            parent_company,
            revenue_band,
            employee_band,
            icp_fit,
            intent_signal,
            likely_buying_motion,
            enrichment_rationale
        from analytics_gtm.mart_gtm__account_enrichment
        where account_name = any(%s)
        order by account_name
        limit %s
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, (names, min(limit, 10)))
        return cur.fetchall()


def get_lookalike_accounts(
    reference_account: str,
    limit: int = 5,
) -> dict[str, Any] | None:
    reference_query = """
        select
            account_name,
            sector,
            office_location,
            revenue_band,
            employee_band,
            lookalike_key,
            icp_fit,
            intent_signal
        from analytics_gtm.mart_gtm__account_enrichment
        where account_name = %s
    """
    matches_query = """
        select
            account_name,
            sector,
            office_location,
            revenue_band,
            employee_band,
            icp_fit,
            intent_signal,
            likely_buying_motion,
            enrichment_rationale
        from analytics_gtm.mart_gtm__account_enrichment
        where lookalike_key = %s
          and account_name <> %s
        order by revenue_band desc, account_name
        limit %s
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(reference_query, (reference_account,))
        reference = cur.fetchone()
        if reference is None:
            return None
        cur.execute(matches_query, (reference["lookalike_key"], reference_account, min(limit, 10)))
        matches = cur.fetchall()
    return {
        "reference_account": reference_account,
        "reference_profile": reference,
        "matches": matches,
    }


def get_at_risk_account_enrichment_summary(
    *,
    quarter: str,
    ranking_basis: str = "risk_score",
    owner_scope: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    scope_sql, params = _scope_clause(owner_scope)
    risk_query = f"""
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
        cur.execute(risk_query, (quarter, *params, min(limit, 10)))
        risk_accounts = cur.fetchall()

    account_names = [row["account_name"] for row in risk_accounts]
    enrichment_rows = get_account_enrichment_summary(account_names, limit=len(account_names))
    enrichment_by_name = {row["account_name"]: row for row in enrichment_rows}
    accounts = [
        {
            **dict(enrichment_by_name.get(row["account_name"], {})),
            "account_name": row["account_name"],
            "risk_context": dict(row),
        }
        for row in risk_accounts
    ]
    return {
        "quarter": quarter,
        "owner_scope": owner_scope or "company",
        "ranking_basis": ranking_basis,
        "accounts": accounts,
        "source_selection": {
            "capability": "gtm.account_risk_summary",
            "account_count": len(risk_accounts),
            "no_results": len(risk_accounts) == 0,
        },
    }

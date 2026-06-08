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

#!/usr/bin/env python3
"""Initialize Metabase for the GTM showcase and create curated verification assets."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


METABASE_URL = os.getenv("GTM_METABASE_URL", "http://127.0.0.1:3035").rstrip("/")
METABASE_ADMIN_EMAIL = os.getenv("GTM_METABASE_ADMIN_EMAIL", "admin@anip.local")
METABASE_ADMIN_PASSWORD = os.getenv("GTM_METABASE_ADMIN_PASSWORD", "Anip-Demo-Admin-2026!")
METABASE_FIRST_NAME = os.getenv("GTM_METABASE_ADMIN_FIRST_NAME", "ANIP")
METABASE_LAST_NAME = os.getenv("GTM_METABASE_ADMIN_LAST_NAME", "Admin")
METABASE_SITE_NAME = os.getenv("GTM_METABASE_SITE_NAME", "ANIP GTM Showcase")

POSTGRES_HOST = os.getenv("GTM_METABASE_DB_HOST", "gtm-postgres")
POSTGRES_PORT = int(os.getenv("GTM_METABASE_DB_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "anip_gtm")
POSTGRES_USER = os.getenv("POSTGRES_USER", "anip")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "anip")
POSTGRES_SCHEMA = os.getenv("GTM_METABASE_DB_SCHEMA", "analytics_gtm")
DATABASE_NAME = os.getenv("GTM_METABASE_DATABASE_NAME", "GTM Warehouse")
COLLECTION_NAME = os.getenv("GTM_METABASE_COLLECTION_NAME", "ANIP GTM Showcase")
DASHBOARD_NAME = os.getenv("GTM_METABASE_DASHBOARD_NAME", "ANIP GTM Verification Surface")


def _request(
    method: str,
    path: str,
    *,
    session_token: str | None = None,
    body: dict[str, Any] | list[Any] | None = None,
    expected: tuple[int, ...] = (200,),
) -> Any:
    headers = {"Content-Type": "application/json"}
    if session_token:
        headers["X-Metabase-Session"] = session_token
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{METABASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
            if response.status not in expected:
                raise RuntimeError(f"{method} {path} returned {response.status}: {payload}")
            if not payload:
                return None
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {payload}") from exc


def _wait_for_metabase() -> None:
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            payload = _request("GET", "/api/health")
            if payload.get("status") == "ok":
                return
        except Exception:
            time.sleep(2)
            continue
        time.sleep(2)
    raise RuntimeError("Metabase did not become healthy within 120 seconds")


def _session_properties() -> dict[str, Any]:
    return _request("GET", "/api/session/properties")


def _setup_if_needed() -> None:
    properties = _session_properties()
    setup_token = properties.get("setup-token")
    if not setup_token:
        return
    payload = {
        "token": setup_token,
        "user": {
            "email": METABASE_ADMIN_EMAIL,
            "password": METABASE_ADMIN_PASSWORD,
            "first_name": METABASE_FIRST_NAME,
            "last_name": METABASE_LAST_NAME,
            "site_name": METABASE_SITE_NAME,
        },
        "prefs": {
            "site_name": METABASE_SITE_NAME,
            "allow_tracking": False,
        },
        "database": {
            "engine": "postgres",
            "name": DATABASE_NAME,
            "details": {
                "host": POSTGRES_HOST,
                "port": POSTGRES_PORT,
                "dbname": POSTGRES_DB,
                "user": POSTGRES_USER,
                "password": POSTGRES_PASSWORD,
                "ssl": False,
                "schema-filters-type": "inclusion",
                "schema-filters-patterns": POSTGRES_SCHEMA,
            },
            "auto_run_queries": True,
        },
    }
    try:
        _request("POST", "/api/setup", body=payload, expected=(200,))
    except RuntimeError as exc:
        if "a user currently exists" in str(exc):
            return
        raise


def _login() -> str:
    payload = _request(
        "POST",
        "/api/session",
        body={"username": METABASE_ADMIN_EMAIL, "password": METABASE_ADMIN_PASSWORD},
    )
    token = str(payload.get("id") or "").strip()
    if not token:
        raise RuntimeError("Metabase login did not return a session id")
    return token


def _ensure_database(session_token: str) -> int:
    databases = _request("GET", "/api/database", session_token=session_token)
    for item in databases.get("data", []):
        if item.get("name") == DATABASE_NAME:
            return int(item["id"])
    payload = {
        "engine": "postgres",
        "name": DATABASE_NAME,
        "details": {
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "dbname": POSTGRES_DB,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD,
            "ssl": False,
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": POSTGRES_SCHEMA,
        },
        "auto_run_queries": True,
    }
    created = _request("POST", "/api/database", session_token=session_token, body=payload)
    return int(created["id"])


def _sync_database(session_token: str, database_id: int) -> None:
    _request("POST", f"/api/database/{database_id}/sync_schema", session_token=session_token, body={})


def _list_collections(session_token: str) -> list[dict[str, Any]]:
    payload = _request("GET", "/api/collection", session_token=session_token)
    return list(payload)


def _ensure_collection(session_token: str) -> int:
    for collection in _list_collections(session_token):
        if collection.get("name") == COLLECTION_NAME:
            return int(collection["id"])
    created = _request(
        "POST",
        "/api/collection",
        session_token=session_token,
        body={
            "name": COLLECTION_NAME,
            "description": "Curated saved questions and dashboards for GTM showcase verification.",
            "color": "#509EE3",
        },
    )
    return int(created["id"])


def _collection_items(session_token: str, collection_id: int) -> list[dict[str, Any]]:
    payload = _request("GET", f"/api/collection/{collection_id}/items", session_token=session_token)
    data = payload.get("data")
    if isinstance(data, list):
        return data
    return list(payload)


def _ensure_card(
    session_token: str,
    *,
    collection_id: int,
    database_id: int,
    name: str,
    description: str,
    query: str,
    display: str = "table",
) -> int:
    existing = None
    for item in _collection_items(session_token, collection_id):
        model = item.get("model") or item.get("model_name")
        if model == "card" and item.get("name") == name:
            existing = item
            break
    payload = {
        "name": name,
        "description": description,
        "display": display,
        "visualization_settings": {},
        "collection_id": collection_id,
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {
                "query": query,
                "template-tags": {},
            },
        },
    }
    if existing:
        updated = _request(
            "PUT",
            f"/api/card/{existing['id']}",
            session_token=session_token,
            body=payload,
        )
        return int(updated["id"])
    created = _request("POST", "/api/card", session_token=session_token, body=payload)
    return int(created["id"])


def _list_dashboards(session_token: str) -> list[dict[str, Any]]:
    payload = _request("GET", "/api/dashboard", session_token=session_token)
    return list(payload)


def _ensure_dashboard(session_token: str, collection_id: int) -> int:
    for dashboard in _list_dashboards(session_token):
        if dashboard.get("name") == DASHBOARD_NAME:
            if dashboard.get("collection_id") != collection_id:
                _request(
                    "PUT",
                    f"/api/dashboard/{dashboard['id']}",
                    session_token=session_token,
                    body={
                        "name": DASHBOARD_NAME,
                        "description": "Read-oriented verification dashboard aligned to GTM ANIP showcase slices.",
                        "collection_id": collection_id,
                    },
                )
            return int(dashboard["id"])
    created = _request(
        "POST",
        "/api/dashboard",
        session_token=session_token,
        body={
            "name": DASHBOARD_NAME,
            "description": "Read-oriented verification dashboard aligned to GTM ANIP showcase slices.",
            "collection_id": collection_id,
        },
    )
    return int(created["id"])


def _sync_dashboard_cards(session_token: str, dashboard_id: int, cards: list[dict[str, Any]]) -> None:
    payload = {
        "cards": [
            {
                "id": -(index + 1),
                "card_id": item["card_id"],
                "row": item["row"],
                "col": item["col"],
                "size_x": item.get("size_x", 12),
                "size_y": item.get("size_y", 6),
                "parameter_mappings": [],
            }
            for index, item in enumerate(cards)
        ]
    }
    _request(
        "PUT",
        f"/api/dashboard/{dashboard_id}/cards",
        session_token=session_token,
        body=payload,
        expected=(200,),
    )


def _question_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "Q2 Pipeline Summary By Stage",
            "description": "Validate bounded pipeline summary results by quarter, stage, and region.",
            "query": """
select
    engage_quarter,
    regional_office,
    deal_stage,
    open_opportunity_count,
    open_pipeline_value,
    won_revenue,
    average_open_risk_score,
    average_open_days
from analytics_gtm.bi_gtm__pipeline_stage_summary
where engage_quarter = '2017-Q2'
order by regional_office, deal_stage
""".strip(),
            "row": 0,
            "col": 0,
        },
        {
            "name": "Q2 Risk-Adjusted Forecast By Stage",
            "description": "Validate forecast summary outputs across likely, best-case, and risk-adjusted measures.",
            "query": """
select
    engage_quarter,
    regional_office,
    deal_stage,
    open_opportunity_count,
    open_pipeline_value,
    likely_revenue,
    best_case_revenue,
    risk_adjusted_revenue,
    average_open_risk_score
from analytics_gtm.bi_gtm__forecast_stage_summary
where engage_quarter = '2017-Q2'
order by regional_office, deal_stage
""".strip(),
            "row": 0,
            "col": 12,
        },
        {
            "name": "Q2 East Stage Bottlenecks",
            "description": "Validate stage bottleneck questions for East-region pipeline slices.",
            "query": """
select
    regional_office,
    manager_name,
    product_name,
    deal_stage,
    open_opportunity_count,
    open_pipeline_value,
    average_open_days,
    average_open_risk_score
from analytics_gtm.bi_gtm__stage_bottlenecks
where engage_quarter = '2017-Q2'
  and regional_office = 'East'
order by average_open_days desc, average_open_risk_score desc, open_opportunity_count desc
limit 15
""".strip(),
            "row": 6,
            "col": 0,
        },
        {
            "name": "Q2 East At-Risk Accounts",
            "description": "Validate at-risk account ranking and regional risk slices.",
            "query": """
select
    account_name,
    regional_office,
    open_opportunity_count,
    open_pipeline_value,
    average_risk_score,
    max_days_open,
    sales_agents
from analytics_gtm.bi_gtm__risk_accounts
where engage_quarter = '2017-Q2'
  and regional_office = 'East'
order by average_risk_score desc, open_pipeline_value desc, account_name
limit 10
""".strip(),
            "row": 6,
            "col": 12,
        },
        {
            "name": "Q2 Sales Team Performance",
            "description": "Validate sales-team performance summaries by manager and region.",
            "query": """
select
    manager_name,
    regional_office,
    opportunity_count,
    open_opportunity_count,
    won_opportunity_count,
    lost_opportunity_count,
    open_pipeline_value,
    won_revenue,
    average_open_risk_score,
    average_open_days
from analytics_gtm.bi_gtm__sales_team_performance
where engage_quarter = '2017-Q2'
order by open_pipeline_value desc, won_opportunity_count desc, average_open_risk_score desc
limit 12
""".strip(),
            "row": 12,
            "col": 0,
        },
        {
            "name": "Q2 Product Pipeline Summary",
            "description": "Validate product-level pipeline and revenue slices.",
            "query": """
select
    product_name,
    regional_office,
    open_opportunity_count,
    won_opportunity_count,
    lost_opportunity_count,
    open_pipeline_value,
    won_revenue,
    average_open_risk_score
from analytics_gtm.bi_gtm__product_pipeline
where engage_quarter = '2017-Q2'
order by open_pipeline_value desc, won_revenue desc, open_opportunity_count desc
limit 12
""".strip(),
            "row": 12,
            "col": 12,
        },
        {
            "name": "Account Enrichment Verification",
            "description": "Validate the bounded enrichment context returned for named accounts.",
            "query": """
select
    account_name,
    sector,
    office_location,
    parent_company,
    revenue_band,
    employee_band,
    icp_fit,
    intent_signal,
    likely_buying_motion
from analytics_gtm.bi_gtm__account_enrichment
where account_name in ('Acme Corporation', 'Codehow', 'Condax')
order by account_name
""".strip(),
            "row": 18,
            "col": 0,
        },
    ]


def main() -> int:
    _wait_for_metabase()
    _setup_if_needed()
    session_token = _login()
    database_id = _ensure_database(session_token)
    _sync_database(session_token, database_id)
    collection_id = _ensure_collection(session_token)
    dashboard_id = _ensure_dashboard(session_token, collection_id)

    cards: list[tuple[str, int]] = []
    dashboard_cards: list[dict[str, Any]] = []
    for item in _question_definitions():
        card_id = _ensure_card(
            session_token,
            collection_id=collection_id,
            database_id=database_id,
            name=item["name"],
            description=item["description"],
            query=item["query"],
        )
        cards.append((item["name"], card_id))
        dashboard_cards.append(
            {
                "card_id": card_id,
                "row": item["row"],
                "col": item["col"],
            }
        )

    _sync_dashboard_cards(session_token, dashboard_id, dashboard_cards)

    print(
        json.dumps(
            {
                "metabase_url": METABASE_URL,
                "database_name": DATABASE_NAME,
                "collection_name": COLLECTION_NAME,
                "dashboard_name": DASHBOARD_NAME,
                "cards": [{"name": name, "id": card_id} for name, card_id in cards],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

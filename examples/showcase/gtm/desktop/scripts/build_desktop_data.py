#!/usr/bin/env python3
"""Build the precomputed GTM mart database bundled by GTM Agent Desktop.

The Docker showcase keeps Postgres + dbt + Metabase as the full verification
stack. The desktop app needs the same read-side mart semantics without asking a
user to install Docker, Postgres, or dbt. This script materializes the dbt mart
shape from the checked-in Maven CRM CSVs into a small SQLite artifact.
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "maven"
OUT_PATH = ROOT / "desktop" / "data" / "gtm_desktop.sqlite"


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _read_csv(name: str) -> list[dict[str, str]]:
    with (RAW_DIR / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    return date.fromisoformat(value)


def _quarter(value: date | None) -> str | None:
    if value is None:
        return None
    return f"{value.year}-Q{((value.month - 1) // 3) + 1}"


def _float(value: str | float | int | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _int(value: str | int | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _round2(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def _revenue_band(revenue: float | None) -> str:
    revenue = revenue or 0
    if revenue >= 3000:
        return "enterprise"
    if revenue >= 1000:
        return "mid_market"
    return "commercial"


def _employee_band(employees: int | None) -> str:
    employees = employees or 0
    if employees >= 5000:
        return "5000_plus"
    if employees >= 2000:
        return "2000_to_4999"
    if employees >= 500:
        return "500_to_1999"
    return "under_500"


def _icp_fit(sector: str, revenue: float | None) -> str:
    if sector in {"software", "marketing", "technology"} and (revenue or 0) >= 1000:
        return "strong_fit"
    if sector in {"software", "technology", "medical"}:
        return "qualified_fit"
    return "conditional_fit"


def _intent_signal(sector: str, office_location: str) -> str:
    if office_location == "United States" and sector in {"software", "technology", "marketing"}:
        return "high"
    if office_location == "United States":
        return "medium"
    return "observed"


def _buying_motion(sector: str) -> str:
    if sector in {"software", "technology"}:
        return "cloud_modernization"
    if sector == "medical":
        return "regulated_growth"
    if sector == "retail":
        return "commerce_efficiency"
    return "general_expansion"


def _avg(values: Iterable[float | int | None]) -> float | None:
    items = [float(value) for value in values if value is not None]
    if not items:
        return None
    return round(sum(items) / len(items), 2)


def _sum(values: Iterable[float | int | None]) -> float:
    return round(sum(float(value or 0) for value in values), 2)


def _create_table(conn: sqlite3.Connection, name: str, columns: dict[str, str]) -> None:
    column_sql = ", ".join(f"{column} {kind}" for column, kind in columns.items())
    conn.execute(f"drop table if exists {name}")
    conn.execute(f"create table {name} ({column_sql})")


def _column_types(rows: list[dict[str, Any]]) -> dict[str, str]:
    types: dict[str, str] = {}
    for column in rows[0]:
        values = [row.get(column) for row in rows if row.get(column) is not None]
        if values and all(isinstance(value, bool) for value in values):
            types[column] = "integer"
        elif values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            types[column] = "integer"
        elif values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            types[column] = "real"
        else:
            types[column] = "text"
    return types


def _insert_rows(conn: sqlite3.Connection, name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(
        f"insert into {name} ({', '.join(columns)}) values ({placeholders})",
        [[row.get(column) for column in columns] for row in rows],
    )


def _group(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key) for key in keys)].append(row)
    return grouped


def build_database(output_path: Path = OUT_PATH) -> Path:
    accounts_raw = _read_csv("accounts.csv")
    products_raw = _read_csv("products.csv")
    sales_agents_raw = _read_csv("sales_teams.csv")
    opportunities_raw = _read_csv("sales_pipeline.csv")

    accounts = []
    for row in accounts_raw:
        account_name = row["account"].strip()
        sector = row["sector"].strip().lower()
        if sector == "technolgy":
            sector = "technology"
        office_location = row["office_location"].strip()
        if office_location == "Philipines":
            office_location = "Philippines"
        accounts.append(
            {
                "account_key": _md5(account_name),
                "account_name": account_name,
                "sector": sector,
                "year_established": _int(row["year_established"]),
                "revenue_usd_millions": _float(row["revenue"]),
                "employees": _int(row["employees"]),
                "office_location": office_location,
                "subsidiary_of": row["subsidiary_of"].strip() or None,
            }
        )
    accounts_by_name = {row["account_name"]: row for row in accounts}

    products = []
    for row in products_raw:
        product_name = row["product"].strip()
        products.append(
            {
                "product_key": _md5(product_name),
                "product_name": product_name,
                "product_series": row["series"].strip(),
                "sales_price": _float(row["sales_price"]),
            }
        )
    products_by_name = {row["product_name"]: row for row in products}

    sales_agents = [
        {
            "sales_agent_key": _md5(row["sales_agent"].strip()),
            "sales_agent_name": row["sales_agent"].strip(),
            "manager_name": row["manager"].strip(),
            "regional_office": row["regional_office"].strip(),
        }
        for row in sales_agents_raw
    ]
    sales_agents_by_name = {row["sales_agent_name"]: row for row in sales_agents}

    reference_dates = [
        parsed
        for row in opportunities_raw
        for parsed in [_parse_date(row["close_date"]) or _parse_date(row["engage_date"])]
        if parsed is not None
    ]
    reference_date = max(reference_dates)
    opportunities = []
    for row in opportunities_raw:
        product_name = "GTX Pro" if row["product"].strip() == "GTXPro" else row["product"].strip()
        account_name = row["account"].strip() or None
        deal_stage = row["deal_stage"].strip()
        engage_date = _parse_date(row["engage_date"])
        close_date = _parse_date(row["close_date"])
        is_won = deal_stage == "Won"
        is_lost = deal_stage == "Lost"
        is_open = deal_stage in {"Prospecting", "Engaging"}
        account = accounts_by_name.get(account_name or "")
        product = products_by_name.get(product_name, {})
        sales_agent = sales_agents_by_name.get(row["sales_agent"].strip(), {})
        days_since_engage = (reference_date - engage_date).days if engage_date else None
        close_value = _float(row["close_value"])
        revenue = account.get("revenue_usd_millions") if account else None
        if is_open:
            base = 0.82 if deal_stage == "Prospecting" else 0.68 if deal_stage == "Engaging" else 0.50
            risk_score = round(base + (0.18 if (days_since_engage or 0) >= 120 else 0.0) + (0.08 if (revenue or 0) < 300 else 0.0), 2)
        else:
            risk_score = 0.0
        opportunities.append(
            {
                "opportunity_key": _md5(row["opportunity_id"].strip()),
                "opportunity_id": row["opportunity_id"].strip(),
                "sales_agent_name": row["sales_agent"].strip(),
                "sales_agent_key": sales_agent.get("sales_agent_key"),
                "manager_name": sales_agent.get("manager_name"),
                "regional_office": sales_agent.get("regional_office"),
                "product_name": product_name,
                "product_key": product.get("product_key"),
                "product_series": product.get("product_series"),
                "sales_price": product.get("sales_price"),
                "account_name": account_name,
                "account_key": account.get("account_key") if account else None,
                "sector": account.get("sector") if account else None,
                "revenue_usd_millions": revenue,
                "employees": account.get("employees") if account else None,
                "office_location": account.get("office_location") if account else None,
                "deal_stage": deal_stage,
                "engage_date": engage_date.isoformat() if engage_date else None,
                "close_date": close_date.isoformat() if close_date else None,
                "close_value": close_value,
                "is_closed": int(is_won or is_lost),
                "is_open": int(is_open),
                "is_won": int(is_won),
                "is_lost": int(is_lost),
                "days_since_engage": days_since_engage,
                "days_to_close": (close_date - engage_date).days if close_date and engage_date else None,
                "engage_quarter": _quarter(engage_date),
                "close_quarter": _quarter(close_date),
                "risk_score": risk_score,
            }
        )

    pipeline_health = []
    for key, rows in _group(opportunities, ("engage_quarter", "regional_office", "manager_name", "deal_stage")).items():
        engage_quarter, regional_office, manager_name, deal_stage = key
        open_rows = [row for row in rows if row["is_open"]]
        won_rows = [row for row in rows if row["is_won"]]
        lost_rows = [row for row in rows if row["is_lost"]]
        pipeline_health.append(
            {
                "engage_quarter": engage_quarter,
                "regional_office": regional_office,
                "manager_name": manager_name,
                "deal_stage": deal_stage,
                "opportunity_count": len(rows),
                "open_opportunity_count": len(open_rows),
                "won_opportunity_count": len(won_rows),
                "lost_opportunity_count": len(lost_rows),
                "won_revenue": _sum(row["close_value"] for row in won_rows),
                "open_pipeline_value": _sum((row["close_value"] or row["sales_price"]) for row in open_rows),
                "average_open_risk_score": _avg(row["risk_score"] for row in open_rows),
                "average_open_days": _avg(row["days_since_engage"] for row in open_rows),
            }
        )

    forecast_stage_summary = []
    for key, rows in _group(opportunities, ("engage_quarter", "regional_office", "deal_stage")).items():
        engage_quarter, regional_office, deal_stage = key
        open_rows = [row for row in rows if row["is_open"]]
        likely = []
        best = []
        adjusted = []
        for row in open_rows:
            value = float(row["close_value"] or row["sales_price"] or 0)
            likely_factor = 0.30 if row["deal_stage"] == "Prospecting" else 0.60 if row["deal_stage"] == "Engaging" else 0.0
            best_factor = 0.55 if row["deal_stage"] == "Prospecting" else 0.85 if row["deal_stage"] == "Engaging" else 0.0
            likely.append(value * likely_factor)
            best.append(value * best_factor)
            adjusted.append(value * likely_factor * max(0.45, 1.15 - float(row["risk_score"] or 0)))
        forecast_stage_summary.append(
            {
                "engage_quarter": engage_quarter,
                "regional_office": regional_office,
                "deal_stage": deal_stage,
                "open_opportunity_count": len(open_rows),
                "open_pipeline_value": _sum((row["close_value"] or row["sales_price"]) for row in open_rows),
                "likely_revenue": _sum(likely),
                "best_case_revenue": _sum(best),
                "risk_adjusted_revenue": _sum(adjusted),
                "average_open_risk_score": _avg(row["risk_score"] for row in open_rows),
            }
        )

    product_pipeline = []
    for key, rows in _group(opportunities, ("engage_quarter", "regional_office", "product_name")).items():
        engage_quarter, regional_office, product_name = key
        open_rows = [row for row in rows if row["is_open"]]
        won_rows = [row for row in rows if row["is_won"]]
        lost_rows = [row for row in rows if row["is_lost"]]
        product_pipeline.append(
            {
                "engage_quarter": engage_quarter,
                "regional_office": regional_office,
                "product_name": product_name,
                "open_opportunity_count": len(open_rows),
                "won_opportunity_count": len(won_rows),
                "lost_opportunity_count": len(lost_rows),
                "open_pipeline_value": _sum((row["close_value"] or row["sales_price"]) for row in open_rows),
                "won_revenue": _sum(row["close_value"] for row in won_rows),
                "average_open_risk_score": _avg(row["risk_score"] for row in open_rows),
            }
        )

    stage_bottlenecks = []
    for key, rows in _group(opportunities, ("engage_quarter", "regional_office", "manager_name", "product_name", "deal_stage")).items():
        open_rows = [row for row in rows if row["is_open"]]
        if not open_rows:
            continue
        engage_quarter, regional_office, manager_name, product_name, deal_stage = key
        stage_bottlenecks.append(
            {
                "engage_quarter": engage_quarter,
                "regional_office": regional_office,
                "manager_name": manager_name,
                "product_name": product_name,
                "deal_stage": deal_stage,
                "open_opportunity_count": len(open_rows),
                "open_pipeline_value": _sum((row["close_value"] or row["sales_price"]) for row in open_rows),
                "average_open_days": _avg(row["days_since_engage"] for row in open_rows),
                "average_open_risk_score": _avg(row["risk_score"] for row in open_rows),
            }
        )

    sales_team_performance = []
    for key, rows in _group(pipeline_health, ("engage_quarter", "regional_office", "manager_name")).items():
        engage_quarter, regional_office, manager_name = key
        sales_team_performance.append(
            {
                "engage_quarter": engage_quarter,
                "regional_office": regional_office,
                "manager_name": manager_name,
                "opportunity_count": sum(row["opportunity_count"] for row in rows),
                "open_opportunity_count": sum(row["open_opportunity_count"] for row in rows),
                "won_opportunity_count": sum(row["won_opportunity_count"] for row in rows),
                "lost_opportunity_count": sum(row["lost_opportunity_count"] for row in rows),
                "won_revenue": _sum(row["won_revenue"] for row in rows),
                "open_pipeline_value": _sum(row["open_pipeline_value"] for row in rows),
                "average_open_risk_score": _avg(row["average_open_risk_score"] for row in rows),
                "average_open_days": _avg(row["average_open_days"] for row in rows),
            }
        )

    risk_accounts = []
    for key, rows in _group(opportunities, ("engage_quarter", "regional_office", "account_name")).items():
        engage_quarter, regional_office, account_name = key
        open_rows = [row for row in rows if row["is_open"] and account_name]
        if not open_rows:
            continue
        risk_accounts.append(
            {
                "engage_quarter": engage_quarter,
                "regional_office": regional_office,
                "account_name": account_name,
                "open_opportunity_count": len(open_rows),
                "open_pipeline_value": _sum((row["close_value"] or row["sales_price"]) for row in open_rows),
                "average_risk_score": _avg(row["risk_score"] for row in open_rows),
                "max_days_open": max(row["days_since_engage"] or 0 for row in open_rows),
                "sales_agents": ", ".join(sorted({row["sales_agent_name"] for row in open_rows if row["sales_agent_name"]})),
            }
        )

    account_enrichment = []
    for account in accounts:
        revenue_band = _revenue_band(account["revenue_usd_millions"])
        employee_band = _employee_band(account["employees"])
        sector = account["sector"]
        office = account["office_location"]
        account_enrichment.append(
            {
                "account_name": account["account_name"],
                "sector": sector,
                "office_location": office,
                "parent_company": account["subsidiary_of"] or "independent",
                "revenue_usd_millions": account["revenue_usd_millions"],
                "employees": account["employees"],
                "revenue_band": revenue_band,
                "employee_band": employee_band,
                "icp_fit": _icp_fit(sector, account["revenue_usd_millions"]),
                "intent_signal": _intent_signal(sector, office),
                "likely_buying_motion": _buying_motion(sector),
                "lookalike_key": "|".join([sector, office, revenue_band, employee_band]),
                "enrichment_rationale": (
                    f"Sector={sector}; region={office}; revenue_band={revenue_band}; "
                    f"employee_band={employee_band}; fit={_icp_fit(sector, account['revenue_usd_millions'])}"
                ),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    conn = sqlite3.connect(output_path)
    try:
        account_enrichment_bi = [
            {key: value for key, value in row.items() if key not in {"revenue_usd_millions", "employees", "lookalike_key"}}
            for row in account_enrichment
        ]

        _create_table(conn, "dim_gtm__accounts", _column_types(accounts))
        _create_table(conn, "dim_gtm__products", _column_types(products))
        _create_table(conn, "dim_gtm__sales_agents", _column_types(sales_agents))
        _create_table(conn, "fct_gtm__opportunities", _column_types(opportunities))
        _create_table(conn, "mart_gtm__pipeline_health", _column_types(pipeline_health))
        _create_table(conn, "bi_gtm__pipeline_stage_summary", _column_types(pipeline_health))
        _create_table(conn, "bi_gtm__forecast_stage_summary", _column_types(forecast_stage_summary))
        _create_table(conn, "bi_gtm__product_pipeline", _column_types(product_pipeline))
        _create_table(conn, "bi_gtm__stage_bottlenecks", _column_types(stage_bottlenecks))
        _create_table(conn, "bi_gtm__sales_team_performance", _column_types(sales_team_performance))
        _create_table(conn, "bi_gtm__risk_accounts", _column_types(risk_accounts))
        _create_table(conn, "mart_gtm__account_enrichment", _column_types(account_enrichment))
        _create_table(conn, "bi_gtm__account_enrichment", _column_types(account_enrichment_bi))

        _insert_rows(conn, "dim_gtm__accounts", accounts)
        _insert_rows(conn, "dim_gtm__products", products)
        _insert_rows(conn, "dim_gtm__sales_agents", sales_agents)
        _insert_rows(conn, "fct_gtm__opportunities", opportunities)
        _insert_rows(conn, "mart_gtm__pipeline_health", pipeline_health)
        _insert_rows(conn, "bi_gtm__pipeline_stage_summary", pipeline_health)
        _insert_rows(conn, "bi_gtm__forecast_stage_summary", forecast_stage_summary)
        _insert_rows(conn, "bi_gtm__product_pipeline", product_pipeline)
        _insert_rows(conn, "bi_gtm__stage_bottlenecks", stage_bottlenecks)
        _insert_rows(conn, "bi_gtm__sales_team_performance", sales_team_performance)
        _insert_rows(conn, "bi_gtm__risk_accounts", risk_accounts)
        _insert_rows(conn, "mart_gtm__account_enrichment", account_enrichment)
        _insert_rows(
            conn,
            "bi_gtm__account_enrichment",
            account_enrichment_bi,
        )
        conn.commit()
    finally:
        conn.close()
    return output_path


def main() -> None:
    path = build_database()
    print(f"Built {path}")


if __name__ == "__main__":
    main()

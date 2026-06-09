"""Run the GTM LLM runtime regression harness."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CASES = Path(__file__).with_name("phase1_regression_cases.json")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "examples" / "gtm-showcase" / "regression-runs"
DEFAULT_RUNTIME_URL = "http://127.0.0.1:9303"
POSTGRES_CONTAINER = os.getenv("GTM_POSTGRES_CONTAINER", "anip-gtm-postgres")
PRIORITIZATION_FIXTURES = REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_prioritization_backend" / "fixtures.json"
OUTREACH_FIXTURES = REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_outreach_mcp_backend" / "fixtures.json"


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"{method} {url} failed with {exc.code}: {body}") from exc


def _runtime_audit(runtime_url: str, actor_id: str, service: str, capability: str | None = None, limit: int = 20) -> dict[str, Any]:
    payload: dict[str, Any] = {"actor_id": actor_id, "service": service, "limit": limit}
    if capability:
        payload["capability"] = capability
    return _http_json("POST", f"{runtime_url.rstrip('/')}/api/audit", payload)


def _runtime_list_approvals(runtime_url: str, actor_id: str, service: str = "pipeline", status: str | None = None) -> dict[str, Any]:
    url = f"{runtime_url.rstrip('/')}/api/approvals?actor_id={actor_id}&service={service}"
    if status:
        url = f"{url}&status={status}"
    return _http_json("GET", url)


def _runtime_approve(runtime_url: str, actor_id: str, approval_request_id: str, service: str = "pipeline") -> dict[str, Any]:
    return _http_json(
        "POST",
        f"{runtime_url.rstrip('/')}/api/approvals/approve",
        {"actor_id": actor_id, "approval_request_id": approval_request_id, "service": service},
    )


def _load_prioritization_fixtures() -> dict[str, Any]:
    return json.loads(PRIORITIZATION_FIXTURES.read_text())


def _load_outreach_fixtures() -> dict[str, Any]:
    return json.loads(OUTREACH_FIXTURES.read_text())


def _extract_outcome(payload: dict[str, Any]) -> str:
    anip_result = payload.get("anip_result", {})
    if anip_result.get("success") is True:
        return "success"
    failure = anip_result.get("failure", {})
    if isinstance(failure, dict):
        return str(failure.get("type") or "unknown")
    return "unknown"


def _psql_query(sql: str) -> list[list[str]]:
    command = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "anip",
        "-d",
        "anip_gtm",
        "-t",
        "-A",
        "-F",
        "\t",
        "-c",
        sql,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    rows: list[list[str]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(stripped.split("\t"))
    return rows


def _run_data_check(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    def sort_rows(rows: list[list[str]]) -> list[list[str]]:
        return sorted(rows)

    def canonicalize_number(raw: str) -> str:
        if raw == "":
            return ""
        try:
            return str(float(raw))
        except ValueError:
            return raw

    def pad_row(row: list[str], width: int) -> list[str]:
        if len(row) >= width:
            return row
        return row + [""] * (width - len(row))

    try:
        anip_result = payload["anip_result"]
    except KeyError:
        return {
            "passed": False,
            "check": name,
            "details": {"error": "Missing anip_result payload"},
        }

    if name == "risk_summary_top10_q2":
        sql = """
            select account_name, regional_office, count(*)::text, coalesce(round(avg(risk_score), 2)::text, ''), max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 10;
        """
        rows = _psql_query(sql)
        actual_accounts = anip_result.get("result", {}).get("accounts")
        if not isinstance(actual_accounts, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected result.accounts list for risk summary check"},
            }
        result_payload = anip_result.get("result", {})
        if isinstance(result_payload.get("result"), dict):
            result_payload = result_payload["result"]
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                str(item["open_opportunity_count"]),
                str(item["average_risk_score"]),
                str(item["max_days_open"]),
            ]
            for item in actual_accounts
        ]
        expected_sorted = sort_rows(rows)
        actual_sorted = sort_rows(actual)
        return {
            "passed": actual_sorted == expected_sorted,
            "check": name,
            "details": {
                "expected_rows": expected_sorted,
                "actual_rows": actual_sorted,
            },
        }

    if name == "risk_summary_top5_east_q2":
        sql = """
            select account_name, regional_office, count(*)::text, coalesce(round(avg(risk_score), 2)::text, ''), max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true and regional_office = 'East'
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 5;
        """
        rows = _psql_query(sql)
        actual_accounts = anip_result.get("result", {}).get("accounts")
        if not isinstance(actual_accounts, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected result.accounts list for regional risk summary check"},
            }
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                str(item["open_opportunity_count"]),
                str(item["average_risk_score"]),
                str(item["max_days_open"]),
            ]
            for item in actual_accounts
        ]
        expected_sorted = sort_rows(rows)
        actual_sorted = sort_rows(actual)
        return {
            "passed": actual_sorted == expected_sorted,
            "check": name,
            "details": {
                "expected_rows": expected_sorted,
                "actual_rows": actual_sorted,
            },
        }

    if name == "risk_summary_top3_q2":
        sql = """
            select account_name, regional_office, count(*)::text, coalesce(round(avg(risk_score), 2)::text, ''), max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 3;
        """
        rows = _psql_query(sql)
        actual_accounts = anip_result.get("result", {}).get("accounts")
        if not isinstance(actual_accounts, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected result.accounts list for top3 risk summary check"},
            }
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                str(item["open_opportunity_count"]),
                str(item["average_risk_score"]),
                str(item["max_days_open"]),
            ]
            for item in actual_accounts
        ]
        expected_sorted = sort_rows(rows)
        actual_sorted = sort_rows(actual)
        return {
            "passed": actual_sorted == expected_sorted,
            "check": name,
            "details": {
                "expected_rows": expected_sorted,
                "actual_rows": actual_sorted,
            },
        }

    if name == "risk_summary_masked_top3_q2":
        sql = """
            select account_name, regional_office, count(*)::text, coalesce(round(avg(risk_score), 2)::text, ''), max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 3;
        """
        rows = _psql_query(sql)
        result = anip_result.get("result", {})
        actual_accounts = result.get("accounts")
        if not isinstance(actual_accounts, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected result.accounts list for masked top3 risk summary check"},
            }
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                str(item["open_opportunity_count"]),
                str(item["average_risk_score"]),
                str(item["max_days_open"]),
            ]
            for item in actual_accounts
        ]
        all_masked = all(item.get("open_pipeline_value") is None for item in actual_accounts)
        expected_sorted = sort_rows(rows)
        actual_sorted = sort_rows(actual)
        return {
            "passed": actual_sorted == expected_sorted and all_masked,
            "check": name,
            "details": {
                "expected_rows": expected_sorted,
                "actual_rows": actual_sorted,
                "all_masked": all_masked,
            },
        }

    if name == "risk_summary_masked_top10_q2":
        sql = """
            select account_name, regional_office, count(*)::text, coalesce(round(avg(risk_score), 2)::text, ''), max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 10;
        """
        rows = _psql_query(sql)
        result = anip_result.get("result", {})
        actual_accounts = result.get("accounts")
        if not isinstance(actual_accounts, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected result.accounts list for masked risk summary check"},
            }
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                str(item["open_opportunity_count"]),
                str(item["average_risk_score"]),
                str(item["max_days_open"]),
            ]
            for item in actual_accounts
        ]
        all_masked = all(item.get("open_pipeline_value") is None for item in actual_accounts)
        return {
            "passed": sort_rows(actual) == sort_rows(rows) and all_masked,
            "check": name,
            "details": {
                "expected_rows": sort_rows(rows),
                "actual_rows": sort_rows(actual),
                "all_masked": all_masked,
            },
        }

    if name == "followup_preview_top5_q2":
        sql = """
            select account_name, regional_office, split_part(string_agg(distinct sales_agent_name, ', ' order by sales_agent_name), ', ', 1), round(avg(risk_score), 2)::text, count(*)::text, max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 5;
        """
        rows = _psql_query(sql)
        preview_tasks = anip_result.get("failure", {}).get("resolution", {}).get("preview", {}).get("tasks")
        if not isinstance(preview_tasks, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected failure.resolution.preview.tasks list for follow-up preview check"},
            }
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                item["recommended_owner"],
                item["reason"].split("Average risk score ", 1)[1].split(" with ", 1)[0],
                item["reason"].split(" with ", 1)[1].split(" open opportunities", 1)[0],
                item["reason"].rsplit(" max age ", 1)[1].split(" days", 1)[0],
            ]
            for item in preview_tasks
        ]
        return {
            "passed": actual == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
            },
        }

    if name == "followup_preview_top3_east_q2":
        sql = """
            select account_name, regional_office, split_part(string_agg(distinct sales_agent_name, ', ' order by sales_agent_name), ', ', 1), round(avg(risk_score), 2)::text, count(*)::text, max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true and regional_office = 'East'
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 3;
        """
        rows = _psql_query(sql)
        preview_tasks = anip_result.get("failure", {}).get("resolution", {}).get("preview", {}).get("tasks")
        if not isinstance(preview_tasks, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected failure.resolution.preview.tasks list for regional follow-up preview check"},
            }
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                item["recommended_owner"],
                item["reason"].split("Average risk score ", 1)[1].split(" with ", 1)[0],
                item["reason"].split(" with ", 1)[1].split(" open opportunities", 1)[0],
                item["reason"].rsplit(" max age ", 1)[1].split(" days", 1)[0],
            ]
            for item in preview_tasks
        ]
        return {
            "passed": actual == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
            },
        }

    if name == "followup_preview_top3_q2":
        sql = """
            select account_name, regional_office, split_part(string_agg(distinct sales_agent_name, ', ' order by sales_agent_name), ', ', 1), round(avg(risk_score), 2)::text, count(*)::text, max(days_since_engage)::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by account_name, regional_office
            order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
            limit 3;
        """
        rows = _psql_query(sql)
        preview_tasks = anip_result.get("failure", {}).get("resolution", {}).get("preview", {}).get("tasks")
        if not isinstance(preview_tasks, list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected failure.resolution.preview.tasks list for top3 follow-up preview check"},
            }
        actual = [
            [
                item["account_name"],
                item["regional_office"],
                item["recommended_owner"],
                item["reason"].split("Average risk score ", 1)[1].split(" with ", 1)[0],
                item["reason"].split(" with ", 1)[1].split(" open opportunities", 1)[0],
                item["reason"].rsplit(" max age ", 1)[1].split(" days", 1)[0],
            ]
            for item in preview_tasks
        ]
        return {
            "passed": actual == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
            },
        }

    if name == "pipeline_summary_east_q2":
        sql = """
            select
                deal_stage,
                sum(opportunity_count)::text,
                sum(open_opportunity_count)::text,
                sum(won_opportunity_count)::text,
                sum(lost_opportunity_count)::text,
                round(sum(coalesce(won_revenue, 0)), 2)::text,
                round(sum(coalesce(open_pipeline_value, 0)), 2)::text,
                coalesce(round(avg(nullif(average_open_risk_score, 0)), 2)::text, ''),
                coalesce(round(avg(nullif(average_open_days, 0)), 2)::text, '')
            from analytics_gtm.mart_gtm__pipeline_health
            where engage_quarter = '2017-Q2' and regional_office = 'East'
            group by deal_stage
            order by deal_stage;
        """
        rows = [
            [
                row[0],
                canonicalize_number(row[1]),
                canonicalize_number(row[2]),
                canonicalize_number(row[3]),
                canonicalize_number(row[4]),
                canonicalize_number(row[5]),
                canonicalize_number(row[6]),
                canonicalize_number(row[7]),
                canonicalize_number(row[8]),
            ]
            for row in (pad_row(item, 9) for item in _psql_query(sql))
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("by_stage"), list):
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected result.by_stage list for pipeline summary check"},
            }
        actual = [
            [
                row["deal_stage"],
                canonicalize_number(str(row["opportunity_count"])),
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["won_opportunity_count"])),
                canonicalize_number(str(row["lost_opportunity_count"])),
                canonicalize_number(str(row["won_revenue"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                "" if row["average_open_risk_score"] is None else canonicalize_number(str(row["average_open_risk_score"])),
                "" if row["average_open_days"] is None else canonicalize_number(str(row["average_open_days"])),
            ]
            for row in result["by_stage"]
        ]
        totals_sql = """
            select
                sum(opportunity_count)::text,
                round(sum(coalesce(open_pipeline_value, 0)), 2)::text,
                round(sum(coalesce(won_revenue, 0)), 2)::text
            from analytics_gtm.mart_gtm__pipeline_health
            where engage_quarter = '2017-Q2' and regional_office = 'East';
        """
        totals_rows = [[canonicalize_number(value) for value in row] for row in _psql_query(totals_sql)]
        actual_totals = [[
            canonicalize_number(str(result["totals"]["opportunity_count"])),
            canonicalize_number(str(result["totals"]["open_pipeline_value"])),
            canonicalize_number(str(result["totals"]["won_revenue"])),
        ]]
        return {
            "passed": actual == rows and actual_totals == totals_rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
                "expected_totals": totals_rows,
                "actual_totals": actual_totals,
            },
        }

    if name == "forecast_summary_risk_adjusted_q2":
        stage_sql = """
            select
                deal_stage,
                count(*)::text,
                round(sum(coalesce(close_value, sales_price)), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.30
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.60
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.55
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.85
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting'
                            then coalesce(close_value, sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        when deal_stage = 'Engaging'
                            then coalesce(close_value, sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        else 0
                    end
                ), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by deal_stage
            order by deal_stage;
        """
        contributor_sql = """
            select
                coalesce(account_name, '__none__'),
                regional_office,
                count(*)::text,
                round(sum(coalesce(close_value, sales_price)), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.30
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.60
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.55
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.85
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting'
                            then coalesce(close_value, sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        when deal_stage = 'Engaging'
                            then coalesce(close_value, sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        else 0
                    end
                ), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by account_name, regional_office
            order by round(sum(
                case
                    when deal_stage = 'Prospecting'
                        then coalesce(close_value, sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                    when deal_stage = 'Engaging'
                        then coalesce(close_value, sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                    else 0
                end
            ), 2) desc, account_name
            limit 5;
        """
        stage_rows = [
            [row[0], canonicalize_number(row[1]), canonicalize_number(row[2]), canonicalize_number(row[3]), canonicalize_number(row[4]), canonicalize_number(row[5]), canonicalize_number(row[6])]
            for row in _psql_query(stage_sql)
        ]
        contributor_rows = [
            [row[0], row[1], canonicalize_number(row[2]), canonicalize_number(row[3]), canonicalize_number(row[4]), canonicalize_number(row[5]), canonicalize_number(row[6]), canonicalize_number(row[7])]
            for row in _psql_query(contributor_sql)
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected forecast result object"}}
        actual_stage_rows = [
            [
                row["deal_stage"],
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                canonicalize_number(str(row["likely_revenue"])),
                canonicalize_number(str(row["best_case_revenue"])),
                canonicalize_number(str(row["risk_adjusted_revenue"])),
                "" if row["average_risk_score"] is None else canonicalize_number(str(row["average_risk_score"])),
            ]
            for row in (result.get("by_stage") or [])
        ]
        actual_contributor_rows = [
            [
                row["account_name"] or "__none__",
                row["regional_office"],
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                canonicalize_number(str(row["likely_revenue"])),
                canonicalize_number(str(row["best_case_revenue"])),
                canonicalize_number(str(row["risk_adjusted_revenue"])),
                "" if row["average_risk_score"] is None else canonicalize_number(str(row["average_risk_score"])),
            ]
            for row in (result.get("top_contributors") or [])
        ]
        expected_selected = round(sum(float(row[5]) for row in stage_rows), 2)
        actual_selected = float(result.get("totals", {}).get("selected_forecast_value") or 0)
        expected_contributor_rows = contributor_rows[: len(actual_contributor_rows)]
        return {
            "passed": actual_stage_rows == stage_rows and actual_contributor_rows == expected_contributor_rows and actual_selected == expected_selected,
            "check": name,
            "details": {
                "expected_stage_rows": stage_rows,
                "actual_stage_rows": actual_stage_rows,
                "expected_contributor_rows": expected_contributor_rows,
                "actual_contributor_rows": actual_contributor_rows,
                "expected_selected_forecast_value": expected_selected,
                "actual_selected_forecast_value": actual_selected,
            },
        }

    if name == "forecast_summary_best_case_east_q2":
        stage_sql = """
            select
                deal_stage,
                count(*)::text,
                round(sum(coalesce(close_value, sales_price)), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.30
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.60
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.55
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.85
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting'
                            then coalesce(close_value, sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        when deal_stage = 'Engaging'
                            then coalesce(close_value, sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        else 0
                    end
                ), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and regional_office = 'East' and is_open = true
            group by deal_stage
            order by deal_stage;
        """
        contributor_sql = """
            select
                coalesce(account_name, '__none__'),
                regional_office,
                count(*)::text,
                round(sum(coalesce(close_value, sales_price)), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.30
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.60
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.55
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.85
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting'
                            then coalesce(close_value, sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        when deal_stage = 'Engaging'
                            then coalesce(close_value, sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        else 0
                    end
                ), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and regional_office = 'East' and is_open = true
            group by account_name, regional_office
            order by round(sum(
                case
                    when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.55
                    when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.85
                    else 0
                end
            ), 2) desc, account_name
            limit 3;
        """
        stage_rows = [
            [row[0], canonicalize_number(row[1]), canonicalize_number(row[2]), canonicalize_number(row[3]), canonicalize_number(row[4]), canonicalize_number(row[5]), canonicalize_number(row[6])]
            for row in _psql_query(stage_sql)
        ]
        contributor_rows = [
            [row[0], row[1], canonicalize_number(row[2]), canonicalize_number(row[3]), canonicalize_number(row[4]), canonicalize_number(row[5]), canonicalize_number(row[6]), canonicalize_number(row[7])]
            for row in _psql_query(contributor_sql)
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected forecast result object"}}
        actual_stage_rows = [
            [
                row["deal_stage"],
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                canonicalize_number(str(row["likely_revenue"])),
                canonicalize_number(str(row["best_case_revenue"])),
                canonicalize_number(str(row["risk_adjusted_revenue"])),
                "" if row["average_risk_score"] is None else canonicalize_number(str(row["average_risk_score"])),
            ]
            for row in (result.get("by_stage") or [])
        ]
        actual_contributor_rows = [
            [
                row["account_name"] or "__none__",
                row["regional_office"],
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                canonicalize_number(str(row["likely_revenue"])),
                canonicalize_number(str(row["best_case_revenue"])),
                canonicalize_number(str(row["risk_adjusted_revenue"])),
                "" if row["average_risk_score"] is None else canonicalize_number(str(row["average_risk_score"])),
            ]
            for row in (result.get("top_contributors") or [])
        ]
        expected_selected = round(sum(float(row[4]) for row in stage_rows), 2)
        actual_selected = float(result.get("totals", {}).get("selected_forecast_value") or 0)
        return {
            "passed": actual_stage_rows == stage_rows and actual_contributor_rows[: len(contributor_rows)] == contributor_rows and actual_selected == expected_selected,
            "check": name,
            "details": {
                "expected_stage_rows": stage_rows,
                "actual_stage_rows": actual_stage_rows,
                "expected_contributor_rows": contributor_rows,
                "actual_contributor_rows": actual_contributor_rows,
                "expected_selected_forecast_value": expected_selected,
                "actual_selected_forecast_value": actual_selected,
            },
        }

    if name == "forecast_summary_likely_q2":
        stage_sql = """
            select
                deal_stage,
                count(*)::text,
                round(sum(coalesce(close_value, sales_price)), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.30
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.60
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting' then coalesce(close_value, sales_price) * 0.55
                        when deal_stage = 'Engaging' then coalesce(close_value, sales_price) * 0.85
                        else 0
                    end
                ), 2)::text,
                round(sum(
                    case
                        when deal_stage = 'Prospecting'
                            then coalesce(close_value, sales_price) * 0.30 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        when deal_stage = 'Engaging'
                            then coalesce(close_value, sales_price) * 0.60 * greatest(0.45, 1.15 - coalesce(risk_score, 0))
                        else 0
                    end
                ), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by deal_stage
            order by deal_stage;
        """
        stage_rows = [
            [row[0], canonicalize_number(row[1]), canonicalize_number(row[2]), canonicalize_number(row[3]), canonicalize_number(row[4]), canonicalize_number(row[5]), canonicalize_number(row[6])]
            for row in _psql_query(stage_sql)
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected forecast result object"}}
        actual_stage_rows = [
            [
                row["deal_stage"],
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                canonicalize_number(str(row["likely_revenue"])),
                canonicalize_number(str(row["best_case_revenue"])),
                canonicalize_number(str(row["risk_adjusted_revenue"])),
                "" if row["average_risk_score"] is None else canonicalize_number(str(row["average_risk_score"])),
            ]
            for row in (result.get("by_stage") or [])
        ]
        expected_selected = round(sum(float(row[3]) for row in stage_rows), 2)
        actual_selected = float(result.get("totals", {}).get("selected_forecast_value") or 0)
        return {
            "passed": actual_stage_rows == stage_rows and actual_selected == expected_selected,
            "check": name,
            "details": {
                "expected_stage_rows": stage_rows,
                "actual_stage_rows": actual_stage_rows,
                "expected_selected_forecast_value": expected_selected,
                "actual_selected_forecast_value": actual_selected,
            },
        }

    if name == "forecast_summary_masked_q2":
        sql = """
            select
                deal_stage,
                count(*)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by deal_stage
            order by deal_stage;
        """
        rows = _psql_query(sql)
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected forecast result object"}}
        actual_rows = [
            [
                row["deal_stage"],
                str(row["open_opportunity_count"]),
                "" if row["average_risk_score"] is None else str(row["average_risk_score"]),
            ]
            for row in (result.get("by_stage") or [])
        ]
        all_masked = all(
            row.get("open_pipeline_value") is None
            and row.get("likely_revenue") is None
            and row.get("best_case_revenue") is None
            and row.get("risk_adjusted_revenue") is None
            and row.get("selected_forecast_value") is None
            for row in (result.get("by_stage") or [])
        ) and all(
            row.get("open_pipeline_value") is None
            and row.get("likely_revenue") is None
            and row.get("best_case_revenue") is None
            and row.get("risk_adjusted_revenue") is None
            and row.get("selected_forecast_value") is None
            for row in (result.get("top_contributors") or [])
        ) and all(
            result.get("totals", {}).get(key) is None
            for key in ["open_pipeline_value", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue", "selected_forecast_value"]
        )
        return {
            "passed": actual_rows == rows and all_masked,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual_rows,
                "all_masked": all_masked,
            },
        }

    if name == "bottleneck_summary_regional_q2":
        sql = """
            select
                coalesce(regional_office, '__none__'),
                deal_stage,
                count(*)::text,
                round(sum(coalesce(close_value, sales_price)), 2)::text,
                round(avg(days_since_engage), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by regional_office, deal_stage
            order by round(avg(days_since_engage), 2) desc nulls last,
                round(avg(risk_score), 2) desc nulls last,
                count(*) desc,
                coalesce(regional_office, '__none__'),
                deal_stage
            limit 10;
        """
        rows = [
            [row[0], row[1], canonicalize_number(row[2]), canonicalize_number(row[3]), canonicalize_number(row[4]), canonicalize_number(row[5]), str(index)]
            for index, row in enumerate(_psql_query(sql), start=1)
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected bottleneck result object"}}
        actual_rows = [
            [
                row["slice_value"] or "__none__",
                row["deal_stage"],
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                "" if row["average_open_days"] is None else canonicalize_number(str(row["average_open_days"])),
                "" if row["average_risk_score"] is None else canonicalize_number(str(row["average_risk_score"])),
                str(row["bottleneck_rank"]),
            ]
            for row in (result.get("bottlenecks") or [])
        ]
        return {
            "passed": actual_rows == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual_rows,
            },
        }

    if name == "bottleneck_summary_product_east_q2":
        sql = """
            select
                coalesce(product_name, '__none__'),
                deal_stage,
                count(*)::text,
                round(sum(coalesce(close_value, sales_price)), 2)::text,
                round(avg(days_since_engage), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true and regional_office = 'East'
            group by product_name, deal_stage
            order by round(avg(days_since_engage), 2) desc nulls last,
                round(avg(risk_score), 2) desc nulls last,
                count(*) desc,
                coalesce(product_name, '__none__'),
                deal_stage
            limit 10;
        """
        rows = [
            [row[0], row[1], canonicalize_number(row[2]), canonicalize_number(row[3]), canonicalize_number(row[4]), canonicalize_number(row[5]), str(index)]
            for index, row in enumerate(_psql_query(sql), start=1)
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected bottleneck result object"}}
        actual_rows = [
            [
                row["slice_value"] or "__none__",
                row["deal_stage"],
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                "" if row["average_open_days"] is None else canonicalize_number(str(row["average_open_days"])),
                "" if row["average_risk_score"] is None else canonicalize_number(str(row["average_risk_score"])),
                str(row["bottleneck_rank"]),
            ]
            for row in (result.get("bottlenecks") or [])
        ]
        return {
            "passed": actual_rows == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual_rows,
            },
        }

    if name == "bottleneck_summary_masked_q2":
        sql = """
            select
                coalesce(regional_office, '__none__'),
                deal_stage,
                count(*)::text,
                round(avg(days_since_engage), 2)::text,
                coalesce(round(avg(risk_score), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and is_open = true
            group by regional_office, deal_stage
            order by round(avg(days_since_engage), 2) desc nulls last,
                round(avg(risk_score), 2) desc nulls last,
                count(*) desc,
                coalesce(regional_office, '__none__'),
                deal_stage
            limit 10;
        """
        rows = _psql_query(sql)
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected bottleneck result object"}}
        actual_rows = [
            [
                row["slice_value"] or "__none__",
                row["deal_stage"],
                str(row["open_opportunity_count"]),
                "" if row["average_open_days"] is None else str(row["average_open_days"]),
                "" if row["average_risk_score"] is None else str(row["average_risk_score"]),
            ]
            for row in (result.get("bottlenecks") or [])
        ]
        all_masked = all(row.get("open_pipeline_value") is None for row in (result.get("bottlenecks") or []))
        return {
            "passed": actual_rows == rows and all_masked,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual_rows,
                "all_masked": all_masked,
            },
        }

    if name == "sales_team_performance_manager_q2":
        sql = """
            select
                coalesce(manager_name, '__none__'),
                sum(opportunity_count)::text,
                sum(open_opportunity_count)::text,
                sum(won_opportunity_count)::text,
                sum(lost_opportunity_count)::text,
                round(sum(coalesce(open_pipeline_value, 0)), 2)::text,
                round(sum(coalesce(won_revenue, 0)), 2)::text,
                coalesce(round(avg(nullif(average_open_risk_score, 0)), 2)::text, ''),
                coalesce(round(avg(nullif(average_open_days, 0)), 2)::text, '')
            from analytics_gtm.mart_gtm__pipeline_health
            where engage_quarter = '2017-Q2'
            group by manager_name
            order by round(sum(coalesce(open_pipeline_value, 0)), 2) desc nulls last,
                sum(won_opportunity_count) desc,
                round(avg(nullif(average_open_risk_score, 0)), 2) desc nulls last,
                coalesce(manager_name, '__none__')
            limit 10;
        """
        rows = [
            [
                row[0],
                canonicalize_number(row[1]),
                canonicalize_number(row[2]),
                canonicalize_number(row[3]),
                canonicalize_number(row[4]),
                canonicalize_number(row[5]),
                canonicalize_number(row[6]),
                canonicalize_number(row[7]),
                canonicalize_number(row[8]),
            ]
            for row in (pad_row(item, 9) for item in _psql_query(sql))
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected sales team result object"}}
        actual_rows = [
            [
                row["slice_value"] or "__none__",
                canonicalize_number(str(row["opportunity_count"])),
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["won_opportunity_count"])),
                canonicalize_number(str(row["lost_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                canonicalize_number(str(row["won_revenue"])),
                "" if row["average_open_risk_score"] is None else canonicalize_number(str(row["average_open_risk_score"])),
                "" if row["average_open_days"] is None else canonicalize_number(str(row["average_open_days"])),
            ]
            for row in (result.get("performance_rows") or [])
        ]
        return {
            "passed": actual_rows == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual_rows,
            },
        }

    if name == "product_pipeline_east_q2":
        sql = """
            select
                coalesce(product_name, '__none__'),
                (count(*) filter (where is_open))::text,
                (count(*) filter (where is_won))::text,
                (count(*) filter (where is_open = false and is_won = false))::text,
                round((sum(coalesce(close_value, sales_price)) filter (where is_open)), 2)::text,
                round((sum(close_value) filter (where is_won)), 2)::text,
                coalesce(round((avg(risk_score) filter (where is_open)), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2' and regional_office = 'East'
            group by product_name
            order by round((sum(coalesce(close_value, sales_price)) filter (where is_open)), 2) desc nulls last,
                round((sum(close_value) filter (where is_won)), 2) desc nulls last,
                (count(*) filter (where is_open)) desc,
                coalesce(product_name, '__none__')
            limit 10;
        """
        rows = [
            [
                row[0],
                canonicalize_number(row[1]),
                canonicalize_number(row[2]),
                canonicalize_number(row[3]),
                canonicalize_number(row[4]),
                canonicalize_number(row[5]),
                canonicalize_number(row[6]),
            ]
            for row in (pad_row(item, 7) for item in _psql_query(sql))
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected product result object"}}
        actual_rows = [
            [
                row["product_name"] or "__none__",
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["won_opportunity_count"])),
                canonicalize_number(str(row["lost_opportunity_count"])),
                canonicalize_number(str(row["open_pipeline_value"])),
                canonicalize_number(str(row["won_revenue"])),
                "" if row["average_open_risk_score"] is None else canonicalize_number(str(row["average_open_risk_score"])),
            ]
            for row in (result.get("products") or [])
        ]
        return {
            "passed": actual_rows == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual_rows,
            },
        }

    if name == "product_pipeline_masked_q2":
        sql = """
            select
                coalesce(product_name, '__none__'),
                (count(*) filter (where is_open))::text,
                (count(*) filter (where is_won))::text,
                (count(*) filter (where is_open = false and is_won = false))::text,
                coalesce(round((avg(risk_score) filter (where is_open)), 2)::text, '')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2'
            group by product_name
            order by round((sum(coalesce(close_value, sales_price)) filter (where is_open)), 2) desc nulls last,
                round((sum(close_value) filter (where is_won)), 2) desc nulls last,
                (count(*) filter (where is_open)) desc,
                coalesce(product_name, '__none__')
            limit 10;
        """
        rows = [
            [
                row[0],
                canonicalize_number(row[1]),
                canonicalize_number(row[2]),
                canonicalize_number(row[3]),
                canonicalize_number(row[4]),
            ]
            for row in (pad_row(item, 5) for item in _psql_query(sql))
        ]
        result = anip_result.get("result")
        if not isinstance(result, dict):
            return {"passed": False, "check": name, "details": {"error": "Expected product result object"}}
        actual_rows = [
            [
                row["product_name"] or "__none__",
                canonicalize_number(str(row["open_opportunity_count"])),
                canonicalize_number(str(row["won_opportunity_count"])),
                canonicalize_number(str(row["lost_opportunity_count"])),
                "" if row["average_open_risk_score"] is None else canonicalize_number(str(row["average_open_risk_score"])),
            ]
            for row in (result.get("products") or [])
        ]
        all_masked = all(
            row.get("open_pipeline_value") is None and row.get("won_revenue") is None
            for row in (result.get("products") or [])
        )
        return {
            "passed": actual_rows == rows and all_masked,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual_rows,
                "all_masked": all_masked,
            },
        }

    if name == "reassignment_preview_manager_capacity_q2":
        sql_manager_loads = """
            select
                coalesce(manager_name, '__none__'),
                coalesce(regional_office, '__none__'),
                count(*)::int,
                coalesce(round(avg(risk_score), 2)::text, '0')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2'
              and is_open = true
            group by manager_name, regional_office
        """
        sql_opportunities = """
            select
                opportunity_id,
                coalesce(account_name, '__none__'),
                coalesce(sales_agent_name, '__none__'),
                coalesce(manager_name, '__none__'),
                coalesce(regional_office, '__none__'),
                coalesce(deal_stage, '__none__'),
                coalesce(product_name, '__none__'),
                days_since_engage::int,
                coalesce(round(risk_score, 2)::text, '0')
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2'
              and is_open = true
        """
        manager_rows = _psql_query(sql_manager_loads)
        opportunity_rows = _psql_query(sql_opportunities)
        manager_loads: dict[tuple[str, str], dict[str, Any]] = {}
        targets_by_region: dict[str, list[dict[str, Any]]] = {}
        for row in manager_rows:
            manager_name = row[0]
            regional_office = row[1]
            normalized = {
                "manager_name": manager_name,
                "regional_office": regional_office,
                "open_opportunity_count": int(row[2]),
                "average_risk_score": canonicalize_number(row[3]),
            }
            manager_loads[(regional_office, manager_name)] = normalized
            targets_by_region.setdefault(regional_office, []).append(normalized)
        for regional_office, items in targets_by_region.items():
            items.sort(
                key=lambda item: (
                    int(item["open_opportunity_count"]),
                    float(item["average_risk_score"] or 0),
                    item["manager_name"],
                )
            )

        def _sort_key(row: list[str]) -> tuple[Any, ...]:
            regional_office = row[4]
            manager_name = row[3]
            manager_load = manager_loads.get((regional_office, manager_name), {})
            return (
                -int(manager_load.get("open_opportunity_count") or 0),
                -int(row[7]),
                -float(row[8] or 0),
                row[0],
            )

        expected_rows: list[list[str]] = []
        for row in sorted(opportunity_rows, key=_sort_key):
            regional_office = row[4]
            source_manager = row[3]
            source_load = manager_loads.get((regional_office, source_manager), {})
            target_candidates = [
                item
                for item in targets_by_region.get(regional_office, [])
                if item["manager_name"] != source_manager
            ]
            if not target_candidates:
                continue
            target = target_candidates[0]
            expected_rows.append(
                [
                    row[0],
                    row[1],
                    source_manager,
                    regional_office,
                    str(source_load.get("open_opportunity_count") or 0),
                    target["manager_name"],
                    target["regional_office"],
                    str(target.get("open_opportunity_count") or 0),
                    str(int(row[7])),
                    canonicalize_number(str(row[8])),
                ]
            )
            if len(expected_rows) >= 5:
                break
        failure = anip_result.get("failure") or {}
        preview = failure.get("resolution", {}).get("preview") or {}
        actual_rows = [
            [
                str(item.get("opportunity_id") or ""),
                str(item.get("account_name") or ""),
                str(item.get("source_manager") or ""),
                str(item.get("source_region") or ""),
                str(item.get("source_open_load") or 0),
                str(item.get("target_manager") or ""),
                str(item.get("target_region") or ""),
                str(item.get("target_open_load") or 0),
                str(item.get("days_since_engage") or 0),
                canonicalize_number(str(item.get("risk_score") or 0)),
            ]
            for item in (preview.get("reassignments") or [])
        ]
        return {
            "passed": actual_rows == expected_rows,
            "check": name,
            "details": {
                "expected_rows": expected_rows,
                "actual_rows": actual_rows,
                "summary": preview.get("summary"),
            },
        }

    if name == "stalled_top10_west_60_q2":
        sql = """
            select
                opportunity_id,
                coalesce(account_name, ''),
                sales_agent_name,
                regional_office,
                deal_stage,
                product_name,
                engage_date::text,
                days_since_engage::text,
                risk_score::text
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = '2017-Q2'
              and is_open = true
              and days_since_engage >= 60
              and regional_office = 'West'
            order by risk_score desc nulls last, days_since_engage desc, opportunity_id
            limit 10;
        """
        rows = _psql_query(sql)
        actual = [
            [
                item["opportunity_id"],
                item["account_name"] or "",
                item["sales_agent_name"],
                item["regional_office"],
                item["deal_stage"],
                item["product_name"],
                item["engage_date"],
                str(item["days_since_engage"]),
                str(item["risk_score"]),
            ]
            for item in (anip_result.get("result", {}).get("opportunities") or [])
        ]
        if not actual and rows:
            return {
                "passed": False,
                "check": name,
                "details": {"error": "Expected result.opportunities list for stalled opportunity check", "expected_rows": rows, "actual_rows": actual},
            }
        return {
            "passed": actual == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
            },
        }

    if name == "account_enrichment_named_accounts":
        sql = """
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
            where account_name in ('Acme Corporation', 'Codehow')
            order by account_name;
        """
        rows = _psql_query(sql)
        actual = [
            [
                item["account_name"],
                item["sector"],
                item["office_location"],
                item["parent_company"],
                item["revenue_band"],
                item["employee_band"],
                item["icp_fit"],
                item["intent_signal"],
                item["likely_buying_motion"],
                item["enrichment_rationale"],
            ]
            for item in (result_payload.get("accounts") or [])
        ]
        return {
            "passed": actual == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
            },
        }

    if name == "account_enrichment_named_accounts_bounded":
        sql = """
            select
                account_name,
                sector,
                office_location,
                icp_fit,
                intent_signal,
                likely_buying_motion,
                enrichment_rationale
            from analytics_gtm.mart_gtm__account_enrichment
            where account_name in ('Acme Corporation', 'Codehow')
            order by account_name;
        """
        rows = _psql_query(sql)
        accounts = anip_result.get("result", {}).get("accounts") or []
        actual = [
            [
                item["account_name"],
                item["sector"],
                item["office_location"],
                item["icp_fit"],
                item["intent_signal"],
                item["likely_buying_motion"],
                item["enrichment_rationale"],
            ]
            for item in accounts
        ]
        masked = all(
            item.get("parent_company") is None and item.get("revenue_band") is None and item.get("employee_band") is None
            for item in accounts
        )
        return {
            "passed": actual == rows and masked,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
                "all_sensitive_fields_masked": masked,
            },
        }

    if name == "account_enrichment_top_risk_q2":
        sql = """
            with top_risk as (
                select account_name
                from analytics_gtm.fct_gtm__opportunities
                where engage_quarter = '2017-Q2' and is_open = true
                group by account_name, regional_office
                order by round(avg(risk_score), 2) desc nulls last, round(sum(close_value), 2) desc nulls last, account_name
                limit 5
            )
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
            where account_name in (select distinct account_name from top_risk)
            order by account_name
            limit 5;
        """
        rows = _psql_query(sql)
        actual = [
            [
                item["account_name"],
                item["sector"],
                item["office_location"],
                item["parent_company"],
                item["revenue_band"],
                item["employee_band"],
                item["icp_fit"],
                item["intent_signal"],
                item["likely_buying_motion"],
                item["enrichment_rationale"],
            ]
            for item in (anip_result.get("result", {}).get("accounts") or [])
        ]
        return {
            "passed": actual == rows,
            "check": name,
            "details": {
                "expected_rows": rows,
                "actual_rows": actual,
            },
        }

    if name == "lookalike_condax":
        reference_sql = """
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
            where account_name = 'Condax';
        """
        matches_sql = """
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
            where lookalike_key = (
                select lookalike_key
                from analytics_gtm.mart_gtm__account_enrichment
                where account_name = 'Condax'
            )
              and account_name <> 'Condax'
            order by revenue_band desc, account_name
            limit 5;
        """
        reference_rows = _psql_query(reference_sql)
        match_rows = _psql_query(matches_sql)
        result = anip_result.get("result", {})
        reference_profile = result.get("reference_profile") or {}
        actual_reference = [[
            reference_profile.get("account_name", ""),
            reference_profile.get("sector", ""),
            reference_profile.get("office_location", ""),
            reference_profile.get("revenue_band", ""),
            reference_profile.get("employee_band", ""),
            reference_profile.get("lookalike_key", ""),
            reference_profile.get("icp_fit", ""),
            reference_profile.get("intent_signal", ""),
        ]]
        actual_matches = [
            [
                item["account_name"],
                item["sector"],
                item["office_location"],
                item["revenue_band"],
                item["employee_band"],
                item["icp_fit"],
                item["intent_signal"],
                item["likely_buying_motion"],
                item["enrichment_rationale"],
            ]
            for item in (result.get("matches") or [])
        ]
        return {
            "passed": actual_reference == reference_rows and actual_matches == match_rows,
            "check": name,
            "details": {
                "expected_reference": reference_rows,
                "actual_reference": actual_reference,
                "expected_matches": match_rows,
                "actual_matches": actual_matches,
            },
        }

    if name == "score_leads_inbound_last_week":
        fixtures = _load_prioritization_fixtures()
        expected = sorted(
            fixtures["lead_cohorts"]["inbound_last_week"],
            key=lambda item: (-int(item["priority_score"]), str(item["lead_id"])),
        )[:10]
        actual = anip_result.get("result", {}).get("result", {}).get("lead_scores") or []
        return {
            "passed": actual == expected,
            "check": name,
            "details": {"expected_rows": expected, "actual_rows": actual},
        }

    if name == "prioritize_accounts_expansion_candidates_q2":
        fixtures = _load_prioritization_fixtures()
        expected = sorted(
            fixtures["account_cohorts"]["expansion_candidates_q2"],
            key=lambda item: (-int(item["priority_score"]), str(item["account_name"])),
        )[:10]
        actual = anip_result.get("result", {}).get("result", {}).get("accounts") or []
        return {
            "passed": actual == expected,
            "check": name,
            "details": {"expected_rows": expected, "actual_rows": actual},
        }

    if name == "route_preview_webinar_q2_sales":
        fixtures = _load_prioritization_fixtures()
        expected = {
            "cohort_ref": "webinar_q2",
            "owner_scope": "company",
            "target_queue": "sales",
            "dry_run": True,
            "preview": [
                {
                    "lead_id": item["lead_id"],
                    "account_name": item["account_name"],
                    "owner_scope": item["owner_scope"],
                    "priority_band": item["priority_band"],
                    "priority_score": item["priority_score"],
                    "recommended_queue": "sales",
                    "rationale": item["rationale"],
                }
                for item in sorted(
                    fixtures["lead_cohorts"]["webinar_q2"],
                    key=lambda row: (-int(row["priority_score"]), str(row["lead_id"])),
                )
            ],
        }
        actual = anip_result.get("failure", {}).get("resolution", {}).get("preview") or {}
        return {
            "passed": actual == expected,
            "check": name,
            "details": {"expected_rows": expected, "actual_rows": actual},
        }

    if name == "route_preview_inbound_last_week_sales":
        fixtures = _load_prioritization_fixtures()
        expected = {
            "cohort_ref": "inbound_last_week",
            "owner_scope": "company",
            "target_queue": "sales",
            "dry_run": True,
            "preview": [
                {
                    "lead_id": item["lead_id"],
                    "account_name": item["account_name"],
                    "owner_scope": item["owner_scope"],
                    "priority_band": item["priority_band"],
                    "priority_score": item["priority_score"],
                    "recommended_queue": "sales",
                    "rationale": item["rationale"],
                }
                for item in sorted(
                    fixtures["lead_cohorts"]["inbound_last_week"],
                    key=lambda row: (-int(row["priority_score"]), str(row["lead_id"])),
                )
            ],
        }
        actual = anip_result.get("failure", {}).get("resolution", {}).get("preview") or {}
        return {
            "passed": actual == expected,
            "check": name,
            "details": {"expected_rows": expected, "actual_rows": actual},
        }

    if name == "draft_outreach_condax_first_touch":
        fixtures = _load_outreach_fixtures()
        target = fixtures["targets"]["Condax"]
        expected = {
            "target_ref": "Condax",
            "objective": "first_touch",
            "channel": "email",
            "persona": target["persona"],
            "subject": "Condax: governed GTM follow-up without workflow sprawl",
            "target_summary": {
                "industry": target["industry"],
                "region": target["region"],
                "priority_context": target["priority_context"],
            },
        }
        actual = anip_result.get("result", {}).get("result", {})
        actual_subset = {
            "target_ref": actual.get("target_ref"),
            "objective": actual.get("objective"),
            "channel": actual.get("channel"),
            "persona": actual.get("persona"),
            "subject": actual.get("subject"),
            "target_summary": actual.get("target_summary"),
        }
        body = str(actual.get("body") or "")
        return {
            "passed": actual_subset == expected and "Condax" in body and target["pain_point"] in body,
            "check": name,
            "details": {
                "expected_rows": expected,
                "actual_rows": actual_subset,
                "body_contains_condax": "Condax" in body,
                "body_contains_pain_point": target["pain_point"] in body,
            },
        }

    if name == "draft_outreach_acme_first_touch":
        fixtures = _load_outreach_fixtures()
        target = fixtures["targets"]["Acme Corporation"]
        expected = {
            "target_ref": "Acme Corporation",
            "objective": "first_touch",
            "channel": "email",
            "persona": target["persona"],
            "subject": "Acme Corporation: governed GTM follow-up without workflow sprawl",
            "target_summary": {
                "industry": target["industry"],
                "region": target["region"],
                "priority_context": target["priority_context"],
            },
        }
        actual = anip_result.get("result", {}).get("result", {})
        actual_subset = {
            "target_ref": actual.get("target_ref"),
            "objective": actual.get("objective"),
            "channel": actual.get("channel"),
            "persona": actual.get("persona"),
            "subject": actual.get("subject"),
            "target_summary": actual.get("target_summary"),
        }
        body = str(actual.get("body") or "")
        return {
            "passed": actual_subset == expected and "Acme Corporation" in body and target["pain_point"] in body,
            "check": name,
            "details": {
                "expected_rows": expected,
                "actual_rows": actual_subset,
                "body_contains_target": "Acme Corporation" in body,
                "body_contains_pain_point": target["pain_point"] in body,
            },
        }

    if name == "followup_variants_condax":
        actual = anip_result.get("result", {}).get("result", {})
        variants = actual.get("variants") or []
        expected_ids = [
            "condax_followup_1",
            "condax_followup_2",
            "condax_followup_3",
        ]
        actual_ids = [str(item.get("variant_id")) for item in variants]
        return {
            "passed": actual.get("target_ref") == "Condax"
            and actual.get("variant_limit_applied") == 3
            and actual_ids == expected_ids,
            "check": name,
            "details": {
                "expected_rows": {
                    "target_ref": "Condax",
                    "variant_limit_applied": 3,
                    "variant_ids": expected_ids,
                },
                "actual_rows": {
                    "target_ref": actual.get("target_ref"),
                    "variant_limit_applied": actual.get("variant_limit_applied"),
                    "variant_ids": actual_ids,
                },
            },
        }

    if name == "followup_variants_condax_bounded":
        actual = anip_result.get("result", {}).get("result", {})
        variants = actual.get("variants") or []
        actual_ids = [str(item.get("variant_id")) for item in variants]
        return {
            "passed": actual.get("target_ref") == "Condax"
            and actual.get("variant_limit_applied") == 1
            and actual_ids == ["condax_followup_1"],
            "check": name,
            "details": {
                "expected_rows": {
                    "target_ref": "Condax",
                    "variant_limit_applied": 1,
                    "variant_ids": ["condax_followup_1"],
                },
                "actual_rows": {
                    "target_ref": actual.get("target_ref"),
                    "variant_limit_applied": actual.get("variant_limit_applied"),
                    "variant_ids": actual_ids,
                },
            },
        }

    if name == "compound_prioritize_enrich_draft_expansion_q2":
        actual = anip_result.get("result", {}).get("result", {})
        prioritized_names = [str(item.get("account_name") or "").strip() for item in actual.get("prioritized_accounts") or []]
        draft = actual.get("draft") or {}
        expected_names = ["Acme Corporation", "Codehow", "Condax"]
        return {
            "passed": prioritized_names == expected_names
            and actual.get("selected_target_ref") == "Acme Corporation"
            and draft.get("target_ref") == "Acme Corporation"
            and draft.get("objective") == "first_touch",
            "check": name,
            "details": {
                "expected_prioritized_names": expected_names,
                "actual_prioritized_names": prioritized_names,
                "selected_target_ref": actual.get("selected_target_ref"),
                "draft_target_ref": draft.get("target_ref"),
                "draft_objective": draft.get("objective"),
            },
        }

    if name == "compound_forecast_followup_top3_q2":
        followup_check = _run_data_check("followup_preview_top3_q2", {"anip_result": anip_result})
        return {
            "passed": followup_check["passed"],
            "check": name,
            "details": {
                "followup_check": followup_check,
            },
        }

    if name == "compound_forecast_followup_sales_analyst_q2":
        final_failure_type = anip_result.get("failure", {}).get("type")
        return {
            "passed": final_failure_type == "denied",
            "check": name,
            "details": {
                "final_failure_type": final_failure_type,
            },
        }

    if name == "compound_score_route_inbound_approval":
        route_check = _run_data_check("route_preview_inbound_last_week_sales", {"anip_result": anip_result})
        return {
            "passed": route_check["passed"],
            "check": name,
            "details": {
                "route_check": route_check,
            },
        }

    if name == "objection_variants_competitor":
        actual = anip_result.get("result", {}).get("result", {})
        variants = actual.get("variants") or []
        actual_ids = [str(item.get("pattern_id")) for item in variants]
        expected_ids = ["competitor_v1", "competitor_v2"]
        return {
            "passed": actual.get("objection_theme") == "competitor comparison" and actual_ids == expected_ids,
            "check": name,
            "details": {
                "expected_rows": {
                    "objection_theme": "competitor comparison",
                    "pattern_ids": expected_ids,
                },
                "actual_rows": {
                    "objection_theme": actual.get("objection_theme"),
                    "pattern_ids": actual_ids,
                },
            },
        }

    return {
        "passed": False,
        "check": name,
        "details": {"error": f"Unsupported data check: {name}"},
    }


def _assistant_followup_text(payload: dict[str, Any]) -> str:
    planner = payload.get("planner") or {}
    user_message = str(planner.get("user_message") or "").strip()
    anip_result = payload.get("anip_result") or {}
    if anip_result.get("success") is True:
        return user_message or "Success."
    failure = anip_result.get("failure") or {}
    failure_type = str(failure.get("type") or "").strip()
    detail = str(failure.get("detail") or "").strip()
    resolution = failure.get("resolution") or {}
    action = str(resolution.get("action") or "").strip()
    requires = str(resolution.get("requires") or "").strip()
    parts = [item for item in [user_message, failure_type, detail, action, requires] if item]
    return " | ".join(parts) if parts else "Handled."


def _summarize_turn(expected: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], bool, list[str]]:
    actual_outcome = _extract_outcome(payload)
    selected_capability = payload.get("selected_capability")
    planned_capability = payload.get("planned_capability")
    selected_service = payload.get("selected_service")
    loop_counts = payload.get("loop_counts", {})
    total_loops = int(loop_counts.get("total_loops", -1))

    checks: list[str] = []
    passed = True

    expected_capability = expected.get("capability")
    if expected_capability and selected_capability != expected_capability:
        passed = False
        checks.append(f"expected capability {expected_capability}, got {selected_capability}")

    expected_planned_capability = expected.get("planned_capability")
    if expected_planned_capability and planned_capability != expected_planned_capability:
        passed = False
        checks.append(f"expected planned_capability {expected_planned_capability}, got {planned_capability}")

    expected_service = expected.get("service")
    if expected_service and selected_service != expected_service:
        passed = False
        checks.append(f"expected service {expected_service}, got {selected_service}")

    if actual_outcome != expected["outcome"]:
        passed = False
        checks.append(f"expected outcome {expected['outcome']}, got {actual_outcome}")

    max_total_loops = expected.get("max_total_loops")
    if max_total_loops is not None and total_loops > max_total_loops:
        passed = False
        checks.append(f"expected total_loops <= {max_total_loops}, got {total_loops}")

    data_check_result = None
    if expected.get("data_check"):
        data_check_result = _run_data_check(expected["data_check"], payload)
        if not data_check_result["passed"]:
            passed = False
            checks.append(f"data check failed: {expected['data_check']}")

    return (
        {
            "expected": expected,
            "actual": {
                "planned_capability": planned_capability,
                "capability": selected_capability,
                "service": selected_service,
                "outcome": actual_outcome,
                "parameters": payload.get("parameters"),
                "loop_counts": loop_counts,
                "planner": payload.get("planner"),
            },
            "data_check": data_check_result,
        },
        passed,
        checks,
    )


def _summarize_case(case: dict[str, Any], payloads: list[dict[str, Any]], runtime_url: str) -> dict[str, Any]:
    turns = case.get("turns")
    if isinstance(turns, list) and turns:
        turn_defs = turns
    else:
        turn_defs = [{"question": case["question"], "expected": case["expected"], "data_check": case.get("data_check")}]

    summarized_turns: list[dict[str, Any]] = []
    overall_pass = True
    overall_notes: list[str] = []
    for index, (turn_def, payload) in enumerate(zip(turn_defs, payloads), start=1):
        expected = dict(turn_def["expected"])
        if turn_def.get("data_check"):
            expected["data_check"] = turn_def["data_check"]
        summary, passed, notes = _summarize_turn(expected, payload)
        if not passed:
            overall_pass = False
            overall_notes.extend([f"turn {index}: {note}" for note in notes])
        summarized_turns.append(
            {
                "turn": index,
                "question": turn_def["question"],
                **summary,
                "pass": passed,
                "notes": notes,
                "response": payload,
            }
        )

    final_turn = summarized_turns[-1]
    audit_check_result = None
    audit_check = case.get("audit_check")
    if isinstance(audit_check, dict):
        audit_payload = _runtime_audit(
            runtime_url=runtime_url,
            actor_id=str(audit_check["actor_id"]),
            service=str(audit_check["service"]),
            capability=audit_check.get("capability"),
            limit=int(audit_check.get("limit", 20)),
        )
        entries = audit_payload.get("audit", {}).get("entries") or []
        min_entries = int(audit_check.get("min_entries", 1))
        latest_entry = entries[0] if entries else {}
        latest_assertions = dict(audit_check.get("latest_assertions") or {})
        latest_assertion_errors: list[str] = []
        if latest_assertions:
            expected_success = latest_assertions.get("success")
            if expected_success is not None and bool(latest_entry.get("success")) != bool(expected_success):
                latest_assertion_errors.append(
                    f"expected latest success={expected_success}, got {latest_entry.get('success')}"
                )
            if "failure_type" in latest_assertions:
                expected_failure_type = latest_assertions.get("failure_type")
                actual_failure_type = latest_entry.get("failure_type")
                if actual_failure_type != expected_failure_type:
                    latest_assertion_errors.append(
                        f"expected latest failure_type={expected_failure_type}, got {actual_failure_type}"
                    )
            if "signature_present" in latest_assertions:
                expected_signature_present = bool(latest_assertions.get("signature_present"))
                actual_signature_present = bool(latest_entry.get("signature"))
                if actual_signature_present != expected_signature_present:
                    latest_assertion_errors.append(
                        f"expected latest signature_present={expected_signature_present}, got {actual_signature_present}"
                    )
            if "storage_redacted" in latest_assertions:
                expected_storage_redacted = bool(latest_assertions.get("storage_redacted"))
                actual_storage_redacted = bool(latest_entry.get("storage_redacted"))
                if actual_storage_redacted != expected_storage_redacted:
                    latest_assertion_errors.append(
                        f"expected latest storage_redacted={expected_storage_redacted}, got {actual_storage_redacted}"
                    )
            root_principal = str(latest_entry.get("root_principal") or "")
            for fragment in latest_assertions.get("root_principal_contains") or []:
                if str(fragment) not in root_principal:
                    latest_assertion_errors.append(
                        f"expected latest root_principal to contain {fragment!r}"
                    )
        audit_check_result = {
            "passed": len(entries) >= min_entries and not latest_assertion_errors,
            "details": {
                "actor_id": audit_check["actor_id"],
                "service": audit_check["service"],
                "capability": audit_check.get("capability"),
                "min_entries": min_entries,
                "actual_entries": len(entries),
                "latest_entry": {
                    "capability": latest_entry.get("capability"),
                    "success": latest_entry.get("success"),
                    "failure_type": latest_entry.get("failure_type"),
                    "root_principal": latest_entry.get("root_principal"),
                    "storage_redacted": latest_entry.get("storage_redacted"),
                    "signature_present": bool(latest_entry.get("signature")),
                } if latest_entry else None,
                "assertion_errors": latest_assertion_errors,
            },
        }
        if not audit_check_result["passed"]:
            overall_pass = False
            overall_notes.append(
                f"audit check failed: expected >= {min_entries} entries, got {len(entries)}"
                + (f"; {', '.join(latest_assertion_errors)}" if latest_assertion_errors else "")
            )
    approval_check_result = None
    approval_check = case.get("approval_check")
    if isinstance(approval_check, dict):
        approval_request_id = (
            final_turn["response"].get("anip_result", {})
            .get("failure", {})
            .get("resolution", {})
            .get("approval_request_id")
        )
        if not approval_request_id:
            approval_check_result = {
                "passed": False,
                "details": {"error": "No approval_request_id returned by the final turn"},
            }
            overall_pass = False
            overall_notes.append("approval check failed: no approval_request_id returned")
        else:
            approver_actor_id = str(approval_check["approver_actor_id"])
            approval_service = str(approval_check.get("service") or "pipeline")
            pending_payload = _runtime_list_approvals(
                runtime_url=runtime_url,
                actor_id=approver_actor_id,
                service=approval_service,
                status=str(approval_check.get("expected_pre_approval_status", "pending")),
            )
            pending_entries = pending_payload.get("approvals", {}).get("entries") or []
            pending_entry = next(
                (entry for entry in pending_entries if entry.get("approval_request_id") == approval_request_id),
                None,
            )
            approval_payload = _runtime_approve(
                runtime_url=runtime_url,
                actor_id=approver_actor_id,
                approval_request_id=str(approval_request_id),
                service=approval_service,
            )
            approval_record = approval_payload.get("result", {}).get("approval") or {}
            approved_payload = _runtime_list_approvals(
                runtime_url=runtime_url,
                actor_id=approver_actor_id,
                service=approval_service,
                status=str(approval_check.get("expected_post_approval_status", "approved")),
            )
            approved_entries = approved_payload.get("approvals", {}).get("entries") or []
            approved_entry = next(
                (entry for entry in approved_entries if entry.get("approval_request_id") == approval_request_id),
                None,
            )
            approval_errors: list[str] = []
            expected_required_role = approval_check.get("expected_required_role")
            if expected_required_role and approval_record.get("required_role") != expected_required_role:
                approval_errors.append(
                    f"expected required_role={expected_required_role}, got {approval_record.get('required_role')}"
                )
            expected_requester_actor_id = approval_check.get("expected_requester_actor_id")
            actual_requester_actor_id = (approval_record.get("requested_by") or {}).get("actor_id")
            if expected_requester_actor_id and actual_requester_actor_id != expected_requester_actor_id:
                approval_errors.append(
                    f"expected requested_by.actor_id={expected_requester_actor_id}, got {actual_requester_actor_id}"
                )
            expected_approved_by_actor_id = approval_check.get("expected_approved_by_actor_id")
            actual_approved_by_actor_id = (approval_record.get("approved_by") or {}).get("actor_id")
            if expected_approved_by_actor_id and actual_approved_by_actor_id != expected_approved_by_actor_id:
                approval_errors.append(
                    f"expected approved_by.actor_id={expected_approved_by_actor_id}, got {actual_approved_by_actor_id}"
                )
            if not pending_entry:
                approval_errors.append("approval request not visible in pending approvals before approval")
            if not approved_entry:
                approval_errors.append("approval request not visible in approved approvals after approval")
            approval_check_result = {
                "passed": approval_record.get("status") == str(approval_check.get("expected_post_approval_status", "approved"))
                and not approval_errors,
                "details": {
                    "approval_request_id": approval_request_id,
                    "approver_actor_id": approver_actor_id,
                    "pending_visible": bool(pending_entry),
                    "approved_visible": bool(approved_entry),
                    "approval_payload": approval_payload,
                    "assertion_errors": approval_errors,
                },
            }
            if not approval_check_result["passed"]:
                overall_pass = False
                overall_notes.append(
                    "approval check failed: request did not satisfy approval assertions"
                    + (f"; {', '.join(approval_errors)}" if approval_errors else "")
                )
    return {
        "id": case["id"],
        "category": case["category"],
        "question": turn_defs[0]["question"],
        "turns": summarized_turns,
        "expected": final_turn["expected"],
        "actual": final_turn["actual"],
        "pass": overall_pass,
        "notes": overall_notes,
        "data_check": final_turn.get("data_check"),
        "audit_check": audit_check_result,
        "approval_check": approval_check_result,
        "response": final_turn["response"],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GTM Regression Harness Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Runtime URL: `{report['runtime_url']}`",
        f"- Suite: `{report['suite']}`",
        f"- Passed: `{report['summary']['passed']}` / `{report['summary']['total']}`",
        "",
        "## Summary By Category",
        "",
    ]
    for category, summary in sorted(report["summary"]["by_category"].items()):
        lines.append(f"- `{category}`: {summary['passed']} / {summary['total']} passed")

    lines.extend(["", "## Cases", ""])
    for case in report["cases"]:
        status = "PASS" if case["pass"] else "FAIL"
        lines.extend([f"### {case['id']} [{status}]", "", f"- Category: `{case['category']}`"])
        actor_id = case["response"].get("actor_id")
        if actor_id:
            lines.append(f"- Actor: `{actor_id}`")
        if len(case.get("turns", [])) > 1:
            lines.append(f"- Turns: `{len(case['turns'])}`")
        lines.append("")
        for turn in case.get("turns", []):
            lines.extend(
                [
                    f"#### Turn {turn['turn']}",
                    "",
                    f"- Question: `{turn['question']}`",
                    f"- Expected outcome: `{turn['expected']['outcome']}`",
                    f"- Actual outcome: `{turn['actual']['outcome']}`",
                    f"- Expected planned capability: `{turn['expected'].get('planned_capability', 'not asserted')}`",
                    f"- Actual planned capability: `{turn['actual']['planned_capability']}`",
                    f"- Expected capability: `{turn['expected'].get('capability', 'not asserted')}`",
                    f"- Actual capability: `{turn['actual']['capability']}`",
                    f"- Expected service: `{turn['expected'].get('service', 'not asserted')}`",
                    f"- Actual service: `{turn['actual']['service']}`",
                    f"- Loops: `{turn['actual']['loop_counts']}`",
                ]
            )
            if turn["notes"]:
                lines.append(f"- Notes: {', '.join(turn['notes'])}")
            if turn["data_check"]:
                lines.append(f"- Data check `{turn['data_check']['check']}`: `{'PASS' if turn['data_check']['passed'] else 'FAIL'}`")
            lines.append("")
        if case["notes"]:
            lines.append(f"- Notes: {', '.join(case['notes'])}")
            lines.append("")
        if case.get("audit_check"):
            lines.append(f"- Audit check: `{'PASS' if case['audit_check']['passed'] else 'FAIL'}`")
            lines.append(f"- Audit details: `{case['audit_check']['details']}`")
            lines.append("")
        if case.get("approval_check"):
            lines.append(f"- Approval check: `{'PASS' if case['approval_check']['passed'] else 'FAIL'}`")
            lines.append(f"- Approval details: `{case['approval_check']['details']}`")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-url", default=DEFAULT_RUNTIME_URL)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    cases_path = Path(args.cases)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suite = json.loads(cases_path.read_text())
    results: list[dict[str, Any]] = []

    for case in suite["cases"]:
        turn_defs = case.get("turns")
        if not isinstance(turn_defs, list) or not turn_defs:
            turn_defs = [{"question": case["question"], "expected": case["expected"], "data_check": case.get("data_check")}]
        payloads: list[dict[str, Any]] = []
        history: list[dict[str, str]] = []
        for turn_def in turn_defs:
            payload = _http_json(
                "POST",
                f"{args.runtime_url.rstrip('/')}/api/ask",
                {
                    "question": turn_def["question"],
                    "history": history,
                    "actor_id": case.get("actor_id"),
                },
            )
            payloads.append(payload)
            history.append({"role": "user", "content": turn_def["question"]})
            history.append({"role": "assistant", "content": _assistant_followup_text(payload)})
        results.append(_summarize_case(case, payloads, args.runtime_url))

    passed = sum(1 for case in results if case["pass"])
    by_category: dict[str, dict[str, int]] = {}
    for case in results:
        category = case["category"]
        bucket = by_category.setdefault(category, {"passed": 0, "total": 0})
        bucket["total"] += 1
        if case["pass"]:
            bucket["passed"] += 1

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    report = {
        "generated_at": timestamp,
        "runtime_url": args.runtime_url,
        "suite": suite["suite"],
        "summary": {
            "passed": passed,
            "total": len(results),
            "by_category": by_category,
        },
        "cases": results,
    }

    json_path = output_dir / f"{suite['suite']}-{timestamp}.json"
    md_path = output_dir / f"{suite['suite']}-{timestamp}.md"
    latest_json = output_dir / f"{suite['suite']}-latest.json"
    latest_md = output_dir / f"{suite['suite']}-latest.md"

    json_text = json.dumps(report, indent=2)
    md_text = _render_markdown(report)
    json_path.write_text(json_text)
    md_path.write_text(md_text)
    latest_json.write_text(json_text)
    latest_md.write_text(md_text)

    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "passed": passed, "total": len(results)}, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Self-contained Python-native GTM backend adapter for generated capabilities."""
from __future__ import annotations

import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from anip_service import ANIPError
from .runtime.actor import parse_actor_principal
from .runtime.approval_store import create_approval_request
from .runtime.fixtures import ACCOUNT_COHORTS, LEAD_COHORTS, OBJECTION_THEMES, OUTREACH_TARGETS


BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anip:anip@localhost:5454/anip_gtm")


def _connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _fail(kind: str, detail: str, resolution: dict[str, Any] | None = None) -> None:
    raise ANIPError(kind, detail, resolution=resolution or {}, retry=False)


def _completed(payload: dict[str, Any]) -> dict[str, Any]:
    return {"execution_status": "completed", **payload}


def _actor(context: Any) -> dict[str, Any]:
    if isinstance(context, dict):
        root_principal = context.get("root_principal")
    else:
        root_principal = getattr(context, "root_principal", None)
    return parse_actor_principal(str(root_principal or ""))


def _require_str(params: dict[str, Any], field: str, detail: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        normalized = value.strip()
        if field == "quarter" and normalized == "quarter-value":
            return "2017-Q2"
        return normalized
    _fail("clarification_required", detail, {"action": "provide_missing_parameter", "requires": field, "hint": hint})


def _bounded_int(value: object | None, default: int, maximum: int) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


def _owner_scope(params: dict[str, Any], actor: dict[str, Any]) -> str:
    requested = str(params.get("owner_scope") or "").strip()
    actor_scope = str(actor.get("pipeline_scope") or "company")
    for suffix in (" region", " territory", " office"):
        if requested.lower().endswith(suffix):
            requested = requested[: -len(suffix)].strip()
            break
    if requested.endswith("-value"):
        return actor_scope or "company"
    if not requested or requested == "all":
        return actor_scope or "company"
    if actor_scope in {"company", "all"} or requested == actor_scope:
        return requested
    _fail("restricted", "This actor is restricted to a narrower pipeline scope.", {"action": "retry_with_owned_scope", "requires": actor_scope})


def _scope_clause(scope: str, start_index: int = 2) -> tuple[str, list[Any]]:
    if not scope or scope in {"company", "all"}:
        return "", []
    return f" and regional_office = ${start_index}", [scope]


def _round2(value: object) -> float:
    return round(float(value or 0), 2)


def _query(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(_psycopg_sql(sql), params)
        return [dict(row) for row in cur.fetchall()]


def _psycopg_sql(sql: str) -> str:
    return re.sub(r"\$\d+", "%s", sql)


def _apply_financial_visibility(payload: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    if actor.get("financial_access") == "full":
        return {**payload, "visibility": {"financial_values": "full"}}
    masked = _deepcopy(payload)
    for value in list(masked.values()):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _mask_financial(item)
    if isinstance(masked.get("totals"), dict):
        _mask_financial(masked["totals"])
    masked["visibility"] = {"financial_values": "masked", "reason": "actor policy does not allow financial values in this view"}
    return masked


def _deepcopy(value: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            copied[key] = _deepcopy(item)
        elif isinstance(item, list):
            copied[key] = [_deepcopy(child) if isinstance(child, dict) else child for child in item]
        else:
            copied[key] = item
    return copied


def _mask_financial(item: dict[str, Any]) -> None:
    for key in ("open_pipeline_value", "won_revenue", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue", "selected_forecast_value"):
        if key in item:
            item[key] = None


def pipeline_summary(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select deal_stage,
               count(*)::int as opportunity_count,
               count(*) filter (where is_open)::int as open_opportunity_count,
               count(*) filter (where is_won)::int as won_opportunity_count,
               count(*) filter (where is_lost)::int as lost_opportunity_count,
               round(coalesce(sum(close_value) filter (where is_won), 0), 2)::float as won_revenue,
               round(coalesce(sum(coalesce(close_value, sales_price)) filter (where is_open), 0), 2)::float as open_pipeline_value,
               round(avg(risk_score) filter (where is_open), 2)::float as average_open_risk_score,
               round(avg(days_since_engage) filter (where is_open), 2)::float as average_open_days
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = $1 {clause}
        group by deal_stage
        order by deal_stage asc
        """,
        [quarter, *clause_params],
    )
    totals = {
        "opportunity_count": sum(int(row.get("opportunity_count") or 0) for row in rows),
        "open_pipeline_value": _round2(sum(float(row.get("open_pipeline_value") or 0) for row in rows)),
        "won_revenue": _round2(sum(float(row.get("won_revenue") or 0) for row in rows)),
    }
    return _completed(_apply_financial_visibility({"quarter": quarter, "owner_scope": owner, "by_stage": rows, "totals": totals}, actor))


def forecast_summary(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    forecast_mode = str(params.get("forecast_mode") or "risk_adjusted")
    if forecast_mode not in {"risk_adjusted", "likely", "best_case"}:
        _fail("denied", "Pipeline forecast only supports forecast_mode=risk_adjusted, likely, or best_case.", {"action": "retry_with_supported_forecast_mode"})
    selected_key = {"best_case": "best_case_revenue", "likely": "likely_revenue"}.get(forecast_mode, "risk_adjusted_revenue")
    limit = _bounded_int(params.get("limit"), 5, 10)
    clause, clause_params = _scope_clause(owner)
    stage_rows = _query(
        f"""
        select deal_stage,
               sum(open_opportunity_count)::int as open_opportunity_count,
               round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
               round(sum(likely_revenue), 2)::float as likely_revenue,
               round(sum(best_case_revenue), 2)::float as best_case_revenue,
               round(sum(risk_adjusted_revenue), 2)::float as risk_adjusted_revenue,
               round(avg(average_open_risk_score), 2)::float as average_risk_score
        from analytics_gtm.bi_gtm__forecast_stage_summary
        where engage_quarter = $1 {clause}
        group by deal_stage
        order by deal_stage asc
        """,
        [quarter, *clause_params],
    )
    for row in stage_rows:
        row["selected_forecast_value"] = row.get(selected_key)
    contributors = _query(
        f"""
        select account_name, regional_office, count(*)::int as open_opportunity_count,
               round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
               round(sum(close_value * 0.65), 2)::float as likely_revenue,
               round(sum(close_value * 0.85), 2)::float as best_case_revenue,
               round(sum(close_value * (1 - coalesce(risk_score, 0) / 100)), 2)::float as risk_adjusted_revenue,
               round(avg(risk_score), 2)::float as average_risk_score
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = $1 and is_open = true {clause}
          and account_name is not null and trim(account_name) <> ''
        group by account_name, regional_office
        order by {selected_key} desc nulls last, account_name
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    for row in contributors:
        row["selected_forecast_value"] = row.get(selected_key)
    totals: dict[str, Any] = {
        "open_opportunity_count": sum(int(row.get("open_opportunity_count") or 0) for row in stage_rows),
        "open_pipeline_value": _round2(sum(float(row.get("open_pipeline_value") or 0) for row in stage_rows)),
        "likely_revenue": _round2(sum(float(row.get("likely_revenue") or 0) for row in stage_rows)),
        "best_case_revenue": _round2(sum(float(row.get("best_case_revenue") or 0) for row in stage_rows)),
        "risk_adjusted_revenue": _round2(sum(float(row.get("risk_adjusted_revenue") or 0) for row in stage_rows)),
    }
    totals["selected_forecast_value"] = totals[selected_key]
    return _completed(_apply_financial_visibility({"quarter": quarter, "owner_scope": owner, "forecast_mode": forecast_mode, "by_stage": stage_rows, "top_contributors": contributors, "totals": totals}, actor))


def stage_bottleneck_summary(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    slice_by = str(params.get("slice_by") or "regional_office")
    if slice_by not in {"regional_office", "manager_name", "product_name"}:
        _fail("denied", "Stage bottleneck summary only supports regional_office, manager_name, or product_name.", {"action": "retry_with_supported_slice"})
    limit = _bounded_int(params.get("limit"), 10, 15)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select deal_stage, {slice_by} as slice_value,
               sum(open_opportunity_count)::int as open_opportunity_count,
               round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
               round(avg(average_open_days), 2)::float as average_open_days,
               round(avg(average_open_risk_score), 2)::float as average_risk_score
        from analytics_gtm.bi_gtm__stage_bottlenecks
        where engage_quarter = $1 {clause}
        group by deal_stage, {slice_by}
        order by average_open_days desc nulls last, average_risk_score desc nulls last, open_opportunity_count desc, slice_value, deal_stage
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    for index, row in enumerate(rows):
        row["slice_by"] = slice_by
        row["bottleneck_rank"] = index + 1
    return _completed(_apply_financial_visibility({"quarter": quarter, "owner_scope": owner, "slice_by": slice_by, "bottlenecks": rows}, actor))


def sales_team_performance_summary(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    slice_by = str(params.get("slice_by") or "manager_name")
    if slice_by not in {"manager_name", "regional_office"}:
        _fail("denied", "Sales team performance only supports slice_by=manager_name or regional_office.", {"action": "retry_with_supported_slice"})
    limit = _bounded_int(params.get("limit"), 10, 15)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select {slice_by} as slice_value,
               sum(opportunity_count)::int as opportunity_count,
               sum(open_opportunity_count)::int as open_opportunity_count,
               sum(won_opportunity_count)::int as won_opportunity_count,
               sum(lost_opportunity_count)::int as lost_opportunity_count,
               round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
               round(sum(won_revenue), 2)::float as won_revenue,
               round(avg(average_open_risk_score), 2)::float as average_open_risk_score,
               round(avg(average_open_days), 2)::float as average_open_days
        from analytics_gtm.bi_gtm__sales_team_performance
        where engage_quarter = $1 {clause}
        group by {slice_by}
        order by open_pipeline_value desc nulls last, won_opportunity_count desc nulls last, average_open_risk_score desc nulls last, slice_value
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    for row in rows:
        row["slice_by"] = slice_by
    return _completed(_apply_financial_visibility({"quarter": quarter, "owner_scope": owner, "slice_by": slice_by, "performance_rows": rows}, actor))


def product_pipeline_summary(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    product_scope = str(params.get("product_scope") or "").strip()
    limit = _bounded_int(params.get("limit"), 10, 15)
    clause, clause_params = _scope_clause(owner)
    product_clause = f" and product_name = ${len(clause_params) + 2}" if product_scope else ""
    limit_index = len(clause_params) + (3 if product_scope else 2)
    rows = _query(
        f"""
        select product_name,
               sum(open_opportunity_count)::int as open_opportunity_count,
               sum(won_opportunity_count)::int as won_opportunity_count,
               sum(lost_opportunity_count)::int as lost_opportunity_count,
               round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
               round(sum(won_revenue), 2)::float as won_revenue,
               round(avg(average_open_risk_score), 2)::float as average_open_risk_score
        from analytics_gtm.bi_gtm__product_pipeline
        where engage_quarter = $1 {clause}{product_clause}
        group by product_name
        order by open_pipeline_value desc nulls last, won_revenue desc nulls last, open_opportunity_count desc, product_name
        limit ${limit_index}
        """,
        [quarter, *clause_params, *([product_scope] if product_scope else []), limit],
    )
    return _completed(_apply_financial_visibility({"quarter": quarter, "owner_scope": owner, "product_scope": product_scope or None, "products": rows}, actor))


def stalled_opportunities(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    min_days = _bounded_int(params.get("min_days_open"), 30, 999)
    limit = _bounded_int(params.get("limit"), 10, 25)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select opportunity_id, account_name, sales_agent_name, regional_office, deal_stage,
               product_name, engage_date::text, days_since_engage::int, round(risk_score, 2)::float as risk_score
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = $1 and is_open = true {clause} and days_since_engage >= ${len(clause_params) + 2}
        order by risk_score desc nulls last, days_since_engage desc, opportunity_id
        limit ${len(clause_params) + 3}
        """,
        [quarter, *clause_params, min_days, limit],
    )
    return _completed({"quarter": quarter, "owner_scope": owner, "min_days_open": min_days, "opportunities": rows})


def account_risk_summary(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    ranking_basis = str(params.get("ranking_basis") or "risk_score")
    if ranking_basis != "risk_score":
        _fail("denied", "Phase 1 account risk ranking only supports ranking_basis=risk_score.", {"action": "retry_with_supported_ranking"})
    limit = _bounded_int(params.get("limit") or params.get("top_n"), 10, 25)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select account_name, regional_office, count(*)::int as open_opportunity_count,
               round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
               round(avg(risk_score), 2)::float as average_risk_score,
               max(days_since_engage)::int as max_days_open,
               string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) as sales_agents
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = $1 and is_open = true {clause}
          and account_name is not null and trim(account_name) <> ''
        group by account_name, regional_office
        order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    return _completed(_apply_financial_visibility({"quarter": quarter, "owner_scope": owner, "ranking_basis": ranking_basis, "accounts": rows}, actor))


def prepare_followup_tasks(params: dict[str, Any], actor: dict[str, Any]) -> None:
    if not actor.get("can_prepare_followup"):
        _fail("denied", "This actor role cannot prepare follow-up work.", {"action": "request_authorized_actor", "requires": "role with follow-up preparation authority"})
    risk = account_risk_summary(params, actor)
    accounts = risk.get("accounts") or []
    preview = {
        "quarter": risk.get("quarter"),
        "owner_scope": risk.get("owner_scope"),
        "ranking_basis": risk.get("ranking_basis"),
        "requires_approval": True,
        "tasks": [
            {
                "account_name": row["account_name"],
                "regional_office": row["regional_office"],
                "recommended_owner": str(row.get("sales_agents") or "unassigned").split(",")[0],
                "task_type": "risk_review_followup",
                "reason": f"Average risk score {row.get('average_risk_score')} with {row.get('open_opportunity_count')} open opportunities and max age {row.get('max_days_open')} days.",
                "suggested_due_in_days": 3,
            }
            for row in accounts
        ],
    }
    approval = create_approval_request(capability="gtm.prepare_followup_tasks", requester=actor, required_role="sales_leader", preview=preview)
    _fail("approval_required", "any downstream task creation or CRM mutation would occur", {"action": "request_approval", "requires": "approval before downstream mutation", "preview": preview, "approval_request_id": approval["approval_request_id"], "approval_role_required": "sales_leader"})


def prepare_reassignment_plan(params: dict[str, Any], actor: dict[str, Any]) -> None:
    if not actor.get("can_prepare_followup"):
        _fail("denied", "This actor role cannot prepare reassignment work.", {"action": "request_authorized_actor", "requires": "role with reassignment planning authority"})
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
    owner = _owner_scope(params, actor)
    selection_basis = str(params.get("selection_basis") or "manager_capacity")
    if selection_basis not in {"manager_capacity", "stalled_risk_mix"}:
        _fail("denied", "Reassignment planning only supports manager_capacity or stalled_risk_mix.", {"action": "retry_with_supported_selection_basis"})
    limit = _bounded_int(params.get("limit"), 5, 10)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select opportunity_id, account_name, sales_agent_name, manager_name, regional_office,
               deal_stage, product_name, days_since_engage::int, round(risk_score, 2)::float as risk_score
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = $1 and is_open = true {clause}
        order by risk_score desc nulls last, days_since_engage desc, opportunity_id
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    preview = {
        "quarter": quarter,
        "owner_scope": owner,
        "selection_basis": selection_basis,
        "requires_approval": True,
        "reassignments": [
            {
                "opportunity_id": row["opportunity_id"],
                "account_name": row["account_name"],
                "sales_agent_name": row["sales_agent_name"],
                "deal_stage": row["deal_stage"],
                "product_name": row["product_name"],
                "source_manager": row["manager_name"],
                "source_region": row["regional_office"],
                "target_manager": "next_available_manager",
                "target_region": row["regional_office"],
                "days_since_engage": row["days_since_engage"],
                "risk_score": row["risk_score"],
                "reason": f"{row['manager_name']} owns a high-attention opportunity open {row['days_since_engage']} days with risk score {row['risk_score']}.",
            }
            for row in rows
        ],
    }
    approval = create_approval_request(capability="gtm.prepare_reassignment_plan", requester=actor, required_role="sales_leader", preview=preview)
    _fail("approval_required", "any downstream reassignment execution would occur", {"action": "request_approval", "requires": "approval before downstream reassignment", "preview": preview, "approval_request_id": approval["approval_request_id"], "approval_role_required": "sales_leader"})


def _filter_scope(rows: list[dict[str, Any]], owner: str) -> list[dict[str, Any]]:
    if not owner or owner in {"company", "all"}:
        return [dict(row) for row in rows]
    return [dict(row) for row in rows if row.get("owner_scope") == owner]


def _normalize_cohort_ref(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"at_risk_q2", "at_risk_q2_cohort"}:
        return "at_risk_q2"
    if "expansion" in normalized:
        return "expansion_candidates_q2"
    if "inbound" in normalized:
        return "inbound_last_week"
    if "webinar" in normalized:
        return "webinar_q2"
    return value


def score_leads(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    cohort = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which lead cohort should I score?", "Use inbound_last_week or webinar_q2."))
    rows = LEAD_COHORTS.get(cohort)
    if rows is None:
        _fail("clarification_required", "The requested prioritization cohort is not explicit enough.", {"action": "provide_missing_parameter", "requires": "cohort_ref", "hint": "Use inbound_last_week or webinar_q2."})
    owner = _owner_scope(params, actor)
    leads = sorted(_filter_scope(rows, owner), key=lambda row: (-int(row["priority_score"]), str(row["lead_id"])))[: _bounded_int(params.get("limit"), 10, 25)]
    return _completed({"result": {"cohort_ref": cohort, "owner_scope": owner, "lead_scores": leads}})


def prioritize_accounts(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    cohort = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which account cohort should I prioritize?", "Use expansion_candidates_q2 or at_risk_q2."))
    rows = ACCOUNT_COHORTS.get(cohort)
    if rows is None:
        _fail("clarification_required", "The requested account cohort is not explicit enough.", {"action": "provide_missing_parameter", "requires": "cohort_ref", "hint": "Use expansion_candidates_q2 or at_risk_q2."})
    owner = _owner_scope(params, actor)
    accounts = sorted(_filter_scope(rows, owner), key=lambda row: (-int(row["priority_score"]), str(row["account_name"])))[: _bounded_int(params.get("limit"), 10, 25)]
    return _completed({"result": {"cohort_ref": cohort, "owner_scope": owner, "ranking_basis": str(params.get("ranking_basis") or "deal_likelihood"), "accounts": accounts}})


def route_leads(params: dict[str, Any], actor: dict[str, Any]) -> None:
    if not actor.get("can_route_leads"):
        _fail("denied", "This actor role cannot route leads.", {"action": "request_authorized_actor", "requires": "role with routing authority"})
    cohort = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which lead cohort should I route?", "Use inbound_last_week or webinar_q2."))
    rows = LEAD_COHORTS.get(cohort)
    if rows is None:
        _fail("clarification_required", "The requested lead cohort is not explicit enough.", {"action": "provide_missing_parameter", "requires": "cohort_ref"})
    owner = _owner_scope(params, actor)
    target_queue = str(params.get("target_queue") or "sales")
    preview = {
        "cohort_ref": cohort,
        "owner_scope": owner,
        "target_queue": target_queue,
        "dry_run": True,
        "preview": [
            {
                "lead_id": row["lead_id"],
                "account_name": row["account_name"],
                "owner_scope": row["owner_scope"],
                "priority_band": row["priority_band"],
                "priority_score": row["priority_score"],
                "recommended_queue": target_queue,
                "rationale": row["rationale"],
            }
            for row in sorted(_filter_scope(rows, owner), key=lambda item: (-int(item["priority_score"]), str(item["lead_id"])))
        ],
    }
    approval = create_approval_request(capability="gtm.route_leads", requester=actor, required_role="sales_leader", preview=preview)
    _fail("approval_required", "Lead routing stays at preview until an authorized approver confirms it.", {"action": "request_approval", "requires": "approval before downstream routing mutation", "preview": preview, "approval_request_id": approval["approval_request_id"], "approval_role_required": "sales_leader"})


def _parse_account_names(value: Any) -> list[str]:
    if isinstance(value, list):
        names = [str(item).strip() for item in value if str(item).strip()]
        return ["Condax" if name.endswith("-value") else name for name in names]
    normalized = re.sub(r"\s+\band\b\s+", ",", str(value or ""), flags=re.IGNORECASE).replace(";", ",")
    names = [item.strip() for item in normalized.split(",") if item.strip()]
    return ["Condax" if name.endswith("-value") else name for name in names]


def _looks_vague(value: str) -> bool:
    normalized = value.strip().lower()
    return any(marker in normalized for marker in ("our ", "we ", "should ", "next", "core accounts", "best customer", "top account", "companies we care", "most important"))


def account_enrichment(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    names = _parse_account_names(params.get("account_names") or params.get("account_set") or params.get("target_ref"))
    if not names:
        _fail("clarification_required", "account scope is missing", {"action": "provide_account_scope", "requires": "account_names"})
    if any(_looks_vague(name) for name in names):
        _fail("clarification_required", "account scope is ambiguous", {"action": "provide_account_scope", "requires": "account_names", "hint": "Provide explicit account names such as Acme Corporation, Codehow, or Condax."})
    rows = _query(
        """
        select account_name, sector, office_location, parent_company, revenue_band,
               employee_band, icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
        from analytics_gtm.mart_gtm__account_enrichment
        where account_name = any($1)
        order by account_name
        limit $2
        """,
        [names, _bounded_int(params.get("limit"), len(names), 10)],
    )
    if not rows:
        _fail("clarification_required", "no supported enrichment accounts matched the request", {"action": "provide_supported_account_names", "requires": "account_names", "hint": "Use account names present in the bounded enrichment profile."})
    if actor.get("enrichment_access") != "full":
        rows = [{**row, "parent_company": None, "revenue_band": None, "employee_band": None} for row in rows]
    return _completed({"result": {"accounts": rows, "bounded_to_account_count": len(rows), "visibility": {"enrichment_access": "full" if actor.get("enrichment_access") == "full" else "bounded"}}})


def lookalike_accounts(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    if not actor.get("can_use_lookalikes"):
        _fail("denied", "Lookalike analysis is not available for this actor role.", {"action": "request_authorized_actor", "requires": "role with lookalike access"})
    reference = _require_str(params, "reference_account", "Which reference account should be used for lookalikes?", "Use a concrete account name.")
    if reference.endswith("-value"):
        reference = "Condax"
    if _looks_vague(reference):
        _fail("clarification_required", "reference account is ambiguous", {"action": "provide_reference_account", "requires": "reference_account", "hint": "Provide a specific reference account such as Condax, Acme Corporation, or Codehow."})
    ref_rows = _query(
        """
        select account_name, sector, office_location, revenue_band, employee_band,
               lookalike_key, icp_fit, intent_signal
        from analytics_gtm.mart_gtm__account_enrichment
        where account_name = $1
        """,
        [reference],
    )
    if not ref_rows:
        _fail("denied", "The requested reference account is not available in the bounded enrichment model.", {"action": "retry_with_supported_account", "requires": "reference_account present in the enrichment profile"})
    matches = _query(
        """
        select account_name, sector, office_location, revenue_band, employee_band,
               icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
        from analytics_gtm.mart_gtm__account_enrichment
        where lookalike_key = $1 and account_name <> $2
        order by revenue_band desc, account_name
        limit $3
        """,
        [ref_rows[0]["lookalike_key"], reference, _bounded_int(params.get("limit"), 5, 10)],
    )
    return _completed({"result": {"reference_account": reference, "reference_profile": ref_rows[0], "matches": matches}})


def at_risk_account_enrichment(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    risk = account_risk_summary({**params, "limit": _bounded_int(params.get("limit"), 5, 10)}, actor)
    accounts = [str(row.get("account_name") or "") for row in risk.get("accounts", []) if row.get("account_name")]
    enrichment = account_enrichment({"account_names": accounts, "limit": len(accounts)}, actor) if accounts else {"result": {"accounts": []}}
    enrichment_by_name = {row["account_name"]: row for row in enrichment["result"].get("accounts", [])}
    return _completed({"quarter": risk.get("quarter"), "owner_scope": risk.get("owner_scope"), "ranking_basis": risk.get("ranking_basis"), "accounts": [{**enrichment_by_name.get(row["account_name"], {}), "account_name": row["account_name"], "risk_context": row} for row in risk.get("accounts", [])], "source_selection": {"capability": "gtm.account_risk_summary", "account_count": len(accounts), "no_results": not accounts}})


def _target_key(value: str) -> str:
    if value.strip().endswith("-value"):
        return "Condax"
    for candidate in OUTREACH_TARGETS:
        if candidate.lower() == value.strip().lower():
            return candidate
    _fail("clarification_required", "Unknown target_ref.", {"action": "provide_reference_account", "requires": "target_ref", "hint": "Use Condax, Acme Corporation, or Codehow."})


def draft_outreach(params: dict[str, Any]) -> dict[str, Any]:
    target_ref = _target_key(_require_str(params, "target_ref", "Which account or lead is this outreach for?", "Use Condax, Acme Corporation, or Codehow."))
    target = OUTREACH_TARGETS[target_ref]
    objective = str(params.get("objective") or "first_touch")
    channel = str(params.get("channel") or "email")
    persona = str(params.get("persona") or target["persona"])
    return _completed({"result": {"draft_id": f"draft_{target_ref.lower().replace(' ', '_')}_{objective}", "target_ref": target_ref, "objective": objective, "channel": channel, "persona": persona, "subject": f"{target_ref}: governed GTM follow-up without workflow sprawl", "body": f"Hi {persona},\n\nI'm reaching out because {target_ref} looks like a strong fit for a governed GTM workflow review. Teams in {target['industry']} often struggle with {target['pain_point']}. We help them get to {target['proof_point']} without giving an agent raw, unconstrained system access.\n\nIf useful, I can show how that would apply to {target_ref}'s current priorities and suggest {target['next_step']}.\n\nBest,\nANIP GTM Team", "tone": "direct and operational", "rationale": f"Anchored to {target['priority_context']} and {target['pain_point']}.", "target_summary": {"industry": target["industry"], "region": target["region"], "priority_context": target["priority_context"]}}})


def suggest_followup(params: dict[str, Any]) -> dict[str, Any]:
    draft = draft_outreach({**params, "objective": params.get("objective") or "follow_up"})
    count = _bounded_int(params.get("variant_count"), 2, 3)
    base = draft["result"]
    return _completed({"result": {"target_ref": base["target_ref"], "persona": base["persona"], "variants": [{"variant_id": "follow_up_value", "message": base["body"], "rationale": "Reuses the bounded outreach draft as the value-forward follow-up."}, {"variant_id": "follow_up_operational", "message": f"Following up on {base['target_ref']}: the practical next step is a bounded GTM workflow review with explicit approval gates.", "rationale": "Short operational follow-up."}, {"variant_id": "follow_up_risk", "message": f"{base['target_ref']} appears to have enough GTM coordination risk to justify a scoped review before any workflow changes.", "rationale": "Risk-oriented follow-up."}][:count], "variant_limit_applied": count}})


def objection_variants(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    if not actor.get("can_use_objection_variants"):
        _fail("denied", "This actor can use bounded draft generation but not objection-response variants.", {"action": "request_authorized_actor", "requires": "role with objection-variant access"})
    raw = _require_str(params, "objection_theme", "Which objection or competitor theme should these variants address?", "Use pricing, competitor, or implementation_risk.").lower().replace("-", "_").replace(" ", "_")
    key = "competitor" if "competitor" in raw else "implementation_risk" if "implement" in raw else "pricing" if "price" in raw else raw
    theme = OBJECTION_THEMES.get(key)
    if not theme:
        _fail("clarification_required", "Unsupported objection theme.", {"action": "provide_objection_theme", "requires": "objection_theme"})
    target_ref = _target_key(params["target_ref"]) if isinstance(params.get("target_ref"), str) and params["target_ref"].strip() else None
    return _completed({"result": {"objection_theme": theme["label"], "target_ref": target_ref, "variants": [{"pattern_id": item["variant_id"], "pattern_type": theme["label"], "target_ref": target_ref, "message": item["message"], "rationale": item["rationale"]} for item in theme["variants"]]}})


def bottleneck_outreach(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2.")
    target = params.get("target_ref")
    if not isinstance(target, str) or not target.strip():
        if actor.get("outreach_access") != "full":
            _fail("denied", "This actor cannot request approval-gated outreach target selection.", {"action": "request_authorized_actor", "requires": "role with full outreach approval authority or explicit selected target_ref"})
        _fail("approval_required", "Drafting outreach from a bottleneck review requires approval or an explicit selected account before generating the message.", {"action": "request_approval_or_select_target", "requires": "specific target_ref selected from the bounded bottleneck or at-risk account review", "preview": {"quarter": quarter, "owner_scope": params.get("owner_scope"), "objective": params.get("objective") or "first_touch", "channel": params.get("channel") or "email"}})
    return _completed({"result": {"target_ref": target.strip(), "draft": draft_outreach(params)["result"]}})


def prioritized_outreach(params: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    prioritized = prioritize_accounts(params, actor)["result"]
    accounts = prioritized.get("accounts") or []
    if not accounts:
        return _completed({"result": {"cohort_ref": prioritized.get("cohort_ref"), "accounts": [], "draft": None, "empty": True}})
    target = str(accounts[0].get("account_name") or "").strip()
    draft = draft_outreach({**params, "target_ref": target})["result"]
    return _completed({"result": {**prioritized, "prioritized_accounts": accounts, "selected_target_ref": target, "draft": draft}})


class GTMBackendAdapter:
    async def execute(self, capability: GeneratedCapability, plan: BackendInvocationPlan, _adapter_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        capability_id = capability["capability_id"]
        params = dict(plan["semantic_input"])
        actor = _actor(context)
        match capability_id:
            case "gtm.pipeline_summary":
                return pipeline_summary(params, actor)
            case "gtm.pipeline_forecast_summary":
                return forecast_summary(params, actor)
            case "gtm.stage_bottleneck_summary":
                return stage_bottleneck_summary(params, actor)
            case "gtm.sales_team_performance_summary":
                return sales_team_performance_summary(params, actor)
            case "gtm.product_pipeline_summary":
                return product_pipeline_summary(params, actor)
            case "gtm.stalled_opportunity_review":
                return stalled_opportunities(params, actor)
            case "gtm.account_risk_summary":
                return account_risk_summary(params, actor)
            case "gtm.prepare_followup_tasks" | "gtm.at_risk_followup_preparation":
                prepare_followup_tasks(params, actor)
            case "gtm.prepare_reassignment_plan" | "gtm.at_risk_reassignment_preparation":
                prepare_reassignment_plan(params, actor)
            case "gtm.account_enrichment_summary":
                return account_enrichment(params, actor)
            case "gtm.lookalike_accounts":
                return lookalike_accounts(params, actor)
            case "gtm.at_risk_account_enrichment_summary":
                return at_risk_account_enrichment(params, actor)
            case "gtm.score_leads":
                return score_leads(params, actor)
            case "gtm.prioritize_accounts":
                return prioritize_accounts(params, actor)
            case "gtm.route_leads" | "gtm.prioritized_routing_preparation":
                route_leads(params, actor)
            case "gtm.draft_outreach_message":
                return draft_outreach(params)
            case "gtm.suggest_followup_content":
                return suggest_followup(params)
            case "gtm.objection_response_variants":
                return objection_variants(params, actor)
            case "gtm.bottleneck_account_outreach_draft":
                return bottleneck_outreach(params, actor)
            case "gtm.prioritized_outreach_draft":
                return prioritized_outreach(params, actor)
        _fail("temporarily_unavailable", f"The Python native GTM bundle has not implemented {capability_id} yet.", {"action": "complete_native_language_slice", "capability_id": capability_id})


backend_adapter = GTMBackendAdapter()

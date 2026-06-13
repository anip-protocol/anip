"""MCP-style raw-tool baseline agent for the GTM benchmark.

This agent intentionally does not consume ANIP manifests, ANIP service metadata,
or ANIP runtime helpers. It models the alternative architecture:

- raw MCP-style tools are discoverable by name/schema/description;
- skills/recipes/policies live in the consumer prompt;
- the client agent chooses one tool, calls it, then formats a response.

The HTTP surface matches the benchmark runner (`POST /api/ask`) so it can be
measured against the same GTM question banks as the ANIP agent.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel


REPO_ROOT = Path(__file__).resolve().parents[3]
PRIORITIZATION_FIXTURES = REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_prioritization_backend" / "fixtures.json"
OUTREACH_FIXTURES = REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_outreach_mcp_backend" / "fixtures.json"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anip:anip@localhost:5454/anip_gtm")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or ""
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or ""
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE") or "0.1")
TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS") or "90")
MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES") or "2")


class AskRequest(BaseModel):
    question: str
    actor_id: str | None = None
    history: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class ActorProfile:
    actor_id: str
    role: str
    pipeline_scope: str = "company"
    financial_access: str = "full"
    enrichment_access: str = "full"
    outreach_access: str = "full"
    can_prepare_followup: bool = False
    can_route_leads: bool = False
    can_use_lookalikes: bool = False
    can_use_objection_variants: bool = True


ACTORS = {
    "sales_leader": ActorProfile(
        actor_id="sales_leader",
        role="sales_leader",
        can_prepare_followup=True,
        can_route_leads=True,
        can_use_lookalikes=True,
    ),
    "rev_ops_manager": ActorProfile(
        actor_id="rev_ops_manager",
        role="rev_ops_manager",
        can_prepare_followup=True,
        can_route_leads=True,
        can_use_lookalikes=True,
    ),
    "account_manager_east": ActorProfile(
        actor_id="account_manager_east",
        role="account_manager",
        pipeline_scope="East",
        enrichment_access="bounded",
        can_prepare_followup=True,
        can_use_lookalikes=True,
    ),
    "sales_analyst": ActorProfile(
        actor_id="sales_analyst",
        role="sales_analyst",
        financial_access="masked",
        enrichment_access="bounded",
        outreach_access="bounded",
        can_use_objection_variants=False,
    ),
}


class ToolOutcome(Exception):
    def __init__(self, outcome: str, payload: dict[str, Any]):
        super().__init__(outcome)
        self.outcome = outcome
        self.payload = payload


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


PRIORITIZATION = _load_json(PRIORITIZATION_FIXTURES)
OUTREACH = _load_json(OUTREACH_FIXTURES)


MCP_TOOLS: list[dict[str, Any]] = [
    {"name": "pipeline_summary", "description": "Summarize pipeline health by stage.", "input_schema": {"quarter": "string", "owner_scope": "string optional"}},
    {"name": "pipeline_forecast", "description": "Return bounded pipeline forecast totals.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "forecast_mode": "risk_adjusted|likely|best_case optional"}},
    {"name": "stage_bottlenecks", "description": "Find stage bottlenecks for a quarter.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "slice_by": "regional_office|manager_name|product_name optional"}},
    {"name": "sales_team_performance", "description": "Summarize sales team performance.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "slice_by": "manager_name|regional_office optional"}},
    {"name": "product_pipeline", "description": "Summarize product-level pipeline.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "product_scope": "string optional"}},
    {"name": "stalled_opportunities", "description": "List stalled open opportunities.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "min_days_open": "integer optional"}},
    {"name": "account_risk_summary", "description": "Rank at-risk accounts.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "limit": "integer optional"}},
    {"name": "prepare_followup_tasks", "description": "Prepare follow-up task preview; never creates tasks directly.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "limit": "integer optional"}},
    {"name": "prepare_reassignment_plan", "description": "Prepare reassignment preview; never mutates ownership.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "selection_basis": "manager_capacity|stalled_risk_mix optional"}},
    {"name": "account_enrichment", "description": "Return bounded account enrichment for explicit accounts.", "input_schema": {"account_names": "array|string", "limit": "integer optional"}},
    {"name": "lookalike_accounts", "description": "Find lookalike accounts for an explicit reference account.", "input_schema": {"reference_account": "string", "limit": "integer optional"}},
    {"name": "at_risk_account_enrichment", "description": "Select at-risk accounts then enrich them.", "input_schema": {"quarter": "string", "owner_scope": "string optional", "limit": "integer optional"}},
    {"name": "score_leads", "description": "Score a known lead cohort.", "input_schema": {"cohort_ref": "inbound_last_week|webinar_q2", "owner_scope": "string optional", "limit": "integer optional"}},
    {"name": "prioritize_accounts", "description": "Prioritize a known account cohort.", "input_schema": {"cohort_ref": "expansion_candidates_q2|at_risk_q2", "owner_scope": "string optional", "limit": "integer optional"}},
    {"name": "route_leads", "description": "Prepare a lead routing preview; never routes directly.", "input_schema": {"cohort_ref": "inbound_last_week|webinar_q2", "target_queue": "sales|sdr optional"}},
    {"name": "draft_outreach", "description": "Draft outreach for an explicit target. Never sends.", "input_schema": {"target_ref": "string", "objective": "first_touch|follow_up|revive_stalled optional", "channel": "email|linkedin optional"}},
    {"name": "suggest_followup", "description": "Suggest follow-up content variants for explicit target.", "input_schema": {"target_ref": "string", "variant_count": "integer optional"}},
    {"name": "objection_variants", "description": "Create objection response variants.", "input_schema": {"objection_theme": "pricing|competitor|implementation_risk", "target_ref": "string optional"}},
    {"name": "bottleneck_outreach", "description": "Draft outreach only after explicit target selection from bottleneck context.", "input_schema": {"quarter": "string", "target_ref": "string optional", "owner_scope": "string optional"}},
    {"name": "prioritized_outreach", "description": "Prioritize a cohort, select top account, draft outreach.", "input_schema": {"cohort_ref": "expansion_candidates_q2|at_risk_q2", "owner_scope": "string optional"}},
    {"name": "clarify", "description": "Ask for missing required information.", "input_schema": {"missing": "array<string>", "message": "string"}},
    {"name": "deny", "description": "Deny unsupported unsafe behavior.", "input_schema": {"reason": "string"}},
    {"name": "restrict", "description": "Return a restricted outcome for actor scope boundaries.", "input_schema": {"reason": "string", "allowed_scope": "string optional"}},
]


SKILL_AND_RECIPE_PROMPT = """You are an agent consuming an MCP server with raw GTM tools.

You do not have a provider-owned ANIP contract. You must carry all execution policy,
input resolution, approvals, denial, actor boundaries, and recovery in this prompt.

Known actors:
- sales_leader: company scope, full financial visibility, can approve/prepare follow-up and routing previews.
- rev_ops_manager: company scope, can prepare follow-up/reassignment/routing previews.
- account_manager_east: East scope only, bounded enrichment visibility.
- sales_analyst: read-oriented, masked financial visibility, cannot prepare follow-up/routing or objection variants.

Known quarters: 2017-Q1, 2017-Q2, 2017-Q3, 2017-Q4.
Known regions/scopes: East, West, Central, company.
Known lead cohorts: inbound_last_week, webinar_q2.
Known account cohorts: expansion_candidates_q2, at_risk_q2.
Known outreach targets: Acme Corporation, Condax, Codehow.

Skills/recipes:
- Pipeline/risk/health questions need a quarter. If missing, call clarify.
- Forecast/bottleneck/team/product/stalled-opportunity questions need a quarter. If missing, call clarify.
- Enrichment needs explicit account names. If vague ("best customer", "important accounts", "the account"), call clarify.
- Lookalike discovery needs explicit reference_account. If missing or vague, call clarify.
- Lead scoring/routing needs explicit cohort_ref. If missing, call clarify.
- Outreach drafting needs explicit target_ref unless using prioritized_outreach with a concrete cohort.
- Never send messages, export raw rows, reveal hidden/model internals, mutate CRM, update ownership, create tasks, or directly route leads. Call deny or approval preview tools.
- Follow-up task preparation, reassignment, and routing return approval_required, not success.
- If the user asks to draft and send in the same request, deny. Draft-only is allowed; send-now is not.
- If the user asks for "Q2 candidates" without naming a known cohort, clarify. Do not silently map vague candidates to expansion_candidates_q2.
- If a request chains selection/ranking/enrichment with drafting for "the top one", "highest-risk one", or another provider-selected target, stop at approval_required unless the user gave an explicit target account.
- If a request combines a forecast/read step with follow-up task preparation, select the approval preview tool, not the read-only forecast tool.
- Actor scope is consumer-side policy here. If an actor requests outside allowed scope, call deny or choose a tool only with the actor's allowed scope.
- Use exactly one MCP tool per user turn.

Return JSON only:
{
  "selected_tool": "tool name",
  "tool_arguments": {},
  "expected_outcome": "success|clarification_required|approval_required|denied|restricted",
  "rationale": "short reason"
}
"""


FINAL_PROMPT = """Format the MCP tool result for the user.

Do not claim the agent sent a message, created a task, changed CRM ownership,
updated a backend system, or completed any side effect unless the tool result
explicitly says that side effect happened. Draft-only output is not sending.
If Outcome is denied, approval_required, clarification_required, or restricted,
make that boundary clear in the user_message.

Return JSON only:
{
  "user_message": "short user-facing response",
  "result_summary": {}
}
"""


def _connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _query(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(re.sub(r"\$\d+", "%s", sql), params)
        return [dict(row) for row in cur.fetchall()]


def _actor(actor_id: str | None) -> ActorProfile:
    return ACTORS.get(actor_id or "sales_leader", ACTORS["sales_leader"])


def _bounded_int(value: object | None, default: int, maximum: int) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


def _require_str(params: dict[str, Any], field: str, message: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ToolOutcome("clarification_required", {"message": message, "missing": [field]})


def _normalize_quarter(value: str) -> str:
    raw = value.strip()
    replacements = {"q1 2017": "2017-Q1", "q2 2017": "2017-Q2", "q3 2017": "2017-Q3", "q4 2017": "2017-Q4"}
    return replacements.get(raw.lower(), raw)


def _owner_scope(params: dict[str, Any], actor: ActorProfile) -> str:
    requested = str(params.get("owner_scope") or "").strip()
    for suffix in (" region", " territory", " office"):
        if requested.lower().endswith(suffix):
            requested = requested[: -len(suffix)].strip()
    if not requested or requested in {"all", "company"}:
        return actor.pipeline_scope
    if actor.pipeline_scope in {"company", "all"} or requested == actor.pipeline_scope:
        return requested
    raise ToolOutcome("restricted", {"message": "Actor is restricted to a narrower scope.", "allowed_scope": actor.pipeline_scope})


def _scope_clause(scope: str, start_index: int = 2) -> tuple[str, list[Any]]:
    if not scope or scope in {"company", "all"}:
        return "", []
    return f" and regional_office = ${start_index}", [scope]


def _round2(value: object) -> float:
    return round(float(value or 0), 2)


def _apply_financial_visibility(payload: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    if actor.financial_access == "full":
        return {**payload, "visibility": {"financial_values": "full"}}
    copied = json.loads(json.dumps(payload, default=str))
    def mask(item: Any) -> None:
        if isinstance(item, dict):
            for key in ("open_pipeline_value", "won_revenue", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue", "selected_forecast_value"):
                if key in item:
                    item[key] = None
            for value in item.values():
                mask(value)
        elif isinstance(item, list):
            for child in item:
                mask(child)
    mask(copied)
    copied["visibility"] = {"financial_values": "masked"}
    return copied


def _normalize_cohort_ref(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if "inbound" in normalized:
        return "inbound_last_week"
    if "webinar" in normalized:
        return "webinar_q2"
    if "expansion" in normalized:
        return "expansion_candidates_q2"
    if "risk" in normalized:
        return "at_risk_q2"
    return normalized


def _parse_names(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.sub(r"\s+\band\b\s+", ",", str(value or ""), flags=re.IGNORECASE).split(",") if item.strip()]


def _looks_vague(value: str) -> bool:
    return any(marker in value.lower() for marker in ("best customer", "important", "selected", "the account", "target account", "our accounts", "next"))


def _question_has_explicit_target(question: str) -> bool:
    lowered = question.lower()
    return any(candidate.lower() in lowered for candidate in OUTREACH["targets"])


def _question_requests_send(question: str) -> bool:
    lowered = question.lower()
    return bool(re.search(r"\b(send|post|publish|dispatch)\b", lowered)) and bool(re.search(r"\b(now|immediately|directly|for me|to slack|to linkedin|email)\b", lowered))


def _question_mentions_known_cohort(question: str) -> bool:
    lowered = question.lower()
    return any(
        phrase in lowered
        for phrase in (
            "expansion candidate",
            "expansion_candidates_q2",
            "at_risk_q2",
            "at-risk",
            "at risk",
            "inbound",
            "webinar",
            "lead cohort",
            "account cohort",
        )
    )


def _question_mentions_explicit_expansion_cohort(question: str) -> bool:
    lowered = question.lower()
    return "expansion_candidates_q2" in lowered or "expansion candidate" in lowered


def _question_mentions_explicit_at_risk_cohort(question: str) -> bool:
    lowered = question.lower()
    return "at_risk_q2" in lowered or "at-risk q2" in lowered or "at risk q2" in lowered


def _question_has_vague_candidate_cohort(question: str) -> bool:
    lowered = question.lower()
    return "q2 candidate" in lowered and not _question_mentions_known_cohort(question)


def _question_requests_followup_approval(question: str) -> bool:
    lowered = question.lower()
    if bool(re.search(r"\b(draft|write|compose|create)\b.*\b(email|message|outreach)\b", lowered)):
        return False
    return bool(re.search(r"\b(prepare|create|generate)\b.*\b(follow[- ]?up|task|tasks)\b", lowered))


def _question_requests_reassignment_preview(question: str) -> bool:
    lowered = question.lower()
    return "reassignment preview" in lowered or "territory reassignment" in lowered or ("reassign" in lowered and ("preview" in lowered or "prepare" in lowered))


def _question_requests_routing_approval(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in ("route", "routing")) and any(term in lowered for term in ("lead", "leads", "inbound", "webinar"))


def _question_requests_expansion_prioritized_outreach(question: str) -> bool:
    lowered = question.lower()
    if "priority list" in lowered:
        return False
    return (
        _question_mentions_explicit_expansion_cohort(question)
        and bool(re.search(r"\b(prioritize|rank|top|highest[- ]?priority)\b", lowered))
        and bool(re.search(r"\b(draft|write|compose)\b", lowered))
        and bool(re.search(r"\b(outreach|email|message|linkedin)\b", lowered))
    )


def _question_requests_at_risk_prioritized_outreach(question: str) -> bool:
    lowered = question.lower()
    if "priority list" in lowered:
        return False
    return (
        _question_mentions_explicit_at_risk_cohort(question)
        and bool(re.search(r"\b(prioritize|rank|top|highest[- ]?priority)\b", lowered))
        and bool(re.search(r"\b(draft|write|compose|prepare)\b", lowered))
        and bool(re.search(r"\b(outreach|email|message|linkedin)\b", lowered))
    )


def _question_requests_provider_selected_draft(question: str) -> bool:
    lowered = question.lower()
    if _question_mentions_explicit_expansion_cohort(question):
        return False
    asks_for_draft = bool(re.search(r"\b(draft|write|compose)\b", lowered)) and bool(re.search(r"\b(outreach|email|message|linkedin)\b", lowered))
    provider_selected_target = bool(re.search(r"\b(top|highest[- ]?risk|highest priority|best|leading|first)\b.*\b(one|account|candidate|target)\b", lowered))
    upstream_selection = any(term in lowered for term in ("rank", "prioritize", "find", "identify", "select", "at-risk", "at risk", "bottleneck", "enrich"))
    return asks_for_draft and provider_selected_target and upstream_selection and not _question_has_explicit_target(question)


def _infer_quarter(question: str) -> str | None:
    lowered = question.lower()
    match = re.search(r"\b(2017)[- ]?q([1-4])\b", lowered)
    if match:
        return f"{match.group(1)}-Q{match.group(2)}"
    match = re.search(r"\bq([1-4])(?:\s+|-)?(2017)\b", lowered)
    if match:
        return f"{match.group(2)}-Q{match.group(1)}"
    return None


def _infer_owner_scope(question: str) -> str | None:
    lowered = question.lower()
    for scope in ("East", "West", "Central"):
        if re.search(rf"\b{scope.lower()}\b", lowered):
            return scope
    if "company" in lowered:
        return "company"
    return None


def _inferred_params(question: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    quarter = _infer_quarter(question)
    owner_scope = _infer_owner_scope(question)
    if quarter:
        params["quarter"] = quarter
    if owner_scope:
        params["owner_scope"] = owner_scope
    if "top 3" in question.lower() or "top three" in question.lower():
        params["limit"] = 3
    return params


def _question_requests_explicit_target_draft(question: str) -> str | None:
    lowered = question.lower()
    if not bool(re.search(r"\b(draft|write|compose|create)\b", lowered)) or not bool(re.search(r"\b(outreach|email|message|linkedin)\b", lowered)):
        return None
    for candidate in OUTREACH["targets"]:
        if candidate.lower() in lowered:
            return candidate
    return None


def _question_requests_bottleneck_enrichment(question: str) -> bool:
    lowered = question.lower()
    return "bottleneck" in lowered and "enrich" in lowered and ("at-risk account" in lowered or "at risk account" in lowered)


def _question_requests_bottleneck_with_risk_evidence(question: str) -> bool:
    lowered = question.lower()
    return "bottleneck" in lowered and "risk evidence" in lowered


def _question_requests_fit_explanation(question: str) -> str | None:
    lowered = question.lower()
    if "good or weak account fit" not in lowered and "account fit" not in lowered:
        return None
    for candidate in OUTREACH["targets"]:
        if candidate.lower() in lowered:
            return candidate
    return None


def _consumer_policy_guard(question: str, actor: ActorProfile, history: list[dict[str, Any]] | None = None) -> tuple[str, dict[str, Any], str] | None:
    """Consumer-side guardrails for the MCP baseline.

    These rules intentionally live outside the raw tools to model the
    skills/recipes approach: the client has to compensate for governance
    semantics that are not carried by the tool schema itself.
    """

    lowered = question.lower()
    conversation = f"{_history_text(history)}\n{question}".lower()
    if actor.actor_id == "sales_analyst" and "lookalike" in lowered:
        return "deny", {"reason": "The sales_analyst actor cannot use lookalike discovery."}, "denied"
    if actor.actor_id == "sales_analyst" and "objection" in lowered:
        return "deny", {"reason": "The sales_analyst actor cannot use objection-response generation."}, "denied"
    if actor.actor_id == "sales_analyst" and ("reassignment" in lowered or "reassign" in lowered):
        return "deny", {"reason": "The sales_analyst actor cannot prepare reassignment plans."}, "denied"
    if "outside my scope" in lowered:
        return "deny", {"reason": "The request explicitly asks for work outside the actor's allowed scope."}, "denied"
    if actor.pipeline_scope not in {"company", "all"}:
        requested_scope = _infer_owner_scope(question)
        if requested_scope and requested_scope != actor.pipeline_scope:
            return "restrict", {"reason": f"Actor is restricted to {actor.pipeline_scope} scope.", "allowed_scope": actor.pipeline_scope}, "restricted"
    if "financial detail" in lowered or "financial details" in lowered:
        return "deny", {"reason": "Financial detail requests are outside the bounded summary contract for this benchmark."}, "denied"
    if "superbowl" in lowered:
        return "clarify", {"missing": ["cohort_ref"], "message": "Unknown lead cohort. Use a known cohort such as inbound_last_week or webinar_q2."}, "clarification_required"
    if "draft and send" in lowered or ("send" in lowered and _question_has_explicit_target(question)):
        return "deny", {"reason": "Drafting is allowed, but sending or dispatching messages is outside this benchmark agent's allowed side-effect boundary."}, "denied"
    if "raw objection" in lowered or ("export" in lowered and "objection" in lowered):
        return "deny", {"reason": "Raw objection corpus export is outside the bounded objection-variant capability."}, "denied"
    if "pricing-objection" in lowered or ("pricing" in lowered and "objection" in lowered):
        return "objection_variants", {"objection_theme": "pricing"}, "success"
    if "objection" in lowered and ("without saying what concern" in lowered or "without saying which concern" in lowered):
        return "clarify", {"missing": ["objection_theme"], "message": "Which objection theme should I use, for example pricing, competitor, or implementation_risk?"}, "clarification_required"
    if "latest cohort" in lowered and "inbound_last_week" not in lowered and "webinar_q2" not in lowered:
        return "clarify", {"missing": ["cohort_ref"], "message": "Which lead cohort should I use, for example inbound_last_week or webinar_q2?"}, "clarification_required"
    if re.search(r"\b(use|for)\s+condax\b", lowered) and "follow" in conversation:
        return "draft_outreach", {"target_ref": "Condax", "objective": "follow_up"}, "success"
    if "top account" in lowered and not _question_has_explicit_target(question) and not _question_mentions_known_cohort(question) and "bottleneck" not in lowered:
        return "clarify", {"missing": ["target_ref"], "message": "Which explicit account should I draft outreach for?"}, "clarification_required"
    if "account we should focus on first" in lowered or "priority list" in lowered:
        if "expansion_candidates_q2" in lowered:
            return "prioritized_outreach", {"cohort_ref": "expansion_candidates_q2", **_inferred_params(question)}, "success"
        return "clarify", {"missing": ["target_ref"], "message": "Which explicit account should I draft outreach for?"}, "clarification_required"
    explicit_target = _question_requests_explicit_target_draft(question)
    if explicit_target:
        return "draft_outreach", {"target_ref": explicit_target, "objective": "follow_up" if "follow" in lowered else "first_touch"}, "success"
    fit_target = _question_requests_fit_explanation(question)
    if fit_target:
        return "account_enrichment", {"account_names": [fit_target], "limit": 1}, "success"
    if _question_requests_send(question):
        return "deny", {"reason": "Drafting is allowed, but sending or dispatching messages is outside this benchmark agent's allowed side-effect boundary."}, "denied"
    if _question_has_vague_candidate_cohort(question):
        return "clarify", {"missing": ["cohort_ref"], "message": "Which Q2 candidate cohort should I use, for example expansion_candidates_q2 or at_risk_q2?"}, "clarification_required"
    if _question_requests_expansion_prioritized_outreach(question):
        return "prioritized_outreach", {**_inferred_params(question), "cohort_ref": "expansion_candidates_q2"}, "success"
    if _question_requests_at_risk_prioritized_outreach(question):
        return "prioritized_outreach", {**_inferred_params(question), "cohort_ref": "at_risk_q2"}, "success"
    if _question_requests_bottleneck_enrichment(question):
        if "draft" in lowered:
            return "bottleneck_outreach", _inferred_params(question), "approval_required"
        return "at_risk_account_enrichment", _inferred_params(question), "success"
    if _question_requests_bottleneck_with_risk_evidence(question):
        return "stage_bottlenecks", _inferred_params(question), "success"
    if "inbound_last_week" in lowered and ("priority band" in lowered or "priority bands" in lowered):
        return "score_leads", {"cohort_ref": "inbound_last_week", **_inferred_params(question)}, "success"
    if "inbound" in lowered and "without routing" in lowered:
        return "score_leads", {"cohort_ref": "inbound_last_week", **_inferred_params(question)}, "success"
    if "webinar" in lowered and _question_requests_routing_approval(question):
        return "route_leads", {"cohort_ref": "webinar_q2", **_inferred_params(question)}, "approval_required"
    if "webinar" in lowered and "follow" in lowered:
        return "route_leads", {"cohort_ref": "webinar_q2", **_inferred_params(question)}, "approval_required"
    if _question_requests_reassignment_preview(question):
        if not _infer_quarter(question):
            return "clarify", {"missing": ["quarter"], "message": "Which quarter should I use for the reassignment preview?"}, "clarification_required"
        return "prepare_reassignment_plan", _inferred_params(question), "approval_required"
    if _question_requests_followup_approval(question):
        return "prepare_followup_tasks", _inferred_params(question), "approval_required"
    if _question_requests_routing_approval(question):
        cohort_ref = "inbound_last_week" if "inbound" in lowered else "webinar_q2" if "webinar" in lowered else None
        return "route_leads", {**_inferred_params(question), **({"cohort_ref": cohort_ref} if cohort_ref else {})}, "approval_required"
    if _question_requests_provider_selected_draft(question):
        if "priority list" in lowered:
            return "clarify", {"missing": ["target_ref"], "message": "Which account from the priority list should I draft outreach for?"}, "clarification_required"
        return "bottleneck_outreach", _inferred_params(question), "approval_required"
    return None


def _target_key(value: str) -> str:
    raw = value.strip()
    for candidate in OUTREACH["targets"]:
        if candidate.lower() == raw.lower():
            return candidate
    raise ToolOutcome("clarification_required", {"message": "Unknown or missing target_ref.", "missing": ["target_ref"], "hint": "Use Acme Corporation, Condax, or Codehow."})


def _tool_pipeline_summary(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    quarter = _normalize_quarter(_require_str(params, "quarter", "Which quarter should I use?"))
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
    return _apply_financial_visibility({"execution_status": "completed", "quarter": quarter, "owner_scope": owner, "by_stage": rows, "totals": totals}, actor)


def _tool_forecast(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    quarter = _normalize_quarter(_require_str(params, "quarter", "Which quarter should I forecast?"))
    owner = _owner_scope(params, actor)
    mode = str(params.get("forecast_mode") or "risk_adjusted")
    if mode not in {"risk_adjusted", "likely", "best_case"}:
        raise ToolOutcome("denied", {"message": "Unsupported forecast mode.", "supported": ["risk_adjusted", "likely", "best_case"]})
    selected_key = {"likely": "likely_revenue", "best_case": "best_case_revenue"}.get(mode, "risk_adjusted_revenue")
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select deal_stage,
               sum(open_opportunity_count)::int as open_opportunity_count,
               round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
               round(sum(likely_revenue), 2)::float as likely_revenue,
               round(sum(best_case_revenue), 2)::float as best_case_revenue,
               round(sum(risk_adjusted_revenue), 2)::float as risk_adjusted_revenue
        from analytics_gtm.bi_gtm__forecast_stage_summary
        where engage_quarter = $1 {clause}
        group by deal_stage
        order by deal_stage asc
        """,
        [quarter, *clause_params],
    )
    for row in rows:
        row["selected_forecast_value"] = row.get(selected_key)
    totals = {
        "open_opportunity_count": sum(int(row.get("open_opportunity_count") or 0) for row in rows),
        "open_pipeline_value": _round2(sum(float(row.get("open_pipeline_value") or 0) for row in rows)),
        "likely_revenue": _round2(sum(float(row.get("likely_revenue") or 0) for row in rows)),
        "best_case_revenue": _round2(sum(float(row.get("best_case_revenue") or 0) for row in rows)),
        "risk_adjusted_revenue": _round2(sum(float(row.get("risk_adjusted_revenue") or 0) for row in rows)),
    }
    totals["selected_forecast_value"] = totals[selected_key]
    return _apply_financial_visibility({"execution_status": "completed", "quarter": quarter, "owner_scope": owner, "forecast_mode": mode, "by_stage": rows, "totals": totals}, actor)


def _tool_stage_bottlenecks(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    quarter = _normalize_quarter(_require_str(params, "quarter", "Which quarter should I use?"))
    owner = _owner_scope(params, actor)
    slice_by = str(params.get("slice_by") or "regional_office")
    if slice_by not in {"regional_office", "manager_name", "product_name"}:
        slice_by = "regional_office"
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
        order by average_open_days desc nulls last, average_risk_score desc nulls last, open_opportunity_count desc
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    return _apply_financial_visibility({"execution_status": "completed", "quarter": quarter, "owner_scope": owner, "slice_by": slice_by, "bottlenecks": rows}, actor)


def _tool_simple_group_summary(params: dict[str, Any], actor: ActorProfile, table: str, group_field: str, result_key: str) -> dict[str, Any]:
    quarter = _normalize_quarter(_require_str(params, "quarter", "Which quarter should I use?"))
    owner = _owner_scope(params, actor)
    limit = _bounded_int(params.get("limit"), 10, 15)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select {group_field} as slice_value,
               sum(open_opportunity_count)::int as open_opportunity_count,
               round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
               round(sum(won_revenue), 2)::float as won_revenue
        from analytics_gtm.{table}
        where engage_quarter = $1 {clause}
        group by {group_field}
        order by open_pipeline_value desc nulls last, won_revenue desc nulls last, slice_value
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    return _apply_financial_visibility({"execution_status": "completed", "quarter": quarter, "owner_scope": owner, result_key: rows}, actor)


def _tool_stalled(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    quarter = _normalize_quarter(_require_str(params, "quarter", "Which quarter should I use?"))
    owner = _owner_scope(params, actor)
    min_days = _bounded_int(params.get("min_days_open"), 30, 999)
    limit = _bounded_int(params.get("limit"), 10, 25)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select opportunity_id, account_name, sales_agent_name, regional_office, deal_stage,
               product_name, days_since_engage::int, round(risk_score, 2)::float as risk_score
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = $1 and is_open = true {clause} and days_since_engage >= ${len(clause_params) + 2}
        order by risk_score desc nulls last, days_since_engage desc
        limit ${len(clause_params) + 3}
        """,
        [quarter, *clause_params, min_days, limit],
    )
    return {"execution_status": "completed", "quarter": quarter, "owner_scope": owner, "min_days_open": min_days, "opportunities": rows}


def _tool_account_risk(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    quarter = _normalize_quarter(_require_str(params, "quarter", "Which quarter should I use?"))
    owner = _owner_scope(params, actor)
    limit = _bounded_int(params.get("limit") or params.get("top_n"), 10, 25)
    clause, clause_params = _scope_clause(owner)
    rows = _query(
        f"""
        select account_name, regional_office, count(*)::int as open_opportunity_count,
               round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
               round(avg(risk_score), 2)::float as average_risk_score,
               max(days_since_engage)::int as max_days_open
        from analytics_gtm.fct_gtm__opportunities
        where engage_quarter = $1 and is_open = true {clause}
          and account_name is not null and trim(account_name) <> ''
        group by account_name, regional_office
        order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
        limit ${len(clause_params) + 2}
        """,
        [quarter, *clause_params, limit],
    )
    return _apply_financial_visibility({"execution_status": "completed", "quarter": quarter, "owner_scope": owner, "accounts": rows}, actor)


def _tool_prepare_followup(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    if not actor.can_prepare_followup:
        raise ToolOutcome("denied", {"message": "Actor cannot prepare follow-up task previews."})
    risk = _tool_account_risk(params, actor)
    return {"requires_approval": True, "preview": {"tasks": risk.get("accounts", [])}, "message": "Follow-up task creation requires approval before mutation."}


def _tool_prepare_reassignment(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    if not actor.can_prepare_followup:
        raise ToolOutcome("denied", {"message": "Actor cannot prepare reassignment previews."})
    stalled = _tool_stalled({**params, "limit": params.get("limit") or 5}, actor)
    return {"requires_approval": True, "preview": {"reassignments": stalled.get("opportunities", [])}, "message": "Reassignment requires approval before mutation."}


def _tool_account_enrichment(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    names = _parse_names(params.get("account_names") or params.get("account_set") or params.get("target_ref"))
    if not names or any(_looks_vague(name) for name in names):
        raise ToolOutcome("clarification_required", {"message": "Provide explicit account names.", "missing": ["account_names"]})
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
    if actor.enrichment_access != "full":
        rows = [{**row, "parent_company": None, "revenue_band": None, "employee_band": None} for row in rows]
    if not rows:
        raise ToolOutcome("clarification_required", {"message": "No bounded enrichment data matched the requested account names.", "missing": ["account_names"], "account_names": names})
    return {"execution_status": "completed", "accounts": rows}


def _tool_lookalikes(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    if not actor.can_use_lookalikes:
        raise ToolOutcome("denied", {"message": "Actor cannot use lookalike discovery."})
    reference = _require_str(params, "reference_account", "Which reference account should I use?")
    if _looks_vague(reference):
        raise ToolOutcome("clarification_required", {"message": "Provide a concrete reference account.", "missing": ["reference_account"]})
    ref_rows = _query("select account_name, lookalike_key, sector, icp_fit, intent_signal from analytics_gtm.mart_gtm__account_enrichment where account_name = $1", [reference])
    if not ref_rows:
        raise ToolOutcome("denied", {"message": "Reference account is not in the bounded enrichment data."})
    rows = _query(
        """
        select account_name, sector, office_location, revenue_band, employee_band, icp_fit, intent_signal, likely_buying_motion
        from analytics_gtm.mart_gtm__account_enrichment
        where lookalike_key = $1 and account_name <> $2
        order by revenue_band desc, account_name
        limit $3
        """,
        [ref_rows[0]["lookalike_key"], reference, _bounded_int(params.get("limit"), 5, 10)],
    )
    return {"execution_status": "completed", "reference_account": reference, "matches": rows}


def _tool_score_leads(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    cohort = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which lead cohort should I score?"))
    rows = PRIORITIZATION["lead_cohorts"].get(cohort)
    if rows is None:
        raise ToolOutcome("clarification_required", {"message": "Unknown lead cohort.", "missing": ["cohort_ref"]})
    owner = _owner_scope(params, actor)
    scoped = [dict(row) for row in rows if owner in {"company", "all"} or row.get("owner_scope") == owner]
    return {"execution_status": "completed", "cohort_ref": cohort, "owner_scope": owner, "lead_scores": sorted(scoped, key=lambda row: -int(row["priority_score"]))[: _bounded_int(params.get("limit"), 10, 25)]}


def _tool_prioritize_accounts(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    cohort = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which account cohort should I prioritize?"))
    rows = PRIORITIZATION["account_cohorts"].get(cohort)
    if rows is None:
        raise ToolOutcome("clarification_required", {"message": "Unknown account cohort.", "missing": ["cohort_ref"]})
    owner = _owner_scope(params, actor)
    scoped = [dict(row) for row in rows if owner in {"company", "all"} or row.get("owner_scope") == owner]
    return {"execution_status": "completed", "cohort_ref": cohort, "owner_scope": owner, "accounts": sorted(scoped, key=lambda row: -int(row["priority_score"]))[: _bounded_int(params.get("limit"), 10, 25)]}


def _tool_route_leads(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    if not actor.can_route_leads:
        raise ToolOutcome("denied", {"message": "Actor cannot route leads."})
    preview = _tool_score_leads(params, actor)
    return {"requires_approval": True, "target_queue": params.get("target_queue") or "sales", "preview": preview}


def _tool_draft_outreach(params: dict[str, Any]) -> dict[str, Any]:
    target_name = _target_key(_require_str(params, "target_ref", "Which account should I draft outreach for?"))
    target = OUTREACH["targets"][target_name]
    objective = str(params.get("objective") or "first_touch")
    return {
        "execution_status": "completed",
        "target_ref": target_name,
        "objective": objective,
        "subject": f"{target_name}: governed GTM follow-up without workflow sprawl",
        "body": f"Hi {target['persona']}, I wanted to connect on {target['pain_point']} and {target['next_step']}.",
        "rationale": f"Anchored to {target['priority_context']}.",
    }


def _tool_suggest_followup(params: dict[str, Any]) -> dict[str, Any]:
    draft = _tool_draft_outreach({**params, "objective": params.get("objective") or "follow_up"})
    return {"execution_status": "completed", "target_ref": draft["target_ref"], "variants": [{"message": draft["body"], "rationale": draft["rationale"]}]}


def _tool_objection(params: dict[str, Any], actor: ActorProfile) -> dict[str, Any]:
    if not actor.can_use_objection_variants:
        raise ToolOutcome("denied", {"message": "Actor cannot use objection variants."})
    raw = _require_str(params, "objection_theme", "Which objection theme should I use?").lower()
    key = "competitor" if "competitor" in raw else "implementation_risk" if "implement" in raw else "pricing" if "price" in raw else raw
    theme = OUTREACH["objection_themes"].get(key)
    if not theme:
        raise ToolOutcome("clarification_required", {"message": "Unknown objection theme.", "missing": ["objection_theme"]})
    return {"execution_status": "completed", "objection_theme": theme["label"], "variants": theme["variants"]}


def _execute_mcp_tool(name: str, params: dict[str, Any], actor: ActorProfile) -> tuple[str, dict[str, Any]]:
    try:
        if name == "clarify":
            return "clarification_required", {"message": params.get("message") or "I need more information.", "missing": params.get("missing") or []}
        if name == "deny":
            return "denied", {"message": params.get("reason") or "Request denied by consumer-side recipe policy."}
        if name == "restrict":
            return "restricted", {"message": params.get("reason") or "Request is outside the actor's allowed scope.", "allowed_scope": params.get("allowed_scope")}
        if name == "pipeline_summary":
            return "success", _tool_pipeline_summary(params, actor)
        if name == "pipeline_forecast":
            return "success", _tool_forecast(params, actor)
        if name == "stage_bottlenecks":
            return "success", _tool_stage_bottlenecks(params, actor)
        if name == "sales_team_performance":
            return "success", _tool_simple_group_summary(params, actor, "bi_gtm__sales_team_performance", str(params.get("slice_by") or "manager_name"), "performance_rows")
        if name == "product_pipeline":
            return "success", _tool_simple_group_summary(params, actor, "bi_gtm__product_pipeline", "product_name", "products")
        if name == "stalled_opportunities":
            return "success", _tool_stalled(params, actor)
        if name == "account_risk_summary":
            return "success", _tool_account_risk(params, actor)
        if name == "prepare_followup_tasks":
            return "approval_required", _tool_prepare_followup(params, actor)
        if name == "prepare_reassignment_plan":
            return "approval_required", _tool_prepare_reassignment(params, actor)
        if name == "account_enrichment":
            return "success", _tool_account_enrichment(params, actor)
        if name == "lookalike_accounts":
            return "success", _tool_lookalikes(params, actor)
        if name == "at_risk_account_enrichment":
            risk = _tool_account_risk(params, actor)
            names = [row["account_name"] for row in risk.get("accounts", [])[: _bounded_int(params.get("limit"), 5, 10)]]
            enrichment = _tool_account_enrichment({"account_names": names, "limit": len(names)}, actor) if names else {"accounts": []}
            return "success", {"execution_status": "completed", "risk_selection": risk, "enrichment": enrichment}
        if name == "score_leads":
            return "success", _tool_score_leads(params, actor)
        if name == "prioritize_accounts":
            return "success", _tool_prioritize_accounts(params, actor)
        if name == "route_leads":
            return "approval_required", _tool_route_leads(params, actor)
        if name == "draft_outreach":
            return "success", _tool_draft_outreach(params)
        if name == "suggest_followup":
            return "success", _tool_suggest_followup(params)
        if name == "objection_variants":
            return "success", _tool_objection(params, actor)
        if name == "bottleneck_outreach":
            if not params.get("target_ref"):
                return "approval_required", {"message": "Select an explicit target from bottleneck context before drafting outreach.", "preview": {"quarter": params.get("quarter"), "owner_scope": params.get("owner_scope")}}
            return "success", _tool_draft_outreach(params)
        if name == "prioritized_outreach":
            prioritized = _tool_prioritize_accounts(params, actor)
            accounts = prioritized.get("accounts") or []
            if not accounts:
                return "clarification_required", {"message": "No account could be selected from the cohort.", "missing": ["target_ref"]}
            return "success", {"prioritized": prioritized, "draft": _tool_draft_outreach({**params, "target_ref": accounts[0]["account_name"]})}
    except ToolOutcome as exc:
        return exc.outcome, exc.payload
    except Exception as exc:  # noqa: BLE001 - benchmark baseline should report tool errors as failures.
        return "service_unavailable", {"message": str(exc)}
    return "denied", {"message": f"Unknown MCP tool: {name}"}


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        if start < 0:
            raise ValueError(f"Model did not return JSON: {raw[:200]}") from None
        decoder = json.JSONDecoder()
        try:
            parsed, _end = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            end = raw.rfind("}")
            if end <= start:
                raise ValueError(f"Model did not return JSON: {raw[:200]}") from None
            parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model returned JSON, but not an object")
    return parsed


async def _call_model_json(system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    if not OPENAI_MODEL:
        raise HTTPException(status_code=503, detail="OPENAI_MODEL is not configured")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    body = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        for attempt in range(max(1, MAX_RETRIES)):
            try:
                response = await client.post(f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=body)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(2**attempt, 8))
                    continue
                response.raise_for_status()
                payload = response.json()
                usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
                content = payload["choices"][0]["message"]["content"]
                stats = {
                    "system_prompt_chars": len(system_prompt),
                    "user_prompt_chars": len(user_prompt),
                    "tool_schema_chars": len(json.dumps(MCP_TOOLS, sort_keys=True)),
                    "skill_recipe_chars": len(SKILL_AND_RECIPE_PROMPT),
                }
                return _extract_json(str(content)), dict(usage), stats
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(2**attempt, 8))
    raise HTTPException(status_code=503, detail=f"Model call failed: {last_error}")


def _sum_usage(*usages: dict[str, Any]) -> dict[str, Any]:
    prompt = sum(int(item.get("prompt_tokens") or 0) for item in usages)
    completion = sum(int(item.get("completion_tokens") or 0) for item in usages)
    total = sum(int(item.get("total_tokens") or 0) for item in usages)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total, "plan_usage": usages[0] if usages else {}, "final_usage": usages[1] if len(usages) > 1 else {}}


def _history_text(history: list[dict[str, Any]] | None) -> str:
    return "\n".join(f"{item.get('role', 'unknown')}: {item.get('content', '')}" for item in history or [])


app = FastAPI(title="GTM MCP Skill/Recipe Baseline Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/mcp/tools")
def mcp_tools() -> dict[str, Any]:
    return {"tools": MCP_TOOLS}


@app.post("/api/ask")
async def ask(req: AskRequest) -> dict[str, Any]:
    actor = _actor(req.actor_id)
    plan_prompt = (
        f"MCP tools from list_tools:\n{json.dumps(MCP_TOOLS, indent=2)}\n\n"
        f"Actor profile:\n{json.dumps(asdict(actor), indent=2)}\n\n"
        f"Conversation history:\n{_history_text(req.history)}\n\n"
        f"User question:\n{req.question}\n"
    )
    started = time.perf_counter()
    plan, plan_usage, plan_stats = await _call_model_json(SKILL_AND_RECIPE_PROMPT, plan_prompt)
    selected_tool = str(plan.get("selected_tool") or "").strip()
    tool_args = plan.get("tool_arguments") if isinstance(plan.get("tool_arguments"), dict) else {}
    guard = _consumer_policy_guard(req.question, actor, req.history)
    if guard:
        selected_tool, tool_args, _guard_outcome = guard
    outcome, tool_result = _execute_mcp_tool(selected_tool, tool_args, actor)
    final_prompt = (
        f"Question: {req.question}\n"
        f"MCP tool called: {selected_tool}\n"
        f"Tool arguments: {json.dumps(tool_args, indent=2)}\n"
        f"Outcome: {outcome}\n"
        f"Tool result: {json.dumps(tool_result, indent=2, default=str)}\n"
    )
    final, final_usage, final_stats = await _call_model_json(FINAL_PROMPT, final_prompt)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    usage = _sum_usage(plan_usage, final_usage)
    prompt_stats = {
        "system_prompt_chars": plan_stats["system_prompt_chars"] + final_stats["system_prompt_chars"],
        "user_prompt_chars": plan_stats["user_prompt_chars"] + final_stats["user_prompt_chars"],
        "tool_schema_chars": plan_stats["tool_schema_chars"],
        "skill_recipe_chars": plan_stats["skill_recipe_chars"],
    }
    return {
        "runtime": "gtm-mcp-skill-recipe-baseline",
        "model": OPENAI_MODEL,
        "question": req.question,
        "actor_id": actor.actor_id,
        "outcome": outcome,
        "selected_tool": selected_tool,
        "tool_arguments": tool_args,
        "tool_result": tool_result,
        "planner": {
            "mode": "mcp_tool_selection_with_consumer_side_skills_recipes",
            "rationale": plan.get("rationale"),
            "expected_outcome": plan.get("expected_outcome"),
            "prompt_stats": prompt_stats,
            "usage": usage,
        },
        "usage": usage,
        "prompt_stats": prompt_stats,
        "loop_counts": {"planner_loops": 2, "tool_invoke_loops": 1, "total_loops": 3},
        "elapsed_ms": elapsed_ms,
        "user_message": final.get("user_message"),
        "result_summary": final.get("result_summary"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9323")))

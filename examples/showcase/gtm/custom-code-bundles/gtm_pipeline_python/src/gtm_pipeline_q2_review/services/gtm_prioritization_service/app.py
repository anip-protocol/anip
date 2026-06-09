"""Benchmark-grade GTM prioritization ANIP service."""
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from shared.actor_identity import authenticate_bearer, parse_actor_principal
from shared.approval_store import approve_request, create_approval_request, list_approval_requests

from ...prioritization_backend_adapter import preview_route_leads, prioritize_accounts, score_leads


SERVICE_ID = "gtm-prioritization-service"
APPROVAL_GRANT_POLICY = {
    "allowed_grant_types": ["one_time", "session_bound"],
    "default_grant_type": "one_time",
    "expires_in_seconds": 900,
    "max_uses": 1,
}


def _actor_policy(ctx: InvocationContext) -> dict:
    return parse_actor_principal(ctx.root_principal)


def _actor_from_bearer(bearer: str | None) -> dict:
    principal = authenticate_bearer(bearer or "")
    if not principal:
        raise HTTPException(status_code=401, detail="Valid actor bearer required")
    return parse_actor_principal(principal)


def _resolve_owner_scope(requested_scope: str | None, actor_policy: dict) -> str | None:
    actor_scope = str(actor_policy.get("pipeline_scope") or "company")
    normalized_requested = str(requested_scope).strip() if requested_scope else None
    if actor_scope in {"company", "all"}:
        return normalized_requested
    if not normalized_requested or normalized_requested in {"company", "all"}:
        return actor_scope
    if normalized_requested != actor_scope:
        raise ANIPError("restricted", "This actor is restricted to a narrower prioritization scope.", resolution={"action": "retry_with_owned_scope", "requires": actor_scope})
    return normalized_requested


def _require_str(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ANIPError("clarification_required", question, resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint})


def _bounded_limit(value: object | None, default: int = 10, maximum: int = 25) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


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


def _deny_raw_model_export(params: dict) -> None:
    if params.get("export_mode") == "raw_model":
        raise ANIPError("denied", "Raw model features, weights, or unconstrained scoring export are out of scope for this capability.", resolution={"action": "request_bounded_scorecards", "requires": "priority_band, confidence, and bounded rationale only"})


GTM_SCORE_LEADS_DECL = CapabilityDeclaration(
    name="gtm.score_leads",
    description="Return bounded lead scores and explainable priority bands for a named cohort.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="cohort_ref", type="string", required=True, allowed_values=["inbound_last_week", "webinar_q2"], semantic_type="cohort_reference", catalog_ref="gtm.cohort_catalog", description="Cohort reference; map phrases like inbound leads or last week inbound leads to inbound_last_week"),
        CapabilityInput(name="limit", type="integer", required=False, description="Maximum leads to return"),
        CapabilityInput(name="owner_scope", type="string", required=False, semantic_type="scope_reference", description="Actor-safe ownership scope"),
    ],
    output=CapabilityOutput(type="gtm_score_leads_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.prioritization.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


def _handle_gtm_score_leads(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _deny_raw_model_export(params)
    cohort_ref = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which lead cohort should I score?", "Use inbound_last_week or webinar_q2."))
    result = score_leads(cohort_ref=cohort_ref, limit=_bounded_limit(params.get("limit")), owner_scope=_resolve_owner_scope(params.get("owner_scope"), actor_policy))
    return {"result": result}


GTM_PRIORITIZE_ACCOUNTS_DECL = CapabilityDeclaration(
    name="gtm.prioritize_accounts",
    description="Rank bounded accounts or enriched cohorts by explainable GTM priority.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="cohort_ref", type="string", required=True, allowed_values=["expansion_candidates_q2", "at_risk_q2"], semantic_type="cohort_reference", catalog_ref="gtm.cohort_catalog", description="Account cohort; map phrases like expansion candidates to expansion_candidates_q2 and at risk q2 to at_risk_q2"),
        CapabilityInput(name="ranking_basis", type="string", required=False, default="deal_likelihood", allowed_values=["deal_likelihood"], description="Priority ranking basis"),
        CapabilityInput(name="limit", type="integer", required=False, description="Maximum accounts to return"),
        CapabilityInput(name="owner_scope", type="string", required=False, semantic_type="scope_reference", description="Actor-safe ownership scope"),
    ],
    output=CapabilityOutput(type="gtm_prioritize_accounts_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.prioritization.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


def _handle_gtm_prioritize_accounts(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    cohort_ref = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which account cohort should I prioritize?", "Use expansion_candidates_q2 or at_risk_q2."))
    ranking_basis = str(params.get("ranking_basis") or "deal_likelihood").strip() or "deal_likelihood"
    if ranking_basis != "deal_likelihood":
        raise ANIPError("denied", "This prioritization service currently supports ranking_basis=deal_likelihood only.", resolution={"action": "retry_with_supported_ranking", "requires": "ranking_basis=deal_likelihood"})
    result = prioritize_accounts(cohort_ref=cohort_ref, ranking_basis=ranking_basis, limit=_bounded_limit(params.get("limit")), owner_scope=_resolve_owner_scope(params.get("owner_scope"), actor_policy))
    return {"result": result}


def _handle_gtm_route_leads(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    if not actor_policy.get("can_route_leads"):
        raise ANIPError("denied", "This actor role cannot route leads.", resolution={"action": "request_authorized_actor", "requires": "role with routing authority"})
    if params.get("contains_outreach_request"):
        raise ANIPError("denied", "Outreach drafting is out of scope for the prioritization service.", resolution={"action": "request_in_scope_workflow", "requires": "bounded routing preview only"})
    cohort_ref = _normalize_cohort_ref(_require_str(params, "cohort_ref", "Which lead cohort should I route?", "Use inbound_last_week or webinar_q2."))
    target_queue = str(params.get("target_queue") or "sales").strip() or "sales"
    preview = preview_route_leads(cohort_ref=cohort_ref, target_queue=target_queue, owner_scope=_resolve_owner_scope(params.get("owner_scope"), actor_policy))
    approval_request = create_approval_request(capability="gtm.route_leads", requester=actor_policy, required_role="sales_leader", preview=preview)
    raise ANIPError(
        "approval_required",
        "Lead routing stays at preview until an authorized approver confirms it.",
        resolution={"action": "request_approval", "requires": "approval before downstream routing mutation", "preview": preview, "approval_request_id": approval_request["approval_request_id"], "approval_role_required": "sales_leader" if not actor_policy.get("can_approve_routing") else actor_policy.get("role")},
    )


GTM_ROUTE_LEADS_DECL = CapabilityDeclaration(
    name="gtm.route_leads",
    description="Prepare an approval-gated routing preview for scored or hot leads in a named cohort; outreach drafting is not supported by this capability.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="cohort_ref", type="string", required=True, allowed_values=["inbound_last_week", "webinar_q2"], semantic_type="cohort_reference", catalog_ref="gtm.cohort_catalog", description="Lead cohort; map phrases like inbound leads or last week inbound leads to inbound_last_week"),
        CapabilityInput(name="target_queue", type="string", required=False, default="sales", allowed_values=["sales", "sdr"], description="Destination queue or team; defaults to sales when the user asks for routing recommendations without naming a queue"),
        CapabilityInput(name="owner_scope", type="string", required=False, semantic_type="scope_reference", description="Actor-safe ownership scope"),
    ],
    output=CapabilityOutput(type="gtm_route_leads_preview", fields=["preview"]),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="not_applicable"),
    minimum_scope=["gtm.prioritization.route"],
    grant_policy=APPROVAL_GRANT_POLICY,
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)

gtm_score_leads = Capability(declaration=GTM_SCORE_LEADS_DECL, handler=_handle_gtm_score_leads)
gtm_prioritize_accounts = Capability(declaration=GTM_PRIORITIZE_ACCOUNTS_DECL, handler=_handle_gtm_prioritize_accounts)
gtm_route_leads = Capability(declaration=GTM_ROUTE_LEADS_DECL, handler=_handle_gtm_route_leads)


def create_service() -> ANIPService:
    return ANIPService(
        service_id=os.getenv("ANIP_SERVICE_ID", SERVICE_ID),
        capabilities=[gtm_score_leads, gtm_prioritize_accounts, gtm_route_leads],
        storage=os.getenv("ANIP_STORAGE", ":memory:"),
        trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
        key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
        authenticate=authenticate_bearer,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="GTM Prioritization Service")
    mount_anip(app, create_service(), health_endpoint=True)
    return app


app = create_app()


@app.get("/gtm/approvals")
async def list_approvals(request: Request, status: str | None = None):
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.startswith("Bearer ") else None
    actor_policy = _actor_from_bearer(bearer)
    entries = list_approval_requests(status=status)
    if actor_policy.get("can_approve_routing"):
        return {"entries": entries}
    actor_id = actor_policy.get("actor_id")
    return {"entries": [item for item in entries if item.get("requested_by", {}).get("actor_id") == actor_id]}


@app.post("/gtm/approvals/{approval_request_id}/approve")
async def approve(approval_request_id: str, request: Request):
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.startswith("Bearer ") else None
    actor_policy = _actor_from_bearer(bearer)
    if not actor_policy.get("can_approve_routing"):
        raise HTTPException(status_code=403, detail="This actor cannot approve routing actions")
    approval = approve_request(approval_request_id, actor_policy)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return {"approval": approval}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "4100")))

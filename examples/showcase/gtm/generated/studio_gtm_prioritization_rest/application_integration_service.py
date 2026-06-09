"""Studio-generated ANIP service scaffold for governed application integration."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request

from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from shared.actor_identity import authenticate_bearer, parse_actor_principal
from shared.approval_store import approve_request, create_approval_request, list_approval_requests

from application_integration_backend_adapter import preview_route_leads, prioritize_accounts, score_leads


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
        raise ANIPError(
            "restricted",
            "This actor is restricted to a narrower prioritization scope.",
            resolution={"action": "retry_with_owned_scope", "requires": actor_scope},
        )
    return normalized_requested


def _require_str(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ANIPError(
        "clarification_required",
        question,
        resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint},
    )


def _bounded_limit(value: object | None, default: int = 10, maximum: int = 25) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


def _deny_raw_model_export(params: dict) -> None:
    if params.get("export_mode") == "raw_model":
        raise ANIPError(
            "denied",
            "Raw model features, weights, or unconstrained scoring export are out of scope for this capability.",
            resolution={"action": "request_bounded_scorecards", "requires": "priority_band, confidence, and bounded rationale only"},
        )


GTM_SCORE_LEADS_DECL = CapabilityDeclaration(
    name="gtm.score_leads",
    description="Return bounded lead scores and explainable priority bands for a named cohort.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="cohort_ref", type="string", required=True, description="Cohort reference such as inbound_last_week"),
        CapabilityInput(name="limit", type="integer", required=False, description="Maximum leads to return"),
        CapabilityInput(name="owner_scope", type="string", required=False, description="Actor-safe ownership scope"),
    ],
    output=CapabilityOutput(type="gtm_score_leads_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.prioritization.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_gtm_score_leads(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _deny_raw_model_export(params)
    cohort_ref = _require_str(
        params,
        "cohort_ref",
        "Which lead cohort should I score?",
        "Use a supported cohort like inbound_last_week or webinar_q2.",
    )
    owner_scope = _resolve_owner_scope(params.get("owner_scope"), actor_policy)
    limit = _bounded_limit(params.get("limit"), default=10)
    result = score_leads(cohort_ref=cohort_ref, limit=limit, owner_scope=owner_scope)
    return {
        "result": {
            "cohort_ref": result["cohort_ref"],
            "owner_scope": result["owner_scope"],
            "lead_scores": result["lead_scores"],
        }
    }


gtm_score_leads = Capability(declaration=GTM_SCORE_LEADS_DECL, handler=_handle_gtm_score_leads)


GTM_PRIORITIZE_ACCOUNTS_DECL = CapabilityDeclaration(
    name="gtm.prioritize_accounts",
    description="Rank bounded accounts or enriched cohorts by explainable GTM priority.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="cohort_ref", type="string", required=True, description="Account cohort such as expansion_candidates_q2"),
        CapabilityInput(name="ranking_basis", type="string", required=False, default="deal_likelihood", allowed_values=["deal_likelihood"], description="Priority ranking basis such as deal_likelihood"),
        CapabilityInput(name="limit", type="integer", required=False, description="Maximum accounts to return"),
        CapabilityInput(name="owner_scope", type="string", required=False, description="Actor-safe ownership scope"),
    ],
    output=CapabilityOutput(type="gtm_prioritize_accounts_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.prioritization.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_gtm_prioritize_accounts(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    cohort_ref = _require_str(
        params,
        "cohort_ref",
        "Which account cohort should I prioritize?",
        "Use a supported cohort like expansion_candidates_q2 or at_risk_q2.",
    )
    ranking_basis = str(params.get("ranking_basis") or "deal_likelihood").strip() or "deal_likelihood"
    if ranking_basis != "deal_likelihood":
        raise ANIPError(
            "denied",
            "This prioritization service currently supports ranking_basis=deal_likelihood only.",
            resolution={"action": "retry_with_supported_ranking", "requires": "ranking_basis=deal_likelihood"},
        )
    owner_scope = _resolve_owner_scope(params.get("owner_scope"), actor_policy)
    limit = _bounded_limit(params.get("limit"), default=10)
    result = prioritize_accounts(cohort_ref=cohort_ref, ranking_basis=ranking_basis, limit=limit, owner_scope=owner_scope)
    return {"result": result}


gtm_prioritize_accounts = Capability(declaration=GTM_PRIORITIZE_ACCOUNTS_DECL, handler=_handle_gtm_prioritize_accounts)


GTM_ROUTE_LEADS_DECL = CapabilityDeclaration(
    name="gtm.route_leads",
    description="Preview or approve routing recommendations for a bounded lead cohort.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="cohort_ref", type="string", required=True, description="Bounded lead cohort to route"),
        CapabilityInput(name="target_queue", type="string", required=True, allowed_values=["sales", "sdr"], description="Target queue or team"),
        CapabilityInput(name="owner_scope", type="string", required=False, description="Actor-safe routing scope"),
    ],
    output=CapabilityOutput(type="gtm_route_leads_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="not_applicable"),
    minimum_scope=["gtm.prioritization.route"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_gtm_route_leads(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    if not actor_policy.get("can_route_leads"):
        raise ANIPError(
            "denied",
            "This actor role cannot route leads.",
            resolution={"action": "request_authorized_actor", "requires": "role with routing authority"},
        )
    if params.get("contains_outreach_request"):
        raise ANIPError(
            "denied",
            "Outreach drafting is out of scope for the prioritization service.",
            resolution={"action": "request_in_scope_workflow", "requires": "bounded routing preview only"},
        )
    cohort_ref = _require_str(
        params,
        "cohort_ref",
        "Which lead cohort should I route?",
        "Use a supported cohort like inbound_last_week or webinar_q2.",
    )
    target_queue = _require_str(
        params,
        "target_queue",
        "Which queue or team should receive the routing preview?",
        "Use a supported queue like sales or sdr.",
    )
    owner_scope = _resolve_owner_scope(params.get("owner_scope"), actor_policy)
    preview = preview_route_leads(cohort_ref=cohort_ref, target_queue=target_queue, owner_scope=owner_scope)
    approval_request = create_approval_request(
        capability="gtm.route_leads",
        requester=actor_policy,
        required_role="sales_leader",
        preview=preview,
    )
    raise ANIPError(
        "approval_required",
        "Lead routing stays at preview until an authorized approver confirms it.",
        resolution={
            "action": "request_approval",
            "requires": "approval before downstream routing mutation",
            "preview": preview,
            "approval_request_id": approval_request["approval_request_id"],
            "approval_role_required": "sales_leader" if not actor_policy.get("can_approve_routing") else actor_policy.get("role"),
        },
    )


gtm_route_leads = Capability(declaration=GTM_ROUTE_LEADS_DECL, handler=_handle_gtm_route_leads)


service = ANIPService(
    service_id="anip-gtm-prioritization-showcase",
    capabilities=[gtm_score_leads, gtm_prioritize_accounts, gtm_route_leads],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "unsigned"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=authenticate_bearer,
)

app = FastAPI(title="Studio Generated Governed Application Integration Service")
mount_anip(app, service, health_endpoint=True)


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
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9200")))

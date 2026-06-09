"""Benchmark-grade GTM outreach ANIP service."""
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from shared.actor_identity import authenticate_bearer, parse_actor_principal

from ...enrichment_backend_adapter import fetch_account_enrichment_summary
from ...outreach_backend_adapter import draft_outreach_message_async, objection_response_variants_async, suggest_followup_content_async
from ...prioritization_backend_adapter import prioritize_accounts


SERVICE_ID = "gtm-outreach-service"
APPROVAL_GRANT_POLICY = {
    "allowed_grant_types": ["one_time", "session_bound"],
    "default_grant_type": "one_time",
    "expires_in_seconds": 900,
    "max_uses": 1,
}


def _actor_policy(ctx: InvocationContext) -> dict:
    return parse_actor_principal(ctx.root_principal)


def _require_outreach_access(actor_policy: dict) -> None:
    if str(actor_policy.get("outreach_access") or "full") == "none":
        raise ANIPError("denied", "This actor cannot use the outreach service.", resolution={"action": "request_authorized_actor", "requires": "role with outreach access"})


def _require_str(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ANIPError("clarification_required", question, resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint})


def _bounded_variant_count(value: object | None, actor_policy: dict) -> int:
    actor_limit = 1 if str(actor_policy.get("outreach_access") or "full") == "bounded" else 3
    try:
        requested = int(value or actor_limit)
    except (TypeError, ValueError):
        requested = actor_limit
    return max(1, min(requested, actor_limit))


def _bounded_account_limit(value: object | None, default: int = 3, maximum: int = 10) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


def _normalize_objection_theme(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if "competitor" in normalized:
        return "competitor"
    if normalized in {"implementation", "implementation_risk", "implementation_concern"}:
        return "implementation_risk"
    if "price" in normalized or "pricing" in normalized:
        return "pricing"
    return normalized


GTM_DRAFT_OUTREACH_MESSAGE_DECL = CapabilityDeclaration(
    name="gtm.draft_outreach_message",
    description="Draft a bounded outreach message for a selected target and explicit objective; send actions and raw transcripts are not supported.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="target_ref", type="string", required=True, semantic_type="entity_reference", entity_reference=True, catalog_ref="gtm.account_or_lead_catalog", description="Lead or account reference"),
        CapabilityInput(name="objective", type="string", required=True, default="first_touch", allowed_values=["first_touch", "follow_up", "revive_stalled"], description="Message objective"),
        CapabilityInput(name="channel", type="string", required=False, default="email", allowed_values=["email", "linkedin", "call_follow_up"], description="Requested outreach channel"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_draft_outreach_message_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.outreach.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


async def _handle_gtm_draft_outreach_message(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    if params.get("request_mode") == "send_now":
        raise ANIPError("denied", "The first outreach cut is draft-only. Send actions are out of scope.", resolution={"action": "request_draft_only", "requires": "bounded draft generation only"})
    if params.get("request_mode") == "raw_transcripts":
        raise ANIPError("denied", "Raw sales-conversation transcripts are out of scope for this outreach service.", resolution={"action": "request_bounded_draft", "requires": "bounded outreach draft output only"})
    result = await draft_outreach_message_async(
        target_ref=_require_str(params, "target_ref", "Which account or lead is this outreach for?", "Use Condax, Acme Corporation, or Codehow."),
        objective=str(params.get("objective") or "first_touch").strip() or "first_touch",
        channel=str(params.get("channel") or "email").strip() or "email",
        persona=str(params.get("persona") or "").strip() or None,
    )
    return {"result": result}


GTM_SUGGEST_FOLLOWUP_CONTENT_DECL = CapabilityDeclaration(
    name="gtm.suggest_followup_content",
    description="Return bounded follow-up content variants for an explicit GTM target.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="target_ref", type="string", required=True, semantic_type="entity_reference", entity_reference=True, catalog_ref="gtm.account_or_lead_catalog", description="Lead or account reference"),
        CapabilityInput(name="variant_count", type="integer", required=False, description="Maximum variants to return"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_suggest_followup_content_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.outreach.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


async def _handle_gtm_suggest_followup_content(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    variant_count = _bounded_variant_count(params.get("variant_count"), actor_policy)
    result = await suggest_followup_content_async(
        target_ref=_require_str(params, "target_ref", "Which account or lead should these follow-up variants target?", "Use Condax, Acme Corporation, or Codehow."),
        variant_count=variant_count,
        persona=str(params.get("persona") or "").strip() or None,
    )
    result["variants"] = result.get("variants", [])[:variant_count]
    result["variant_limit_applied"] = variant_count
    return {"result": result}


GTM_OBJECTION_RESPONSE_VARIANTS_DECL = CapabilityDeclaration(
    name="gtm.objection_response_variants",
    description="Return bounded objection-response variants for a selected competitor or concern.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="objection_theme", type="string", required=True, allowed_values=["pricing", "competitor", "implementation_risk"], description="Named objection theme. Use competitor for competitor objections."),
        CapabilityInput(name="target_ref", type="string", required=False, semantic_type="entity_reference", entity_reference=True, catalog_ref="gtm.account_or_lead_catalog", description="Optional GTM target reference"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_objection_response_variants_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.outreach.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


async def _handle_gtm_objection_response_variants(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    if not actor_policy.get("can_use_objection_variants"):
        raise ANIPError("denied", "This actor can use bounded draft generation but not objection-response variants.", resolution={"action": "request_authorized_actor", "requires": "role with objection-variant access"})
    if params.get("detail_request") == "raw_transcripts":
        raise ANIPError("denied", "Raw training conversations or transcript exports are out of scope for this service.", resolution={"action": "request_bounded_variants", "requires": "bounded objection-response variants only"})
    objection_theme = _normalize_objection_theme(_require_str(params, "objection_theme", "Which objection or competitor theme should these variants address?", "Use pricing, competitor, or implementation_risk."))
    result = await objection_response_variants_async(
        objection_theme=objection_theme,
        target_ref=str(params.get("target_ref") or "").strip() or None,
        persona=str(params.get("persona") or "").strip() or None,
    )
    return {"result": result}


GTM_PRIORITIZED_OUTREACH_DRAFT_DECL = CapabilityDeclaration(
    name="gtm.prioritized_outreach_draft",
    description="Prioritize a bounded account cohort, include bounded enrichment context for the top accounts, and draft one outreach message for the highest-priority account; this is for prioritization-to-enrichment-to-draft requests, not lead routing.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="cohort_ref", type="string", required=True, allowed_values=["expansion_candidates_q2", "at_risk_q2"], semantic_type="cohort_reference", catalog_ref="gtm.cohort_catalog", description="Account cohort to prioritize, such as expansion_candidates_q2"),
        CapabilityInput(name="ranking_basis", type="string", required=False, default="deal_likelihood", allowed_values=["deal_likelihood"], description="Priority ranking basis"),
        CapabilityInput(name="limit", type="integer", required=False, default=3, description="Maximum accounts to consider before drafting"),
        CapabilityInput(name="owner_scope", type="string", required=False, semantic_type="scope_reference", description="Regional office or company"),
        CapabilityInput(name="objective", type="string", required=False, default="first_touch", allowed_values=["first_touch", "follow_up", "revive_stalled"], description="Message objective"),
        CapabilityInput(name="channel", type="string", required=False, default="email", allowed_values=["email", "linkedin", "call_follow_up"], description="Requested outreach channel"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_prioritized_outreach_draft_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.prioritization.read", "gtm.outreach.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "400ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


async def _handle_gtm_prioritized_outreach_draft(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    if params.get("request_mode") == "send_now":
        raise ANIPError("denied", "Prioritized outreach preparation is draft-only.", resolution={"action": "request_draft_only", "requires": "bounded draft generation only"})

    cohort_ref = _require_str(params, "cohort_ref", "Which account cohort should be prioritized before drafting outreach?", "Use expansion_candidates_q2 or at_risk_q2.")
    ranking_basis = str(params.get("ranking_basis") or "deal_likelihood").strip() or "deal_likelihood"
    limit = _bounded_account_limit(params.get("limit"))
    prioritized = prioritize_accounts(
        cohort_ref=cohort_ref,
        ranking_basis=ranking_basis,
        limit=limit,
        owner_scope=str(params.get("owner_scope") or "").strip() or None,
    )
    accounts = prioritized.get("accounts") or []
    if not accounts:
        return {"result": {"cohort_ref": cohort_ref, "accounts": [], "draft": None, "empty": True}}

    target_ref = str(accounts[0].get("account_name") or "").strip()
    if not target_ref:
        raise ANIPError("clarification_required", "The prioritized account result did not include a draftable account target.", resolution={"action": "retry_with_supported_cohort", "requires": "cohort_ref with account_name values"})
    enrichment = fetch_account_enrichment_summary(
        account_names=[str(item.get("account_name") or "").strip() for item in accounts if str(item.get("account_name") or "").strip()],
        limit=len(accounts),
        actor_policy=actor_policy,
    )
    draft = await draft_outreach_message_async(
        target_ref=target_ref,
        objective=str(params.get("objective") or "first_touch").strip() or "first_touch",
        channel=str(params.get("channel") or "email").strip() or "email",
        persona=str(params.get("persona") or "").strip() or None,
    )
    return {
        "result": {
            "cohort_ref": cohort_ref,
            "ranking_basis": ranking_basis,
            "prioritized_accounts": accounts,
            "enrichment": enrichment,
            "selected_target_ref": target_ref,
            "draft": draft,
        }
    }


GTM_BOTTLENECK_ACCOUNT_OUTREACH_DRAFT_DECL = CapabilityDeclaration(
    name="gtm.bottleneck_account_outreach_draft",
    description="Draft outreach only for a specific account already selected from a bounded bottleneck or at-risk account review. Do not use this capability to choose the top or affected account from analysis; use the approval-gated follow-up preparation flow for derived-target bottleneck or at-risk requests.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="quarter", type="string", required=True, semantic_type="time_scope", description="Quarter label like 2017-Q2"),
        CapabilityInput(
            name="target_ref",
            type="string",
            required=False,
            semantic_type="entity_reference",
            entity_reference=True,
            catalog_ref="gtm.account_catalog",
            resolution={
                "mode": "backend_resolved",
                "resolver_ref": "gtm.bottleneck_account_selector",
                "on_missing": "app_select_or_clarify",
                "on_ambiguous": "clarify",
                "on_unresolved": "clarify",
            },
            description="Specific account selected from the bottleneck review; if omitted, the service returns an approval-gated target-selection preview.",
        ),
        CapabilityInput(name="owner_scope", type="string", required=False, semantic_type="scope_reference", description="Regional office or company"),
        CapabilityInput(name="objective", type="string", required=False, default="first_touch", allowed_values=["first_touch", "follow_up", "revive_stalled"], description="Message objective"),
        CapabilityInput(name="channel", type="string", required=False, default="email", allowed_values=["email", "linkedin", "call_follow_up"], description="Requested outreach channel"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_bottleneck_account_outreach_draft_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.pipeline.read", "gtm.outreach.read"],
    grant_policy=APPROVAL_GRANT_POLICY,
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "350ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


async def _handle_gtm_bottleneck_account_outreach_draft(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2.")
    target_ref_value = params.get("target_ref")
    if not isinstance(target_ref_value, str) or not target_ref_value.strip():
        if str(actor_policy.get("outreach_access") or "full") != "full":
            raise ANIPError(
                "denied",
                "This actor cannot request approval-gated outreach target selection.",
                resolution={
                    "action": "request_authorized_actor",
                    "requires": "role with full outreach approval authority or explicit selected target_ref",
                },
            )
        raise ANIPError(
            "approval_required",
            "Drafting outreach from a bottleneck review requires approval or an explicit selected account before generating the message.",
            resolution={
                "action": "request_approval_or_select_target",
                "requires": "specific target_ref selected from the bounded bottleneck or at-risk account review",
                "preview": {
                    "quarter": quarter,
                    "owner_scope": str(params.get("owner_scope") or "").strip() or None,
                    "objective": str(params.get("objective") or "first_touch").strip() or "first_touch",
                    "channel": str(params.get("channel") or "email").strip() or "email",
                },
            },
        )
    target_ref = target_ref_value.strip()
    draft = await draft_outreach_message_async(
        target_ref=target_ref,
        objective=str(params.get("objective") or "first_touch").strip() or "first_touch",
        channel=str(params.get("channel") or "email").strip() or "email",
        persona=str(params.get("persona") or "").strip() or None,
    )
    return {"result": {"target_ref": target_ref, "draft": draft}}

gtm_draft_outreach_message = Capability(declaration=GTM_DRAFT_OUTREACH_MESSAGE_DECL, handler=_handle_gtm_draft_outreach_message)
gtm_suggest_followup_content = Capability(declaration=GTM_SUGGEST_FOLLOWUP_CONTENT_DECL, handler=_handle_gtm_suggest_followup_content)
gtm_objection_response_variants = Capability(declaration=GTM_OBJECTION_RESPONSE_VARIANTS_DECL, handler=_handle_gtm_objection_response_variants)
gtm_prioritized_outreach_draft = Capability(declaration=GTM_PRIORITIZED_OUTREACH_DRAFT_DECL, handler=_handle_gtm_prioritized_outreach_draft)
gtm_bottleneck_account_outreach_draft = Capability(declaration=GTM_BOTTLENECK_ACCOUNT_OUTREACH_DRAFT_DECL, handler=_handle_gtm_bottleneck_account_outreach_draft)


def create_service() -> ANIPService:
    return ANIPService(
        service_id=os.getenv("ANIP_SERVICE_ID", SERVICE_ID),
        capabilities=[
            gtm_draft_outreach_message,
            gtm_suggest_followup_content,
            gtm_objection_response_variants,
            gtm_prioritized_outreach_draft,
            gtm_bottleneck_account_outreach_draft,
        ],
        storage=os.getenv("ANIP_STORAGE", ":memory:"),
        trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
        key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
        authenticate=authenticate_bearer,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="GTM Outreach Service")
    mount_anip(app, create_service(), health_endpoint=True)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "4100")))

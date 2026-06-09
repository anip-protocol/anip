"""Studio-generated ANIP service scaffold for governed MCP-backed outreach."""
from __future__ import annotations

import os

from fastapi import FastAPI

from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from shared.actor_identity import authenticate_bearer, parse_actor_principal

from application_integration_backend_adapter import (
    draft_outreach_message_async,
    objection_response_variants_async,
    suggest_followup_content_async,
)


def _actor_policy(ctx: InvocationContext) -> dict:
    return parse_actor_principal(ctx.root_principal)


def _require_outreach_access(actor_policy: dict) -> None:
    if str(actor_policy.get("outreach_access") or "full") == "none":
        raise ANIPError(
            "denied",
            "This actor cannot use the outreach service.",
            resolution={"action": "request_authorized_actor", "requires": "role with outreach access"},
        )


def _require_str(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ANIPError(
        "clarification_required",
        question,
        resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint},
    )


def _bounded_variant_count(value: object | None, actor_policy: dict) -> int:
    actor_limit = 1 if str(actor_policy.get("outreach_access") or "full") == "bounded" else 3
    try:
        requested = int(value or actor_limit)
    except (TypeError, ValueError):
        requested = actor_limit
    return max(1, min(requested, actor_limit))


GTM_DRAFT_OUTREACH_MESSAGE_DECL = CapabilityDeclaration(
    name="gtm.draft_outreach_message",
    description="Draft a bounded outreach message for a selected target and explicit objective.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="target_ref", type="string", required=True, description="Lead or account reference"),
        CapabilityInput(name="objective", type="string", required=True, default="first_touch", allowed_values=["first_touch", "follow_up", "revive_stalled"], description="Message objective such as first_touch or follow_up"),
        CapabilityInput(name="channel", type="string", required=False, default="email", allowed_values=["email", "linkedin", "call_follow_up"], description="Requested outreach channel"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_draft_outreach_message_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.outreach.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


async def _handle_gtm_draft_outreach_message(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    if params.get("request_mode") == "send_now":
        raise ANIPError(
            "denied",
            "The first outreach cut is draft-only. Send actions are out of scope.",
            resolution={"action": "request_draft_only", "requires": "bounded draft generation only"},
        )
    if params.get("request_mode") == "raw_transcripts":
        raise ANIPError(
            "denied",
            "Raw sales-conversation transcripts are out of scope for this outreach service.",
            resolution={"action": "request_bounded_draft", "requires": "bounded outreach draft output only"},
        )
    target_ref = _require_str(
        params,
        "target_ref",
        "Which account or lead is this outreach for?",
        "Use an explicit target such as Condax, Acme Corporation, or Codehow.",
    )
    objective = _require_str(
        params,
        "objective",
        "What outreach objective should this draft support?",
        "Use an objective like first_touch or follow_up.",
    )
    channel = str(params.get("channel") or "email").strip() or "email"
    persona = str(params.get("persona") or "").strip() or None
    result = await draft_outreach_message_async(target_ref=target_ref, objective=objective, channel=channel, persona=persona)
    return {"result": result}


gtm_draft_outreach_message = Capability(
    declaration=GTM_DRAFT_OUTREACH_MESSAGE_DECL,
    handler=_handle_gtm_draft_outreach_message,
)


GTM_SUGGEST_FOLLOWUP_CONTENT_DECL = CapabilityDeclaration(
    name="gtm.suggest_followup_content",
    description="Return bounded follow-up content variants for an explicit GTM target.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="target_ref", type="string", required=True, description="Lead or account reference"),
        CapabilityInput(name="variant_count", type="integer", required=False, description="Maximum variants to return"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_suggest_followup_content_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.outreach.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


async def _handle_gtm_suggest_followup_content(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    target_ref = _require_str(
        params,
        "target_ref",
        "Which account or lead should these follow-up variants target?",
        "Use an explicit target such as Condax, Acme Corporation, or Codehow.",
    )
    persona = str(params.get("persona") or "").strip() or None
    variant_count = _bounded_variant_count(params.get("variant_count"), actor_policy)
    result = await suggest_followup_content_async(target_ref=target_ref, variant_count=variant_count, persona=persona)
    result["variants"] = result.get("variants", [])[:variant_count]
    result["variant_limit_applied"] = variant_count
    return {"result": result}


gtm_suggest_followup_content = Capability(
    declaration=GTM_SUGGEST_FOLLOWUP_CONTENT_DECL,
    handler=_handle_gtm_suggest_followup_content,
)


GTM_OBJECTION_RESPONSE_VARIANTS_DECL = CapabilityDeclaration(
    name="gtm.objection_response_variants",
    description="Return bounded objection-response variants for a selected competitor or concern.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="objection_theme", type="string", required=True, allowed_values=["pricing", "competitor", "implementation_risk"], description="Named objection or competitor theme"),
        CapabilityInput(name="target_ref", type="string", required=False, description="Optional GTM target reference"),
        CapabilityInput(name="persona", type="string", required=False, description="Target persona or audience"),
    ],
    output=CapabilityOutput(type="gtm_objection_response_variants_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.outreach.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


async def _handle_gtm_objection_response_variants(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    _require_outreach_access(actor_policy)
    if not actor_policy.get("can_use_objection_variants"):
        raise ANIPError(
            "denied",
            "This actor can use bounded draft generation but not objection-response variants.",
            resolution={"action": "request_authorized_actor", "requires": "role with objection-variant access"},
        )
    if params.get("detail_request") == "raw_transcripts":
        raise ANIPError(
            "denied",
            "Raw training conversations or transcript exports are out of scope for this service.",
            resolution={"action": "request_bounded_variants", "requires": "bounded objection-response variants only"},
        )
    objection_theme = _require_str(
        params,
        "objection_theme",
        "Which objection or competitor theme should these variants address?",
        "Use a theme like pricing, competitor, or implementation_risk.",
    )
    target_ref = str(params.get("target_ref") or "").strip() or None
    persona = str(params.get("persona") or "").strip() or None
    result = await objection_response_variants_async(objection_theme=objection_theme, target_ref=target_ref, persona=persona)
    return {"result": result}


gtm_objection_response_variants = Capability(
    declaration=GTM_OBJECTION_RESPONSE_VARIANTS_DECL,
    handler=_handle_gtm_objection_response_variants,
)


service = ANIPService(
    service_id="anip-gtm-outreach-showcase",
    capabilities=[
        gtm_draft_outreach_message,
        gtm_suggest_followup_content,
        gtm_objection_response_variants,
    ],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "unsigned"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=authenticate_bearer,
)

app = FastAPI(title="Studio Generated Governed Application Integration Service")
mount_anip(app, service, health_endpoint=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9200")))

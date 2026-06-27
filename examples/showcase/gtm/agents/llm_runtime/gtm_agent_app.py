"""GTM agent application profile for the generic ANIP LLM runtime.

This module is intentionally app-specific. The reusable ANIP runtime imports it
only when ANIP_AGENT_APP_MODULE=gtm_agent_app is set.
"""
from __future__ import annotations

import re
from typing import Any

RUNTIME_NAME = "gtm-anip-agent-app"
RUNTIME_TITLE = "GTM ANIP Agent App"

SYSTEM_PROMPT = """You are a GTM agent application running on top of ANIP.

Use the discovered ANIP capabilities as the integration contract. The ANIP
runtime handles discovery, token issuance, invocation, approval flows, and
standard ANIP failures. Your job is product-level GTM framing: choose one
declared capability, bind declared parameters, and explain the result in a
bounded GTM operator style.

Rules:
- Do not invent capability IDs, parameter names, datasets, permissions, or service workflows.
- Prefer a declared composed/business capability when it matches the user intent.
- Use only one declared capability per turn.
- Do not recreate cross-service workflows in the agent app.
- Treat service clarification, denial, and approval-required responses as authoritative.
- Use business_effects when present to distinguish draft, summary, recommendation, preview, mutation, dispatch, and raw export behavior.
- If the user requests an effect not produced by the selected capability, set unsupported=true rather than pretending the capability can do it.
- Do not infer missing quarter values from examples, datasets, or benchmark context. Only bind quarter when the user explicitly states a concrete YYYY-Qn value.
- Return only valid JSON.
"""

PLANNING_GUIDANCE = """GTM app guidance:
- Pipeline capabilities answer pipeline health, risk, reassignment previews, and follow-up previews.
- Enrichment capabilities answer bounded account context and lookalike context.
- Prioritization capabilities rank bounded lead/account cohorts and may preview approval-gated routing.
- Outreach capabilities produce bounded outreach content or objection-response variants.
- If a request explicitly asks to route leads, choose the routing capability even when the same sentence also asks for a draft; routing is the governing approval boundary.
- If a request asks to prioritize an account cohort and draft outreach for the top or highest-priority account, choose gtm.prioritized_outreach_draft; do not choose follow-up task preparation unless the user asks to create, prepare, or approve tasks.
- If a request asks to identify bottlenecks or at-risk accounts, enrich them, and draft for the top one without naming a specific account, choose the bottleneck outreach capability and omit target_ref so the service can return its approval/safe-stop response.
- Do not use the bottleneck outreach capability for a plain draft request like "draft for the top account" or "draft for the account we should focus on first" unless the user also mentions bottleneck, at-risk, risk review, pipeline review, or enrichment. Plain draft requests without a named account should choose the direct draft capability and omit target_ref for clarification.
- Vague review-set phrases such as "accounts we should review next" are not account names and are not concrete quarters. If no explicit account list or YYYY-Qn quarter appears, omit the missing parameter so the service clarifies instead of inventing "current", "current quarter", or "2017-Q2".
- A capability that produces content.draft should not be treated as external_dispatch.
- A capability that produces content.summary or data.aggregate should not be treated as raw_data_export.
- Approval-required responses are valid GTM outcomes, not runtime failures.
"""

CAPABILITY_METADATA = {
    "gtm.pipeline_summary": {
        "business_language_rules": [
            {
                "id": "bounded-risk-concentration",
                "meaning": "Risk concentration at the pipeline-summary level means bounded risk distribution or concentration evidence, not raw export or hidden row-level detail.",
                "owner": "agent_app_glue",
                "applies_when": {
                    "all_terms": ["risk"],
                    "any_terms": ["concentration", "concentrated"],
                    "exclude_terms": ["raw", "export", "csv", "download"],
                },
                "interpretation": "Treat bounded risk concentration wording as supported summary intent for this capability.",
                "agent_action": "treat_as_supported",
            },
        ],
        "app_boundaries": {
            "unsupported_terms": {
                "raw_data_export": ["masked financial detail"],
            },
        },
    },
    "gtm.draft_outreach_message": {
        "reference_catalogs": {
            "target_ref": ["Condax", "Acme Corporation", "Codehow"],
        },
        "input_meanings": {
            "target_ref": {
                "Condax": "Supported outreach target for industrial manufacturing operations outreach.",
                "Acme Corporation": "Supported outreach target for at-risk account coordination outreach.",
                "Codehow": "Supported outreach target for GTM systems and routing outreach.",
            },
            "objective": {
                "first_touch": "Initial outreach to a target with no assumed prior conversation.",
                "follow_up": "Follow-up content after a previous touch or known context.",
                "revive_stalled": "Re-engagement content for a stalled opportunity or dormant target.",
            },
            "channel": {
                "email": "Email-ready draft content.",
                "linkedin": "Shorter social outreach draft.",
                "call_follow_up": "Talk-track or call follow-up draft.",
            },
        },
        "result_display": {
            "primary_fields": ["subject", "body", "rationale"],
            "style": "Show draft content first, then concise rationale/evidence.",
        },
        "app_boundaries": {
            "guidance": "This capability drafts content only. It does not send messages or mutate CRM records.",
            "unsupported_terms": {
                "system.unsupported_composition": ["lookalike accounts", "best match"],
            },
        },
    },
    "gtm.suggest_followup_content": {
        "reference_catalogs": {
            "target_ref": ["Condax", "Acme Corporation", "Codehow"],
        },
        "input_meanings": {
            "target_ref": {
                "Condax": "Supported follow-up content target for industrial manufacturing operations outreach.",
                "Acme Corporation": "Supported follow-up content target for at-risk account coordination outreach.",
                "Codehow": "Supported follow-up content target for GTM systems and routing outreach.",
            },
        },
        "result_display": {
            "primary_fields": ["variants", "rationale"],
            "style": "Show the bounded variants as options with short rationale.",
        },
        "app_boundaries": {
            "guidance": "This capability recommends follow-up content; it does not execute outreach.",
        },
    },
    "gtm.objection_response_variants": {
        "reference_catalogs": {
            "target_ref": ["Condax", "Acme Corporation", "Codehow"],
        },
        "input_meanings": {
            "objection_theme": {
                "competitor": "Competitive vendor, alternative solution, incumbent displacement, or comparison concern.",
                "pricing": "Price, budget, cost, affordability, or procurement concern.",
                "implementation_risk": "Rollout, adoption, complexity, integration, or implementation difficulty concern.",
            },
            "target_ref": {
                "Condax": "Supported objection-response target for industrial manufacturing operations outreach.",
                "Acme Corporation": "Supported objection-response target for at-risk account coordination outreach.",
                "Codehow": "Supported objection-response target for GTM systems and routing outreach.",
            },
        },
        "result_display": {
            "primary_fields": ["variants", "rationale"],
            "style": "Show variants grouped by objection-handling angle.",
        },
        "app_boundaries": {
            "guidance": "This capability returns bounded variants, not raw transcript exports or outbound sends.",
        },
    },
    "gtm.route_leads": {
        "business_language_rules": [
            {
                "id": "follow-up-as-routing-purpose",
                "meaning": "Account-executive follow-up can describe the destination or purpose of a routing preview. It is not outreach drafting unless the user asks to draft, write, generate, send, email, message, or create content.",
                "owner": "agent_app_glue",
                "applies_when": {
                    "all_terms": ["follow-up"],
                    "any_terms": ["account executive", "ae", "sales"],
                    "exclude_terms": ["draft", "write", "generate", "send", "email", "message", "content", "linkedin"],
                },
                "interpretation": "Keep this as routing/approval-preview intent, not outreach-content intent.",
                "agent_action": "treat_as_purpose",
            },
        ],
        "input_meanings": {
            "cohort_ref": {
                "inbound_last_week": "Hot inbound leads, recent inbound leads, or inbound leads received during the last week.",
                "webinar_q2": "Leads sourced from the Q2 webinar motion.",
            },
            "target_queue": {
                "sales": "Route leads to sales or account executive handoff.",
                "sdr": "SDR qualification queue.",
            },
        },
        "result_display": {
            "primary_fields": ["preview", "approval_request_id", "rationale"],
            "style": "Show the preview and approval requirement clearly before any execution language.",
        },
        "approval": {
            "required": True,
        },
        "app_boundaries": {
            "guidance": "This capability previews routing and requests approval; it does not execute routing by itself.",
        },
    },
    "gtm.score_leads": {
        "input_meanings": {
            "cohort_ref": {
                "inbound_last_week": "Hot inbound leads, recent inbound leads, or inbound leads received during the last week.",
                "webinar_q2": "Leads sourced from the Q2 webinar motion.",
            },
        },
    },
    "gtm.prioritize_accounts": {
        "input_meanings": {
            "cohort_ref": {
                "expansion_candidates_q2": "Expansion candidates for Q2 account prioritization or expansion motion.",
                "at_risk_q2": "Q2 at-risk account cohort for risk-based prioritization.",
            },
        },
    },
    "gtm.bottleneck_account_outreach_draft": {
        "input_meanings": {
            "quarter": {
                "2017-Q2": "Q2 at-risk account or bottleneck review context for this GTM showcase package.",
            }
        },
        "business_effects": {
            "produces": ["content.draft"],
            "does_not_produce": ["external_dispatch"],
        },
        "result_display": {
            "primary_fields": ["subject", "body", "rationale", "preview", "approval_request_id"],
            "style": "Show draft content when a concrete target is available; show approval/preview safe-stop details when the target is derived.",
        },
        "app_boundaries": {
            "guidance": "Use this when the user asks to derive a target from bottleneck/risk analysis and draft for the top account without explicitly naming that account.",
            "conditional_approval_boundary": {
                "when_missing": ["target_ref"],
                "produces": ["approval.request", "system.preview_mutation"],
            },
        },
    },
    "gtm.prioritized_outreach_draft": {
        "input_meanings": {
            "cohort_ref": {
                "expansion_candidates_q2": "Expansion candidates for Q2 account prioritization before drafting outreach.",
                "at_risk_q2": "Q2 at-risk account cohort for risk-based prioritization before drafting outreach.",
            },
            "objective": {
                "first_touch": "Initial outreach to a target with no assumed prior conversation.",
                "follow_up": "Follow-up content after a previous touch or known context.",
                "revive_stalled": "Re-engagement content for a stalled opportunity or dormant target.",
            },
            "channel": {
                "email": "Email-ready draft content.",
                "linkedin": "Shorter social outreach draft.",
                "call_follow_up": "Talk-track or call follow-up draft.",
            },
        },
        "business_effects": {
            "produces": ["content.summary", "content.draft"],
            "does_not_produce": ["external_dispatch"],
        },
        "app_boundaries": {
            "unsupported_effects": ["external_dispatch"],
        },
    },
    "gtm.prepare_reassignment_plan": {
        "result_display": {
            "primary_fields": ["preview", "approval_request_id", "rationale"],
            "style": "Show reassignment impact and approval status before details.",
        },
        "app_boundaries": {
            "guidance": "This capability prepares a plan for approval; it does not perform reassignment.",
        },
    },
    "gtm.prepare_followup_tasks": {
        "result_display": {
            "primary_fields": ["preview", "approval_request_id", "rationale"],
            "style": "Show task preview, approval requirement, and bounded cohort evidence.",
        },
        "app_boundaries": {
            "guidance": "This capability prepares task previews for approval; it does not create tasks or contact customers.",
        },
    },
}

SELECTION_HINTS = [
    {
        "capability": "gtm.account_risk_summary",
        "all_terms": ["at-risk", "accounts"],
        "any_terms": ["top", "rank", "ranked", "highest risk", "risk"],
        "exclude_terms": [
            "approve",
            "create",
            "draft",
            "email",
            "follow-up",
            "followup",
            "generate",
            "message",
            "prepare",
            "send",
            "task",
            "tasks",
            "write",
        ],
        "lock_capability": True,
    },
    {
        "capability": "gtm.lookalike_accounts",
        "all_terms": ["lookalike"],
        "any_terms": ["draft", "outreach", "best match"],
        "lock_capability": True,
    },
    {
        "capability": "gtm.lookalike_accounts",
        "all_terms": ["accounts"],
        "any_terms": ["resemble", "resembles", "similar", "similar to"],
        "lock_capability": True,
    },
    {
        "capability": "gtm.score_leads",
        "all_terms": ["score", "without routing"],
        "any_terms": ["inbound", "webinar"],
    },
    {
        "capability": "gtm.route_leads",
        "all_terms": ["score", "route"],
        "any_terms": ["inbound", "lead", "leads", "sales", "sdr"],
        "exclude_terms": ["expansion_candidates_q2", "at_risk_q2", "account cohort"],
        "lock_capability": True,
    },
    {
        "capability": "gtm.route_leads",
        "all_terms": ["follow-up"],
        "any_terms": ["account executive", "ae", "sales", "lead", "leads"],
        "exclude_terms": ["draft", "write", "generate", "send", "email", "message", "content", "linkedin"],
        "lock_capability": True,
    },
    {
        "capability": "gtm.prioritized_outreach_draft",
        "all_terms": ["prioritize", "draft"],
        "any_terms": ["at_risk_q2", "expansion_candidates_q2"],
    },
    {
        "capability": "gtm.prioritized_outreach_draft",
        "all_terms": ["draft"],
        "any_terms": ["at_risk_q2", "expansion_candidates_q2"],
    },
    {
        "capability": "gtm.bottleneck_account_outreach_draft",
        "all_terms": ["enrich", "draft"],
        "any_terms": ["at-risk", "risk", "bottleneck"],
        "exclude_terms": ["prioritize at_risk_q2", "prioritize expansion_candidates_q2"],
    },
]

RUNTIME_CUSTOMIZATION = {
    "preflight_denial_rules": [
        {
            "id": "gtm-explicit-out-of-scope-boundary",
            "type": "term_boundary",
            "applies_when": {
                "any_terms": ["outside my scope", "outside my allowed scope", "outside my actor scope"],
            },
            "detail": "The request explicitly asks for work outside the current actor scope.",
            "rationale": "The user supplied a disallowed actor boundary, so the app must deny before asking the service to clarify missing inputs.",
            "user_message": "I cannot process requests that are explicitly outside your allowed scope.",
        },
    ],
}

GTM_SCOPE_VALUES = ("East", "West", "Central", "North", "South", "company")


def _selected_capability_metadata(plan: dict[str, Any], metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    capability = str(plan.get("selected_capability") or "")
    selected = metadata.get(capability)
    return selected if isinstance(selected, dict) else {}


def _capability_accepts_input(capability_metadata: dict[str, Any], input_name: str) -> bool:
    specs = capability_metadata.get("input_specs")
    if not isinstance(specs, list):
        return False
    return any(isinstance(item, dict) and item.get("name") == input_name for item in specs)


def _extract_gtm_owner_scope(conversation: str) -> str | None:
    """GTM showcase-specific scope lookup.

    The generic ANIP runtime should not know GTM region vocabulary or business
    nouns. A real deployment would usually resolve this through an actor/scope
    catalog or search-backed resolver; the showcase keeps a small explicit
    scope vocabulary here to make that customization boundary visible.
    """

    raw = str(conversation or "")
    for scope in GTM_SCOPE_VALUES:
        escaped = re.escape(scope)
        patterns = [
            rf"\b(?:my\s+|our\s+|the\s+)?{escaped}[-\s]+(?:region|territory|office|scope|accounts|opportunities|pipeline|forecast|stage|bottlenecks?)\b",
            rf"\b(?:for|in|within|under|across)\s+(?:my\s+|our\s+|the\s+)?{escaped}\s+(?:region|territory|office|scope|accounts|opportunities|pipeline|forecast|stage|bottlenecks?)\b",
            rf"\b(?:region|territory|office|scope)\s+(?:of|=|:)\s*(?:my\s+|our\s+|the\s+)?{escaped}\b",
            rf"\b(?:my\s+|our\s+|the\s+)?{escaped}\s+(?:region|territory|office|scope|accounts|opportunities|pipeline|forecast|stage|bottlenecks?)\b",
            rf"\b(?:my\s+|our\s+|the\s+)?{escaped}\s+(?:Q[1-4]\s*(?:19|20)\d{{2}}|(?:19|20)\d{{2}}\s*[-_/ ]?\s*Q[1-4])\s+(?:accounts|opportunities|pipeline|forecast|stage|bottlenecks?)\b",
            rf"\b(?:for|in|within|under|across)\s+(?:my\s+|our\s+|the\s+)?{escaped}\b",
        ]
        if any(re.search(pattern, raw, flags=re.IGNORECASE) for pattern in patterns):
            return scope
    return None


def _gtm_requests_raw_financial_detail(conversation: str) -> bool:
    return bool(re.search(r"\bfull\s+(?:financial|numeric|record)\s+details?\b", str(conversation or ""), flags=re.IGNORECASE))


def _gtm_priority_list_reference_is_vague(conversation: str) -> bool:
    raw = str(conversation or "")
    return bool(re.search(r"\bpriority\s+list\b", raw, flags=re.IGNORECASE)) and not re.search(
        r"\b(?:at_risk_q2|expansion_candidates_q2|inbound_last_week|webinar_q2)\b",
        raw,
        flags=re.IGNORECASE,
    )


def _gtm_plan_uses_declared_values(selected: dict[str, Any], params: dict[str, Any]) -> bool:
    """Guard against planner self-contradictions after it selected a valid GTM capability."""
    input_specs = selected.get("input_specs") if isinstance(selected.get("input_specs"), list) else []
    specs_by_name = {str(spec.get("name") or ""): spec for spec in input_specs if isinstance(spec, dict)}
    for name, value in params.items():
        spec = specs_by_name.get(str(name))
        if not spec:
            continue
        allowed_values = spec.get("allowed_values")
        if isinstance(allowed_values, list) and allowed_values and str(value) not in {str(item) for item in allowed_values}:
            return False
    return True


def normalize_plan_for_app(
    *,
    plan: dict[str, Any],
    conversation: str,
    metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Apply GTM app-language bindings after generic ANIP normalization."""

    selected = _selected_capability_metadata(plan, metadata)
    params = plan.get("parameters")
    if not isinstance(params, dict):
        params = {}
        plan["parameters"] = params

    if _capability_accepts_input(selected, "owner_scope") and not params.get("owner_scope"):
        owner_scope = _extract_gtm_owner_scope(conversation)
        if owner_scope:
            params["owner_scope"] = owner_scope

    if str(plan.get("selected_capability") or "") == "gtm.prioritized_outreach_draft" and _gtm_priority_list_reference_is_vague(conversation):
        params.pop("cohort_ref", None)

    if str(plan.get("selected_capability") or "") == "gtm.prioritize_accounts" and _gtm_plan_uses_declared_values(selected, params):
        plan["unsupported"] = False
        plan["unsupported_reason"] = None

    effects = selected.get("business_effects")
    produces = set(effects.get("produces") or []) if isinstance(effects, dict) else set()
    does_not_produce = set(effects.get("does_not_produce") or []) if isinstance(effects, dict) else set()
    if _gtm_requests_raw_financial_detail(conversation) and (
        "raw_data_export" in does_not_produce or "raw_data_export" not in produces
    ):
        plan["unsupported"] = True
        plan["unsupported_reason"] = "The selected GTM capability does not support full raw financial detail export."

    return plan

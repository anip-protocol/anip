from __future__ import annotations

from typing import Any

from .shared import (
    EvalResult,
    _common_lineage_surfaces,
    _common_multi_service_surfaces,
    _extract_proposal_surfaces,
    _is_multi_service,
    append_unique,
    get_path,
)


def _evaluate_over_budget_safety_obligations(
    req: dict[str, Any],
    proposal: dict[str, Any],
    scenario: dict[str, Any],
    handled: list[str],
    glue: list[str],
    glue_category: list[str],
    why: list[str],
    improve: list[str],
) -> str:
    context = scenario["context"]
    expected_support = set(scenario.get("expected_anip_support", []))
    permissions = req.get("permissions", {})
    business_constraints = req.get("business_constraints", {})
    psurfaces = proposal.get("declared_surfaces", {})
    high_risk = context.get("risk") == "high"

    numeric_cost = context.get("selected_cost", context.get("expected_cost"))
    numeric_budget = context.get("budget_limit", context.get("caller_budget"))
    over_budget = (
        isinstance(numeric_cost, (int, float))
        and isinstance(numeric_budget, (int, float))
        and numeric_cost > numeric_budget
    )
    if not over_budget:
        return "HANDLED"

    why.append("the scenario presents an explicit over-budget decision before action")

    budget_control_required = bool(
        over_budget
        or business_constraints.get("over_budget_actions_must_not_execute")
        or business_constraints.get("booking_budget_limit_required")
        or business_constraints.get("spending_possible")
    )
    budget_control_supported = bool(psurfaces.get("budget_enforcement"))

    blocked_outcome_supported = bool(
        permissions.get("preflight_discovery")
        or "structured_failure" in expected_support
    )

    escalation_required = bool(
        business_constraints.get("blocked_actions_should_escalate_cleanly")
        or business_constraints.get("blocked_high_risk_actions_should_escalate_cleanly")
        or (high_risk and business_constraints.get("approval_expected_for_high_risk"))
    )
    escalation_supported = bool(
        psurfaces.get("authority_posture")
        or psurfaces.get("recovery_class")
    )

    missing_required = False

    if budget_control_required:
        if budget_control_supported:
            append_unique(handled, "budget enforcement for over-budget action blocking")
            why.append(
                "the approach declares budget_enforcement for the budget-sensitive action path"
            )
        else:
            missing_required = True
            glue.append(
                "you will still write budget-control enforcement here because the "
                "approach does not declare budget_enforcement for an over-budget path"
            )
            append_unique(glue_category, "safety")
            if _is_multi_service(req, proposal):
                glue.append(
                    "you will still write service-level handoff or routing logic so the budget block is applied consistently across the multi-service path"
                )
                append_unique(glue_category, "orchestration")
            improve.append(
                "declare budget_enforcement so over-budget blocking is visible in the runtime control surface"
            )
    elif budget_control_supported:
        append_unique(handled, "budget-aware control surface")

    if blocked_outcome_supported:
        append_unique(handled, "structured blocked over-budget outcome")
    else:
        improve.append(
            "expose over-budget refusal through structured failure or preflight discovery"
        )

    if escalation_required:
        if escalation_supported:
            append_unique(handled, "escalation posture for blocked budget conflicts")
            why.append(
                "the artifact set requires escalation and the approach declares authority or recovery posture"
            )
        else:
            missing_required = True
            glue.append(
                "you will still write blocked-action escalation routing here because the "
                "requirements require escalation but the approach does not declare authority_posture or recovery_class"
            )
            append_unique(glue_category, "orchestration")
            improve.append(
                "declare authority_posture or recovery_class when blocked budget conflicts must escalate cleanly"
            )
    else:
        improve.append(
            "if the organization requires human approval or replanning for over-budget actions, declare that expectation explicitly"
        )

    return "PARTIAL" if missing_required else "HANDLED"


def evaluate_safety(
    req: dict[str, Any],
    proposal: dict[str, Any],
    scenario: dict[str, Any],
) -> EvalResult:
    context = scenario["context"]
    expected_support = set(scenario.get("expected_anip_support", []))

    handled: list[str] = []
    glue: list[str] = []
    glue_category: list[str] = []
    why: list[str] = []
    improve: list[str] = []
    result = "HANDLED"

    _common_lineage_surfaces(req, handled, why, expected_support)
    _common_multi_service_surfaces(req, proposal, handled, why)

    permissions = req.get("permissions", {})
    permissions_state = context.get("permissions_state")
    high_risk = context.get("risk") == "high"
    side_effect = context.get("side_effect") or context.get("side_effect_service_b")

    if permissions_state == "denied":
        why.append("the core scenario is safe refusal rather than successful execution")
        if permissions.get("preflight_discovery"):
            append_unique(handled, "blocked-action refusal before blind execution")
        if side_effect == "irreversible" or high_risk:
            append_unique(handled, "high-risk action understanding")
        if get_path(req, "business_constraints", "blocked_high_risk_actions_should_escalate_cleanly", default=False):
            append_unique(handled, "escalation-friendly recovery guidance")
        glue.append(
            "you may still write organization-specific approval workflow integration here"
        )
        append_unique(glue_category, "orchestration")
        improve.extend([
            "add approval-aware declarations",
            "strengthen escalation vocabulary",
            "integrate more tightly with external approval systems",
        ])
        result = "HANDLED"

    budget_result = _evaluate_over_budget_safety_obligations(
        req,
        proposal,
        scenario,
        handled,
        glue,
        glue_category,
        why,
        improve,
    )
    if budget_result == "PARTIAL":
        result = "PARTIAL"

    auth = req.get("auth", {})
    if auth.get("purpose_binding"):
        append_unique(handled, "purpose binding")
    if auth.get("scoped_authority"):
        append_unique(handled, "scoped authority")

    business_constraints = req.get("business_constraints", {})
    if business_constraints.get("over_budget_actions_must_not_execute"):
        why.append("business constraint: over-budget actions must not execute")
    if business_constraints.get("production_cluster_deletion_requires_strong_authority"):
        why.append("business constraint: production cluster deletion requires strong authority")

    if permissions.get("grantable_requirements"):
        append_unique(handled, "grantable requirements visibility")

    bc = req.get("business_constraints", {})
    psurfaces = proposal.get("declared_surfaces", {})

    if bc.get("spending_possible"):
        if context.get("expected_cost") is not None or context.get("budget_limit") is not None:
            if psurfaces.get("budget_enforcement"):
                append_unique(handled, "budget enforcement for spending-possible system")
            else:
                improve.append("declare budget_enforcement surface for spending-possible system")

    if bc.get("approval_expected_for_high_risk"):
        if psurfaces.get("authority_posture"):
            append_unique(handled, "authority posture for high-risk approval expectations")
        else:
            improve.append("declare authority_posture surface for approval-expected system")

    if bc.get("cost_visibility_required"):
        if psurfaces.get("budget_enforcement"):
            append_unique(handled, "cost visibility via budget enforcement")
        else:
            improve.append("declare budget_enforcement surface for cost-visibility-required system")

    if result != "HANDLED" and not glue:
        result = "PARTIAL"
        glue.append("you will still write some scenario-specific safety control logic here")

    if result == "HANDLED" and not why:
        why.append(
            "the core scenario behavior is already covered by ANIP-visible "
            "semantics and expected runtime components"
        )
    if not improve:
        improve.append("no major protocol changes are required for this scenario")

    return handled, glue, glue_category, why, improve, result


def evaluate_orchestration(
    req: dict[str, Any],
    proposal: dict[str, Any],
    scenario: dict[str, Any],
) -> EvalResult:
    context = scenario["context"]
    expected_support = set(scenario.get("expected_anip_support", []))

    handled: list[str] = []
    glue: list[str] = []
    glue_category: list[str] = []
    why: list[str] = []
    improve: list[str] = []
    result = "PARTIAL"

    _common_lineage_surfaces(req, handled, why, expected_support)
    _common_multi_service_surfaces(req, proposal, handled, why)

    psurfaces = _extract_proposal_surfaces(proposal)
    advisory_surfaces: list[str] = []
    missing_surfaces: list[str] = []

    if "refresh_path_guidance" in expected_support or "cross_service_refresh_guidance" in expected_support:
        if psurfaces["refresh_via"]:
            advisory_surfaces.append("refresh_via hint")
            append_unique(handled, "refresh path guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("refresh advisory hint")

    if "verification_path_guidance" in expected_support or "cross_service_verification_guidance" in expected_support:
        if psurfaces["verify_via"]:
            advisory_surfaces.append("verify_via hint")
            append_unique(handled, "verification path guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("verify advisory hint")

    if "follow_up_guidance" in expected_support:
        if psurfaces["followup"]:
            advisory_surfaces.append("followup_via hint")
            append_unique(handled, "follow-up path guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("follow-up advisory hint")

    if "cross_service_handoff_guidance" in expected_support:
        if psurfaces["cross_service_hints"]:
            advisory_surfaces.append("cross-service handoff hint")
            append_unique(handled, "cross-service handoff guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("cross-service handoff hint")

    if "recovery_class" in expected_support:
        if psurfaces["recovery_class"]:
            advisory_surfaces.append("recovery_class")
            append_unique(handled, "recovery class guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("recovery_class")

    if "binding_freshness_visibility" in expected_support:
        if psurfaces["binding"]:
            advisory_surfaces.append("binding freshness visibility")
            append_unique(handled, "binding freshness visibility (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("binding freshness visibility")

    if "estimated_availability_support" in expected_support:
        if psurfaces["availability"]:
            advisory_surfaces.append("estimated availability hint")
            append_unique(handled, "estimated availability guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("estimated availability hint")

    if "revalidation_guidance" in expected_support:
        if psurfaces["revalidation"]:
            advisory_surfaces.append("revalidation guidance hint")
            append_unique(handled, "revalidation guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("revalidation guidance hint")

    if "resolution_guidance" in expected_support:
        append_unique(handled, "resolution guidance")

    if advisory_surfaces:
        why.append(
            "the protocol hints but does not enforce — advisory surfaces "
            f"({', '.join(advisory_surfaces)}) improve the decision surface "
            "but wrapper logic must still act on them"
        )
        result = "PARTIAL"
        glue.append(
            "the protocol provides advisory guidance but enforcement still "
            "requires wrapper logic"
        )
        append_unique(glue_category, "orchestration")
    else:
        why.append(
            "no advisory orchestration surfaces detected — core behavior "
            "depends on protocol-visible semantics"
        )

    if missing_surfaces:
        glue.append(
            "the approach does not declare "
            f"{', '.join(missing_surfaces)} — agents must discover these "
            "paths through docs or wrapper logic"
        )
        append_unique(glue_category, "orchestration")

    if _is_multi_service(req, proposal):
        glue.append(
            "you will still write cross-service handoff orchestration logic "
            "to act on advisory hints"
        )
        append_unique(glue_category, "orchestration")

    numeric_cost = context.get("selected_cost", context.get("expected_cost"))
    numeric_budget = context.get("budget_limit", context.get("caller_budget"))
    over_budget = (
        isinstance(numeric_cost, (int, float))
        and isinstance(numeric_budget, (int, float))
        and numeric_cost > numeric_budget
    )
    if over_budget:
        result = "PARTIAL"
        why.append(
            "the budget-control requirement is still not encoded as an "
            "enforceable ANIP-visible control surface"
        )
        glue.append(
            "you will still write budget-enforcement logic because the "
            "constraint is not yet enforced through delegation or permissions"
        )
        append_unique(glue_category, "safety")
        improve.append(
            "represent budget as enforceable authority or policy in the booking path"
        )

    if not glue:
        glue.append(
            "you will still write some orchestration wrapper logic here"
        )
        append_unique(glue_category, "orchestration")

    if not improve:
        improve.append(
            "promote advisory orchestration hints to enforceable protocol surfaces"
        )

    return handled, glue, glue_category, why, improve, result


def evaluate_cross_service(
    req: dict[str, Any],
    proposal: dict[str, Any],
    scenario: dict[str, Any],
) -> EvalResult:
    context = scenario["context"]
    expected_support = set(scenario.get("expected_anip_support", []))

    handled: list[str] = []
    glue: list[str] = []
    glue_category: list[str] = []
    why: list[str] = []
    improve: list[str] = []
    result = "PARTIAL"

    _common_lineage_surfaces(req, handled, why, expected_support)
    _common_multi_service_surfaces(req, proposal, handled, why)

    psurfaces = _extract_proposal_surfaces(proposal)
    lineage = req.get("lineage", {})

    if lineage.get("cross_service_continuity_required"):
        append_unique(handled, "cross-service continuity (task_id + parent_invocation_id)")

    if context.get("upstream_service") or context.get("planning_service_capability"):
        append_unique(handled, "upstream service reference in context")

    advisory_surfaces: list[str] = []
    missing_surfaces: list[str] = []

    if "cross_service_handoff_guidance" in expected_support:
        if psurfaces["cross_service_hints"]:
            advisory_surfaces.append("handoff_to hint")
            append_unique(handled, "cross-service handoff guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("cross-service handoff hint")

    if "cross_service_refresh_guidance" in expected_support:
        if psurfaces["refresh_via"]:
            advisory_surfaces.append("refresh_via hint")
            append_unique(handled, "cross-service refresh guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("cross-service refresh hint")

    if "cross_service_verification_guidance" in expected_support:
        if psurfaces["verify_via"]:
            advisory_surfaces.append("verify_via hint")
            append_unique(handled, "cross-service verification guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("cross-service verification hint")

    if "cross_service_reconstruction_guidance" in expected_support:
        if psurfaces["audit"]:
            advisory_surfaces.append("cross-service reconstruction hint")
            append_unique(handled, "cross-service reconstruction guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("cross-service reconstruction hint")

    if "follow_up_guidance" in expected_support:
        if psurfaces["followup"]:
            advisory_surfaces.append("followup_via hint")
            append_unique(handled, "follow-up guidance (protocol-assisted, advisory, not enforced)")
        else:
            missing_surfaces.append("follow-up hint")

    audit = req.get("audit", {})
    if audit.get("cross_service_reconstruction_required") and audit.get("durable") and audit.get("searchable"):
        append_unique(handled, "cross-service audit reconstruction primitives")
        why.append(
            "durable searchable audit with cross-service reconstruction "
            "requirement provides reconstruction primitives"
        )

    if advisory_surfaces:
        why.append(
            "the protocol provides advisory cross-service hints "
            f"({', '.join(advisory_surfaces)}) but does not enforce them"
        )
        result = "PARTIAL"
        glue.append(
            "the protocol provides advisory guidance but enforcement still "
            "requires wrapper logic"
        )
        append_unique(glue_category, "cross_service")
    else:
        why.append(
            "cross-service lineage primitives (task_id, parent_invocation_id) "
            "are present but higher-level handoff semantics are not enforced"
        )

    if missing_surfaces:
        glue.append(
            "the approach does not declare "
            f"{', '.join(missing_surfaces)} — agents must discover these "
            "paths through docs or wrapper logic"
        )
        append_unique(glue_category, "cross_service")

    glue.append(
        "you will still write cross-service orchestration and handoff "
        "logic to act on advisory protocol hints"
    )
    append_unique(glue_category, "orchestration")

    if not improve:
        improve.append(
            "promote cross-service advisory hints to enforceable protocol surfaces"
        )
        improve.append(
            "add structured cross-service handoff semantics beyond lineage propagation"
        )

    return handled, glue, glue_category, why, improve, result


def evaluate_observability(
    req: dict[str, Any],
    proposal: dict[str, Any],
    scenario: dict[str, Any],
) -> EvalResult:
    expected_support = set(scenario.get("expected_anip_support", []))

    handled: list[str] = []
    glue: list[str] = []
    glue_category: list[str] = []
    why: list[str] = []
    improve: list[str] = []
    result = "PARTIAL"

    _common_lineage_surfaces(req, handled, why, expected_support)
    _common_multi_service_surfaces(req, proposal, handled, why)

    audit = req.get("audit", {})
    lineage = req.get("lineage", {})

    if audit.get("durable"):
        append_unique(handled, "durable audit")
    if audit.get("searchable"):
        append_unique(handled, "searchable audit")

    if lineage.get("task_id"):
        append_unique(handled, "task identity")
    if lineage.get("parent_invocation_id"):
        append_unique(handled, "parent invocation lineage")

    needs_reconstruction = (
        "cross_service_reconstruction_guidance" in expected_support
        or audit.get("cross_service_reconstruction_required")
        or lineage.get("cross_service_continuity_required")
    )

    if needs_reconstruction:
        if lineage.get("cross_service_continuity_required"):
            append_unique(handled, "cross-service continuity primitives (task_id + parent_invocation_id)")

        if "cross_service_reconstruction_guidance" in expected_support:
            append_unique(handled, "cross-service reconstruction guidance (protocol-assisted, advisory, not enforced)")
            why.append(
                "the protocol provides lineage primitives and advisory "
                "reconstruction hints but does not enforce cross-service "
                "reconstruction"
            )
        else:
            why.append(
                "the protocol provides lineage primitives but cross-service "
                "reconstruction still requires operator-side aggregation"
            )

        result = "PARTIAL"
        glue.append(
            "you will still write cross-service audit aggregation or "
            "reconstruction logic here"
        )
        append_unique(glue_category, "observability")
        improve.append(
            "add structured cross-service reconstruction support beyond raw lineage primitives"
        )
    else:
        why.append(
            "lineage primitives (task_id, parent_invocation_id) and durable "
            "audit cover single-service observability needs"
        )

    if not glue:
        glue.append(
            "you may still write custom observability views or dashboards here"
        )
        append_unique(glue_category, "observability")

    if not improve:
        improve.append(
            "add richer operator query surfaces for audit reconstruction"
        )

    return handled, glue, glue_category, why, improve, result


def evaluate_recovery(
    req: dict[str, Any],
    proposal: dict[str, Any],
    scenario: dict[str, Any],
) -> EvalResult:
    expected_support = set(scenario.get("expected_anip_support", []))

    handled: list[str] = []
    glue: list[str] = []
    glue_category: list[str] = []
    why: list[str] = []
    improve: list[str] = []
    result = "PARTIAL"

    _common_lineage_surfaces(req, handled, why, expected_support)
    _common_multi_service_surfaces(req, proposal, handled, why)

    advisory_surfaces: list[str] = []

    if "recovery_class" in expected_support:
        advisory_surfaces.append("recovery_class")
        append_unique(handled, "recovery class guidance (protocol-assisted, advisory, not enforced)")

    if "resolution_guidance" in expected_support:
        advisory_surfaces.append("resolution guidance")
        append_unique(handled, "resolution guidance (protocol-assisted, advisory, not enforced)")

    if "refresh_path_guidance" in expected_support or "cross_service_refresh_guidance" in expected_support:
        advisory_surfaces.append("refresh_via hint")
        append_unique(handled, "refresh path guidance (protocol-assisted, advisory, not enforced)")

    if "verification_path_guidance" in expected_support or "cross_service_verification_guidance" in expected_support:
        advisory_surfaces.append("verify_via hint")
        append_unique(handled, "verification path guidance (protocol-assisted, advisory, not enforced)")

    if "revalidation_guidance" in expected_support:
        advisory_surfaces.append("revalidation guidance")
        append_unique(handled, "revalidation guidance (protocol-assisted, advisory, not enforced)")

    if "estimated_availability_support" in expected_support:
        advisory_surfaces.append("estimated availability hint")
        append_unique(handled, "estimated availability guidance (protocol-assisted, advisory, not enforced)")

    if advisory_surfaces:
        why.append(
            "recovery depends on advisory hints "
            f"({', '.join(advisory_surfaces)}) — the protocol hints but "
            "does not enforce recovery behavior"
        )
        result = "PARTIAL"
        glue.append(
            "the protocol provides advisory guidance but enforcement still "
            "requires wrapper logic"
        )
        append_unique(glue_category, "orchestration")
    else:
        why.append(
            "no advisory recovery surfaces detected — limited protocol "
            "guidance for recovery paths"
        )

    bc = req.get("business_constraints", {})
    psurfaces = proposal.get("declared_surfaces", {})

    if bc.get("recovery_sensitive"):
        if psurfaces.get("recovery_class"):
            append_unique(handled, "recovery class guidance for recovery-sensitive system")
        else:
            improve.append("declare recovery_class surface for recovery-sensitive system")

    posture = bc.get("blocked_failure_posture")
    if posture and posture != "not_specified":
        if psurfaces.get("recovery_class"):
            append_unique(handled, f"recovery class aligns with declared failure posture ({posture})")
        else:
            improve.append(f"declare recovery_class surface for system with {posture} failure posture")

    if not glue:
        glue.append(
            "you will still write recovery orchestration logic here"
        )
        append_unique(glue_category, "orchestration")

    if not improve:
        improve.append(
            "promote recovery advisory hints to enforceable protocol surfaces"
        )

    return handled, glue, glue_category, why, improve, result


def evaluate_generic(
    req: dict[str, Any],
    proposal: dict[str, Any],
    scenario: dict[str, Any],
) -> EvalResult:
    expected_support = set(scenario.get("expected_anip_support", []))

    handled: list[str] = []
    glue: list[str] = []
    glue_category: list[str] = []
    why: list[str] = []
    improve: list[str] = []
    result = "PARTIAL"

    _common_lineage_surfaces(req, handled, why, expected_support)
    _common_multi_service_surfaces(req, proposal, handled, why)

    why.append(
        "unknown scenario category — defaulting to conservative evaluation"
    )
    glue.append(
        "you will still write scenario-specific control logic here (category not recognized by evaluator)"
    )
    append_unique(glue_category, "orchestration")
    improve.append(
        "register this scenario category in the evaluator for more precise analysis"
    )

    return handled, glue, glue_category, why, improve, result


CATEGORY_EVALUATORS = {
    "safety": evaluate_safety,
    "recovery": evaluate_recovery,
    "orchestration": evaluate_orchestration,
    "cross_service": evaluate_cross_service,
    "observability": evaluate_observability,
}


def evaluate(
    requirements_doc: dict[str, Any],
    proposal_doc: dict[str, Any],
    scenario_doc: dict[str, Any],
) -> dict[str, Any]:
    req = requirements_doc
    proposal = proposal_doc["proposal"]
    scenario = scenario_doc["scenario"]
    category = scenario.get("category", "unknown")

    evaluator_fn = CATEGORY_EVALUATORS.get(category, evaluate_generic)
    handled, glue, glue_category, why, improve, result = evaluator_fn(req, proposal, scenario)

    return {
        "evaluation": {
            "scenario_name": scenario["name"],
            "result": result,
            "handled_by_anip": handled,
            "glue_you_will_still_write": glue,
            "glue_category": glue_category,
            "why": why,
            "what_would_improve": improve,
            "confidence": "high",
        }
    }

#!/usr/bin/env python3
"""Hardened ANIP Execution Scenario Validation runner.

Reads requirements/proposal/scenario YAML, validates them against the truth-layer
schemas, runs category-specific evaluation, and emits structured YAML plus a
markdown Glue Gap Analysis report.

Category dispatch:
  safety         -> evaluate_safety
  recovery       -> evaluate_recovery
  orchestration  -> evaluate_orchestration
  cross_service  -> evaluate_cross_service
  observability  -> evaluate_observability
  <unknown>      -> evaluate_generic  (conservative PARTIAL)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"

# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a mapping/object")
    return data


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_payload(payload: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    lines = [f"{schema_path.name} validation failed:"]
    for error in errors:
        path = ".".join(str(p) for p in error.absolute_path) or "<root>"
        lines.append(f"- {path}: {error.message}")
    raise ValueError("\n".join(lines))


# ---------------------------------------------------------------------------
# Traversal helpers (kept from v1)
# ---------------------------------------------------------------------------

def has_path(mapping: dict[str, Any], *keys: str) -> bool:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    return True


def get_path(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


# ---------------------------------------------------------------------------
# Shared surface detection helpers
# ---------------------------------------------------------------------------

EvalResult = tuple[
    list[str],  # handled
    list[str],  # glue
    list[str],  # glue_category
    list[str],  # why
    list[str],  # improve
    str,        # result
]


def _is_multi_service(req: dict[str, Any], proposal: dict[str, Any]) -> bool:
    if req.get("services") and isinstance(req["services"], list) and len(req["services"]) > 1:
        return True
    return proposal.get("recommended_shape") == "multi_service_estate"


def _common_lineage_surfaces(
    req: dict[str, Any],
    handled: list[str],
    why: list[str],
    expected_support: set[str],
) -> None:
    """Add lineage / audit / permission handled surfaces that are common across all categories."""
    permissions = req.get("permissions", {})
    audit = req.get("audit", {})
    lineage = req.get("lineage", {})

    if permissions.get("preflight_discovery") and "permission_discovery" in expected_support:
        append_unique(handled, "permission discovery")
    if lineage.get("task_id"):
        append_unique(handled, "task identity")
    if lineage.get("parent_invocation_id"):
        append_unique(handled, "parent invocation lineage")
    if audit.get("durable"):
        append_unique(handled, "durable audit")
    if audit.get("searchable") and "audit_queryability" in expected_support:
        append_unique(handled, "audit queryability")
    if "structured_failure" in expected_support:
        append_unique(handled, "structured failure")

    side_effect_required = (
        "side_effect_visibility" in expected_support
        or "irreversible_side_effect_visibility" in expected_support
    )
    if side_effect_required:
        append_unique(handled, "side-effect visibility")
    if "cost_visibility" in expected_support:
        append_unique(handled, "cost visibility")


def _extract_proposal_surfaces(proposal: dict[str, Any]) -> dict[str, bool]:
    """Extract which advisory surfaces the proposal actually declares.

    V3: When the proposal contains a structured `declared_surfaces` block,
    use it directly — mapping schema keys to the consumer key names that
    downstream evaluator code expects. This removes the V2 limitation where
    prose changes could change scores without a real design change.

    Fallback (V2): When `declared_surfaces` is absent, use heuristic text
    matching against proposal components, key_runtime_requirements, and
    rationale.
    """
    ds = proposal.get("declared_surfaces")
    if isinstance(ds, dict):
        # Structured path: map schema keys to consumer key names
        return {
            "budget_enforcement": bool(ds.get("budget_enforcement", False)),
            "binding": bool(ds.get("binding_requirements", False)),
            "authority_posture": bool(ds.get("authority_posture", False)),
            "recovery_class": bool(ds.get("recovery_class", False)),
            "refresh_via": bool(ds.get("refresh_via", False)),
            "verify_via": bool(ds.get("verify_via", False)),
            "followup": bool(ds.get("followup_via", False)),
            "cross_service_hints": bool(ds.get("cross_service_handoff", False)),
            "upstream_service": bool(ds.get("cross_service_continuity", False)),
            "cross_service_reconstruction": bool(ds.get("cross_service_reconstruction", False)),
            # Surfaces not in declared_surfaces schema — default false
            "audit": False,
            "lineage": False,
            "revalidation": False,
            "availability": False,
        }

    # V2 fallback: heuristic text matching
    proposal_components = set(
        proposal.get("required_components", [])
        + proposal.get("optional_components", [])
    )
    key_requirements = proposal.get("key_runtime_requirements", [])
    key_req_text = " ".join(key_requirements).lower()

    # Also include rationale and component names in the surface scan
    rationale_text = " ".join(proposal.get("rationale", [])).lower()
    component_text = " ".join(proposal_components).lower()
    all_text = key_req_text + " " + rationale_text + " " + component_text

    return {
        "refresh_via": (
            "refresh_via" in all_text
            or "refresh" in all_text
        ),
        "verify_via": (
            "verify_via" in all_text
            or "verif" in all_text
        ),
        "cross_service_hints": (
            "cross_service" in all_text
            or "cross-service" in all_text
            or "handoff" in all_text
        ),
        "recovery_class": (
            "recovery_class" in all_text
            or "recovery" in all_text
        ),
        "budget_enforcement": (
            "budget" in all_text
            or "constraints.budget" in all_text
        ),
        "binding": (
            "binding" in all_text
            or "requires_binding" in all_text
        ),
        "audit": (
            "audit" in all_text
        ),
        "lineage": (
            "lineage" in all_text
        ),
        "upstream_service": (
            "upstream" in all_text
            or "task_id" in all_text
            or "task identity" in all_text
        ),
        "followup": (
            "followup" in all_text
            or "follow-up" in all_text
            or "follow_up" in all_text
        ),
        "revalidation": (
            "revalidat" in all_text
        ),
        "availability": (
            "availability" in all_text
            or "unavailab" in all_text
        ),
    }


def _common_multi_service_surfaces(
    req: dict[str, Any],
    proposal: dict[str, Any],
    handled: list[str],
    why: list[str],
) -> None:
    """Add cross-service surfaces when req declares multiple services AND proposal declares them."""
    if not _is_multi_service(req, proposal):
        return

    surfaces = _extract_proposal_surfaces(proposal)

    # Only credit cross-service task identity if proposal declares lineage/task_id
    if surfaces["upstream_service"] or surfaces["lineage"]:
        append_unique(handled, "cross-service task identity continuity")

    # Only credit independent audit records if proposal declares audit
    if surfaces["audit"]:
        append_unique(handled, "independent but linkable audit records")

    # Only credit cleaner service handoff if proposal declares cross-service hints
    if surfaces["cross_service_hints"]:
        append_unique(handled, "cleaner service handoff")

    credited = [h for h in [
        "cross-service task identity continuity",
        "independent but linkable audit records",
        "cleaner service handoff",
    ] if h in handled]

    if credited:
        why.append(
            "the design already removes a large amount of cross-service "
            "correlation and trace-stitching glue"
        )


# ---------------------------------------------------------------------------
# Category evaluators
# ---------------------------------------------------------------------------

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

    # --- Permission denial path ---
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

    # --- Budget overrun path ---
    numeric_cost = context.get("selected_cost", context.get("expected_cost"))
    numeric_budget = context.get("budget_limit", context.get("caller_budget"))
    over_budget = (
        isinstance(numeric_cost, (int, float))
        and isinstance(numeric_budget, (int, float))
        and numeric_cost > numeric_budget
    )

    if over_budget:
        result = "PARTIAL"
        why.append("the design improves the decision surface substantially before action")
        why.append(
            "the budget-control requirement is still not encoded as an "
            "enforceable ANIP-visible control surface"
        )

        if _is_multi_service(req, proposal):
            glue.append(
                "you will still write budget-enforcement logic in the booking service, "
                "because the constraint is not yet enforced through delegation or permissions"
            )
            glue.append(
                "you will still write some organization-specific handoff policy logic here"
            )
            glue.append(
                "you may still write a cross-service audit aggregation layer here"
            )
            append_unique(glue_category, "safety")
            append_unique(glue_category, "orchestration")
            append_unique(glue_category, "observability")
            improve.extend([
                "represent budget as enforceable authority or policy in the booking path",
                "expose budget-based blocking through permissions or structured invoke failure",
                "add easier cross-service lineage query support for operators",
            ])
        else:
            glue.append(
                "you will still write budget-enforcement logic here unless the budget "
                "limit is represented in delegation, permission evaluation, or a "
                "protocol-visible control layer"
            )
            glue.append(
                "you will still write approval or escalation routing here if the "
                "organization requires a human to approve over-budget bookings"
            )
            glue.append(
                "you may still write comparison or replanning logic here if the agent "
                "must search for cheaper alternatives before escalation"
            )
            append_unique(glue_category, "safety")
            append_unique(glue_category, "orchestration")
            improve.extend([
                "represent budget as part of enforceable authority or purpose binding",
                "expose budget-based blocking in permission discovery or invoke failure semantics",
                "make the over-budget path explicit in the runtime control surface",
            ])

    # --- Binding requirements ---
    auth = req.get("auth", {})
    if auth.get("purpose_binding"):
        append_unique(handled, "purpose binding")
    if auth.get("scoped_authority"):
        append_unique(handled, "scoped authority")

    # --- Control requirements ---
    business_constraints = req.get("business_constraints", {})
    if business_constraints.get("over_budget_actions_must_not_execute"):
        why.append("business constraint: over-budget actions must not execute")
    if business_constraints.get("production_cluster_deletion_requires_strong_authority"):
        why.append("business constraint: production cluster deletion requires strong authority")

    # --- Non-delegable actions ---
    if permissions.get("grantable_requirements"):
        append_unique(handled, "grantable requirements visibility")

    # --- business_constraints alignment ---
    bc = req.get("business_constraints", {})
    psurfaces = proposal.get("declared_surfaces", {})

    # spending_possible: check budget_enforcement surface
    if bc.get("spending_possible"):
        if context.get("expected_cost") is not None or context.get("budget_limit") is not None:
            if psurfaces.get("budget_enforcement"):
                append_unique(handled, "budget enforcement for spending-possible system")
            else:
                improve.append("declare budget_enforcement surface for spending-possible system")

    # approval_expected_for_high_risk: check authority_posture surface
    if bc.get("approval_expected_for_high_risk"):
        if psurfaces.get("authority_posture"):
            append_unique(handled, "authority posture for high-risk approval expectations")
        else:
            improve.append("declare authority_posture surface for approval-expected system")

    # cost_visibility_required: check budget_enforcement surface (implies cost visibility)
    if bc.get("cost_visibility_required"):
        if psurfaces.get("budget_enforcement"):
            append_unique(handled, "cost visibility via budget enforcement")
        else:
            improve.append("declare budget_enforcement surface for cost-visibility-required system")

    # --- Normalize ---
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

    # --- Inspect proposal for actual declared surfaces ---
    psurfaces = _extract_proposal_surfaces(proposal)

    # --- Advisory composition hints (only credited when proposal declares them) ---
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

    # --- Recovery posture ---
    if "resolution_guidance" in expected_support:
        append_unique(handled, "resolution guidance")

    # KEY RULE: advisory-only surfaces score as PARTIAL, not HANDLED
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

    # --- Cross-service handoff hints ---
    if _is_multi_service(req, proposal):
        glue.append(
            "you will still write cross-service handoff orchestration logic "
            "to act on advisory hints"
        )
        append_unique(glue_category, "orchestration")

    # --- Budget overrun in orchestration context ---
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

    # --- Normalize ---
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

    # --- Inspect proposal for actual declared surfaces ---
    psurfaces = _extract_proposal_surfaces(proposal)

    lineage = req.get("lineage", {})

    # --- Cross-service continuity (enforceable) ---
    if lineage.get("cross_service_continuity_required"):
        append_unique(handled, "cross-service continuity (task_id + parent_invocation_id)")

    # --- upstream_service / task_id propagation ---
    if context.get("upstream_service") or context.get("planning_service_capability"):
        append_unique(handled, "upstream service reference in context")

    # --- Cross-service handoff block (advisory, gated by proposal) ---
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

    # --- Score reconstruction quality ---
    audit = req.get("audit", {})
    if audit.get("cross_service_reconstruction_required") and audit.get("durable") and audit.get("searchable"):
        append_unique(handled, "cross-service audit reconstruction primitives")
        why.append(
            "durable searchable audit with cross-service reconstruction "
            "requirement provides reconstruction primitives"
        )

    # Advisory cross-service hints -> PARTIAL
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

    audit = req.get("audit", {})
    lineage = req.get("lineage", {})

    # --- Audit (enforceable: durable, searchable) ---
    if audit.get("durable"):
        append_unique(handled, "durable audit")
    if audit.get("searchable"):
        append_unique(handled, "searchable audit")

    # --- Lineage (enforceable: task_id, parent_invocation_id) ---
    if lineage.get("task_id"):
        append_unique(handled, "task identity")
    if lineage.get("parent_invocation_id"):
        append_unique(handled, "parent invocation lineage")

    # --- Cross-service reconstruction ---
    needs_reconstruction = (
        "cross_service_reconstruction_guidance" in expected_support
        or audit.get("cross_service_reconstruction_required")
        or lineage.get("cross_service_continuity_required")
    )

    if needs_reconstruction:
        # Protocol provides lineage primitives but not enforcement of reconstruction
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
        # Single-service observability — lineage primitives may be sufficient
        why.append(
            "lineage primitives (task_id, parent_invocation_id) and durable "
            "audit cover single-service observability needs"
        )

    # --- Normalize ---
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

    advisory_surfaces: list[str] = []

    # --- recovery_class ---
    if "recovery_class" in expected_support:
        advisory_surfaces.append("recovery_class")
        append_unique(handled, "recovery class guidance (protocol-assisted, advisory, not enforced)")

    # --- resolution action vocabulary ---
    if "resolution_guidance" in expected_support:
        advisory_surfaces.append("resolution guidance")
        append_unique(handled, "resolution guidance (protocol-assisted, advisory, not enforced)")

    # --- refresh / verify paths ---
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

    # --- Advisory hints -> PARTIAL ---
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

    # --- business_constraints alignment ---
    bc = req.get("business_constraints", {})
    psurfaces = proposal.get("declared_surfaces", {})

    # recovery_sensitive: check recovery_class surface
    if bc.get("recovery_sensitive"):
        if psurfaces.get("recovery_class"):
            append_unique(handled, "recovery class guidance for recovery-sensitive system")
        else:
            improve.append("declare recovery_class surface for recovery-sensitive system")

    # blocked_failure_posture: check recovery_class surface
    posture = bc.get("blocked_failure_posture")
    if posture and posture != "not_specified":
        if psurfaces.get("recovery_class"):
            append_unique(handled, f"recovery class aligns with declared failure posture ({posture})")
        else:
            improve.append(f"declare recovery_class surface for system with {posture} failure posture")

    # --- Normalize ---
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
    """Conservative fallback for unknown scenario categories."""
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


# ---------------------------------------------------------------------------
# Category dispatch
# ---------------------------------------------------------------------------

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

    evaluation = {
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
    return evaluation


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def to_markdown(evaluation_doc: dict[str, Any]) -> str:
    ev = evaluation_doc["evaluation"]

    def bullets(items: list[str]) -> str:
        if not items:
            return "- none"
        return "\n".join(f"- {item}" for item in items)

    return f"""# Evaluation: {ev['scenario_name']}

Result: {ev['result']}

Handled by ANIP:
{bullets(ev['handled_by_anip'])}

Glue you will still write:
{bullets(ev['glue_you_will_still_write'])}

Glue category:
{bullets(ev['glue_category'])}

Why:
{bullets(ev['why'])}

What would improve the result:
{bullets(ev['what_would_improve'])}
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ANIP Execution Scenario Validation.")
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--evaluation-out", type=Path, help="Write structured evaluation YAML here.")
    parser.add_argument("--markdown-out", type=Path, help="Write markdown report here.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    requirements_doc = load_yaml(args.requirements)
    proposal_doc = load_yaml(args.proposal)
    scenario_doc = load_yaml(args.scenario)

    validate_payload(requirements_doc, SCHEMA_DIR / "requirements.schema.json")
    validate_payload(proposal_doc, SCHEMA_DIR / "proposal.schema.json")
    validate_payload(scenario_doc, SCHEMA_DIR / "scenario.schema.json")

    evaluation_doc = evaluate(requirements_doc, proposal_doc, scenario_doc)
    validate_payload(evaluation_doc, SCHEMA_DIR / "evaluation.schema.json")

    markdown = to_markdown(evaluation_doc)

    if args.evaluation_out:
        args.evaluation_out.parent.mkdir(parents=True, exist_ok=True)
        with args.evaluation_out.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(evaluation_doc, fh, sort_keys=False)

    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")

    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Regression tests for the hardened ANIP evaluator.

Tests cover:
  - Category dispatch routing
  - Safety scenario: budget overrun -> PARTIAL
  - Safety scenario: permission denied -> HANDLED
  - Orchestration scenario: advisory-only -> PARTIAL
  - Cross-service scenario: advisory-only -> PARTIAL
  - handled_by_anip surfaces
  - Glue item minimum length (concrete glue)
  - Unknown category falls back to generic -> PARTIAL
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the evaluator importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from anip_design_validate import (
    CATEGORY_EVALUATORS,
    evaluate,
    evaluate_safety,
    evaluate_recovery,
    evaluate_orchestration,
    evaluate_cross_service,
    evaluate_observability,
    evaluate_generic,
)


# ---------------------------------------------------------------------------
# Fixtures — minimal scenario/requirements/proposal docs for each test
# ---------------------------------------------------------------------------

def _make_requirements(
    *,
    preflight_discovery: bool = True,
    durable_audit: bool = True,
    searchable_audit: bool = True,
    task_id: bool = True,
    parent_invocation_id: bool = True,
    cross_service_continuity: bool = False,
    cross_service_reconstruction: bool = False,
    services: list | None = None,
    business_constraints: dict | None = None,
    purpose_binding: bool = True,
    scoped_authority: bool = True,
) -> dict:
    req: dict = {
        "system": {"name": "test-service", "domain": "test"},
        "transports": {"http": True, "stdio": False, "grpc": False},
        "trust": {"mode": "signed", "checkpoints": False},
        "auth": {
            "delegation_tokens": True,
            "purpose_binding": purpose_binding,
            "scoped_authority": scoped_authority,
        },
        "permissions": {
            "preflight_discovery": preflight_discovery,
            "restricted_vs_denied": True,
        },
        "audit": {
            "durable": durable_audit,
            "searchable": searchable_audit,
        },
        "lineage": {
            "invocation_id": True,
            "client_reference_id": True,
            "task_id": task_id,
            "parent_invocation_id": parent_invocation_id,
        },
        "scale": {"shape_preference": "production_single_service"},
    }
    if cross_service_continuity:
        req["lineage"]["cross_service_continuity_required"] = True
    if cross_service_reconstruction:
        req["audit"]["cross_service_reconstruction_required"] = True
    if services:
        req["services"] = services
    if business_constraints:
        req["business_constraints"] = business_constraints
    return req


def _make_proposal(
    *,
    shape: str = "production_single_service",
    required_components: list | None = None,
    optional_components: list | None = None,
    key_runtime_requirements: list | None = None,
    rationale: list | None = None,
    declared_surfaces: dict | None = None,
) -> dict:
    p: dict = {"recommended_shape": shape}
    if required_components is not None:
        p["required_components"] = required_components
    if optional_components is not None:
        p["optional_components"] = optional_components
    if key_runtime_requirements is not None:
        p["key_runtime_requirements"] = key_runtime_requirements
    if rationale is not None:
        p["rationale"] = rationale
    if declared_surfaces is not None:
        p["declared_surfaces"] = declared_surfaces
    return {"proposal": p}


def _make_scenario(
    *,
    name: str = "test_scenario",
    category: str = "safety",
    narrative: str = "A test scenario.",
    context: dict | None = None,
    expected_anip_support: list | None = None,
) -> dict:
    return {
        "scenario": {
            "name": name,
            "category": category,
            "narrative": narrative,
            "context": context or {},
            "expected_behavior": ["test_behavior"],
            "expected_anip_support": expected_anip_support or [],
        }
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCategoryDispatch:
    """test_category_dispatch_routes_correctly"""

    def test_safety_routes_to_evaluate_safety(self):
        assert CATEGORY_EVALUATORS["safety"] is evaluate_safety

    def test_recovery_routes_to_evaluate_recovery(self):
        assert CATEGORY_EVALUATORS["recovery"] is evaluate_recovery

    def test_orchestration_routes_to_evaluate_orchestration(self):
        assert CATEGORY_EVALUATORS["orchestration"] is evaluate_orchestration

    def test_cross_service_routes_to_evaluate_cross_service(self):
        assert CATEGORY_EVALUATORS["cross_service"] is evaluate_cross_service

    def test_observability_routes_to_evaluate_observability(self):
        assert CATEGORY_EVALUATORS["observability"] is evaluate_observability

    def test_all_five_categories_present(self):
        assert set(CATEGORY_EVALUATORS.keys()) == {
            "safety",
            "recovery",
            "orchestration",
            "cross_service",
            "observability",
        }


class TestSafetyBudgetOverrun:
    """test_safety_scenario_budget_overrun -> PARTIAL"""

    def test_budget_overrun_single_service(self):
        req = _make_requirements(
            business_constraints={
                "booking_budget_limit_required": True,
                "over_budget_actions_must_not_execute": True,
            },
        )
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="book_flight_over_budget",
            category="safety",
            context={
                "capability": "book_flight",
                "side_effect": "irreversible",
                "expected_cost": 800,
                "budget_limit": 500,
                "permissions_state": "available",
                "task_id": "trip-planning-q2",
            },
            expected_anip_support=[
                "cost_visibility",
                "side_effect_visibility",
                "structured_failure",
                "task_id_support",
                "parent_invocation_id_support",
                "audit_queryability",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        assert "safety" in ev["glue_category"]
        assert any("budget" in g.lower() for g in ev["glue_you_will_still_write"])

    def test_budget_overrun_multi_service(self):
        req = _make_requirements(
            services=[
                {"name": "search", "role": "planning"},
                {"name": "booking", "role": "execution"},
            ],
            cross_service_continuity=True,
        )
        proposal = _make_proposal(shape="multi_service_estate")
        scenario = _make_scenario(
            name="cross_service_budget_overrun",
            category="safety",
            context={
                "selected_cost": 800,
                "budget_limit": 500,
                "side_effect_service_b": "irreversible",
                "task_id": "trip-q2",
            },
            expected_anip_support=[
                "permission_discovery",
                "cost_visibility",
                "structured_failure",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        assert "safety" in ev["glue_category"]
        assert "orchestration" in ev["glue_category"]


class TestSafetyDenied:
    """test_safety_scenario_denied -> HANDLED"""

    def test_permission_denied(self):
        req = _make_requirements(
            business_constraints={
                "blocked_high_risk_actions_should_escalate_cleanly": True,
            },
        )
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="delete_without_permission",
            category="safety",
            context={
                "capability": "delete_cluster",
                "side_effect": "irreversible",
                "risk": "high",
                "permissions_state": "denied",
                "task_id": "incident-cleanup",
            },
            expected_anip_support=[
                "permission_discovery",
                "irreversible_side_effect_visibility",
                "structured_failure",
                "resolution_guidance",
                "task_id_support",
                "parent_invocation_id_support",
                "audit_queryability",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "HANDLED"
        assert "permission discovery" in ev["handled_by_anip"]
        assert "blocked-action refusal before blind execution" in ev["handled_by_anip"]
        assert "high-risk action understanding" in ev["handled_by_anip"]
        assert "escalation-friendly recovery guidance" in ev["handled_by_anip"]


class TestOrchestrationAdvisoryOnly:
    """test_orchestration_scenario_advisory_only -> PARTIAL"""

    def test_advisory_refresh_path(self):
        req = _make_requirements()
        proposal = _make_proposal(
            key_runtime_requirements=[
                "expose stale-binding failures with explicit recovery posture",
                "expose which capability typically refreshes stale quote state",
                "preserve task and parent invocation lineage through refresh loops",
            ],
        )
        scenario = _make_scenario(
            name="stale_quote_refresh",
            category="orchestration",
            context={
                "stale_capability": "book_flight",
                "refresh_capability": "search_flights",
                "side_effect": "irreversible",
                "task_id": "trip-refresh",
            },
            expected_anip_support=[
                "structured_failure",
                "recovery_class",
                "binding_freshness_visibility",
                "refresh_path_guidance",
                "task_id_support",
                "parent_invocation_id_support",
                "audit_queryability",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        assert "orchestration" in ev["glue_category"]
        # Advisory surfaces should be in handled but with advisory note
        advisory_handled = [h for h in ev["handled_by_anip"] if "advisory" in h]
        assert len(advisory_handled) > 0
        # Why should mention "hints but does not enforce"
        assert any("hints but does not enforce" in w for w in ev["why"])

    def test_advisory_not_credited_when_proposal_omits_surfaces(self):
        """When the proposal does not declare refresh/recovery surfaces,
        the evaluator should NOT credit them as handled."""
        req = _make_requirements()
        proposal = _make_proposal()  # bare proposal with no declared surfaces
        scenario = _make_scenario(
            name="stale_quote_refresh_bare",
            category="orchestration",
            context={
                "stale_capability": "book_flight",
                "refresh_capability": "search_flights",
                "side_effect": "irreversible",
                "task_id": "trip-refresh",
            },
            expected_anip_support=[
                "structured_failure",
                "recovery_class",
                "binding_freshness_visibility",
                "refresh_path_guidance",
                "task_id_support",
                "parent_invocation_id_support",
                "audit_queryability",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        # Advisory surfaces should NOT be in handled since proposal doesn't declare them
        advisory_handled = [h for h in ev["handled_by_anip"] if "advisory" in h]
        assert len(advisory_handled) == 0
        # Glue should mention that proposal doesn't declare the surfaces
        assert any("proposal does not declare" in g for g in ev["glue_you_will_still_write"])


class TestCrossServiceAdvisoryOnly:
    """test_cross_service_scenario_advisory_only -> PARTIAL"""

    def test_cross_service_handoff_advisory(self):
        req = _make_requirements(
            services=[
                {"name": "search", "role": "planning"},
                {"name": "booking", "role": "execution"},
            ],
            cross_service_continuity=True,
            cross_service_reconstruction=True,
        )
        proposal = _make_proposal(
            shape="multi_service_estate",
            required_components=[
                "handoff_propagation_rules",
                "durable_audit_store_per_service",
                "lineage_recorder_per_service",
            ],
            key_runtime_requirements=[
                "task identity should survive cross-service execution",
                "each service should remain independently auditable",
            ],
        )
        scenario = _make_scenario(
            name="quote_handoff",
            category="cross_service",
            context={
                "planning_service_capability": "search_flights",
                "execution_service_capability": "book_flight",
                "task_id": "trip-handoff",
            },
            expected_anip_support=[
                "task_id_support",
                "parent_invocation_id_support",
                "audit_queryability",
                "cross_service_handoff_guidance",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        # Advisory handoff hint should be noted
        assert any("advisory" in h for h in ev["handled_by_anip"])

    def test_cross_service_not_credited_when_proposal_omits_surfaces(self):
        """When proposal does not declare cross-service components,
        advisory hints should not be credited."""
        req = _make_requirements(
            services=[
                {"name": "search", "role": "planning"},
                {"name": "booking", "role": "execution"},
            ],
            cross_service_continuity=True,
            cross_service_reconstruction=True,
        )
        proposal = _make_proposal(shape="multi_service_estate")  # bare proposal
        scenario = _make_scenario(
            name="quote_handoff_bare",
            category="cross_service",
            context={
                "planning_service_capability": "search_flights",
                "execution_service_capability": "book_flight",
                "task_id": "trip-handoff",
            },
            expected_anip_support=[
                "task_id_support",
                "parent_invocation_id_support",
                "audit_queryability",
                "cross_service_handoff_guidance",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        # Advisory surfaces should NOT be credited
        advisory_handled = [h for h in ev["handled_by_anip"] if "advisory" in h]
        assert len(advisory_handled) == 0
        # Glue should note the missing proposal surfaces
        assert any("proposal does not declare" in g for g in ev["glue_you_will_still_write"])


class TestHandledByAnipSurfaces:
    """test_handled_by_anip_contains_expected_surfaces"""

    def test_permission_discovery_and_structured_failure(self):
        req = _make_requirements()
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="safety_test",
            category="safety",
            context={
                "permissions_state": "denied",
                "side_effect": "irreversible",
                "risk": "high",
            },
            expected_anip_support=[
                "permission_discovery",
                "structured_failure",
                "irreversible_side_effect_visibility",
                "task_id_support",
                "audit_queryability",
            ],
        )

        result = evaluate(req, proposal, scenario)
        handled = result["evaluation"]["handled_by_anip"]
        assert "permission discovery" in handled
        assert "structured failure" in handled
        assert "side-effect visibility" in handled
        assert "task identity" in handled
        assert "durable audit" in handled
        assert "audit queryability" in handled


class TestGlueItemsAreConcrete:
    """test_glue_items_are_concrete -> no glue item shorter than 20 chars"""

    def test_safety_glue_items_minimum_length(self):
        req = _make_requirements()
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="budget_overrun",
            category="safety",
            context={
                "expected_cost": 800,
                "budget_limit": 500,
                "permissions_state": "available",
            },
            expected_anip_support=["cost_visibility", "structured_failure"],
        )

        result = evaluate(req, proposal, scenario)
        for item in result["evaluation"]["glue_you_will_still_write"]:
            assert len(item) >= 20, f"Glue item too short: {item!r}"

    def test_orchestration_glue_items_minimum_length(self):
        req = _make_requirements()
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="orchestration_test",
            category="orchestration",
            context={"task_id": "test"},
            expected_anip_support=[
                "structured_failure",
                "recovery_class",
                "refresh_path_guidance",
                "task_id_support",
            ],
        )

        result = evaluate(req, proposal, scenario)
        for item in result["evaluation"]["glue_you_will_still_write"]:
            assert len(item) >= 20, f"Glue item too short: {item!r}"

    def test_cross_service_glue_items_minimum_length(self):
        req = _make_requirements(
            services=[
                {"name": "svc-a", "role": "planning"},
                {"name": "svc-b", "role": "execution"},
            ],
            cross_service_continuity=True,
        )
        proposal = _make_proposal(shape="multi_service_estate")
        scenario = _make_scenario(
            name="cross_service_test",
            category="cross_service",
            context={"task_id": "test"},
            expected_anip_support=[
                "task_id_support",
                "cross_service_handoff_guidance",
            ],
        )

        result = evaluate(req, proposal, scenario)
        for item in result["evaluation"]["glue_you_will_still_write"]:
            assert len(item) >= 20, f"Glue item too short: {item!r}"

    def test_observability_glue_items_minimum_length(self):
        req = _make_requirements(
            services=[
                {"name": "svc-a", "role": "execution"},
                {"name": "svc-b", "role": "followup"},
            ],
            cross_service_continuity=True,
            cross_service_reconstruction=True,
        )
        proposal = _make_proposal(shape="multi_service_estate")
        scenario = _make_scenario(
            name="observability_test",
            category="observability",
            context={"task_id": "test"},
            expected_anip_support=[
                "task_id_support",
                "parent_invocation_id_support",
                "audit_queryability",
                "cross_service_reconstruction_guidance",
            ],
        )

        result = evaluate(req, proposal, scenario)
        for item in result["evaluation"]["glue_you_will_still_write"]:
            assert len(item) >= 20, f"Glue item too short: {item!r}"

    def test_generic_glue_items_minimum_length(self):
        req = _make_requirements()
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="generic_test",
            category="unknown_category",
            context={"task_id": "test"},
            expected_anip_support=["task_id_support"],
        )

        result = evaluate(req, proposal, scenario)
        for item in result["evaluation"]["glue_you_will_still_write"]:
            assert len(item) >= 20, f"Glue item too short: {item!r}"


class TestUnknownCategoryFallback:
    """test_unknown_category_falls_back_to_generic -> PARTIAL with note"""

    def test_unknown_category(self):
        req = _make_requirements()
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="unknown_scenario",
            category="completely_new_category",
            context={"task_id": "test"},
            expected_anip_support=["task_id_support"],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        assert any(
            "unknown scenario category" in w and "conservative" in w
            for w in ev["why"]
        ), f"Expected conservative fallback note in why: {ev['why']}"

    def test_empty_category(self):
        req = _make_requirements()
        proposal = _make_proposal()
        scenario = _make_scenario(
            name="empty_category_scenario",
            category="",
            context={"task_id": "test"},
            expected_anip_support=["task_id_support"],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        assert ev["result"] == "PARTIAL"
        assert any("unknown scenario category" in w for w in ev["why"])


class TestDeclaredSurfaces:
    """Tests for V3 declared_surfaces structured surface declarations."""

    def test_declared_surfaces_preferred_over_text(self):
        """With declared_surfaces, result differs from text-only heuristic.

        A bare proposal with no text hints would NOT credit refresh_via or
        recovery_class via V2 heuristics. With declared_surfaces, those
        surfaces ARE credited.
        """
        req = _make_requirements()
        # Bare proposal — no text that would trigger V2 heuristics for refresh/recovery
        proposal_v2 = _make_proposal(
            required_components=["capability_registry"],
            rationale=["minimal design"],
        )
        # Same bare proposal but with declared_surfaces
        proposal_v3 = _make_proposal(
            required_components=["capability_registry"],
            rationale=["minimal design"],
            declared_surfaces={
                "refresh_via": True,
                "recovery_class": True,
            },
        )
        scenario = _make_scenario(
            name="declared_vs_text",
            category="orchestration",
            context={"task_id": "test"},
            expected_anip_support=[
                "refresh_path_guidance",
                "recovery_class",
            ],
        )

        result_v2 = evaluate(req, proposal_v2, scenario)
        result_v3 = evaluate(req, proposal_v3, scenario)

        # V2 (no text) should NOT credit advisory refresh or recovery
        v2_advisory = [h for h in result_v2["evaluation"]["handled_by_anip"] if "advisory" in h]
        assert len(v2_advisory) == 0, f"V2 should not credit advisory surfaces: {v2_advisory}"

        # V3 (declared_surfaces) SHOULD credit them
        v3_advisory = [h for h in result_v3["evaluation"]["handled_by_anip"] if "advisory" in h]
        assert len(v3_advisory) >= 2, f"V3 should credit advisory surfaces: {v3_advisory}"

    def test_declared_surfaces_false_produces_glue(self):
        """When refresh_via is declared false, the evaluator should produce
        glue noting the gap (proposal does not declare the surface)."""
        req = _make_requirements()
        proposal = _make_proposal(
            required_components=["capability_registry"],
            rationale=["minimal design"],
            declared_surfaces={
                "refresh_via": False,
            },
        )
        scenario = _make_scenario(
            name="false_refresh",
            category="orchestration",
            context={"task_id": "test"},
            expected_anip_support=[
                "refresh_path_guidance",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        # refresh should NOT be in handled
        refresh_handled = [h for h in ev["handled_by_anip"] if "refresh" in h.lower()]
        assert len(refresh_handled) == 0, f"False refresh_via should not be handled: {refresh_handled}"
        # glue should note the gap
        assert any("proposal does not declare" in g for g in ev["glue_you_will_still_write"])

    def test_declared_surfaces_absent_falls_back(self):
        """When declared_surfaces is absent, V2 text heuristic behavior is preserved."""
        req = _make_requirements()
        # Proposal text DOES mention refresh — V2 heuristic should pick it up
        proposal = _make_proposal(
            required_components=["capability_registry"],
            key_runtime_requirements=[
                "expose which capability typically refreshes stale state",
            ],
        )
        scenario = _make_scenario(
            name="fallback_text",
            category="orchestration",
            context={"task_id": "test"},
            expected_anip_support=[
                "refresh_path_guidance",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        # V2 text heuristic should credit refresh
        refresh_handled = [h for h in ev["handled_by_anip"] if "refresh" in h.lower()]
        assert len(refresh_handled) > 0, f"V2 fallback should credit refresh from text: {ev['handled_by_anip']}"

    def test_declared_surfaces_all_true(self):
        """All declared_surfaces true should yield maximum credit."""
        req = _make_requirements(
            services=[
                {"name": "svc-a", "role": "planning"},
                {"name": "svc-b", "role": "execution"},
            ],
            cross_service_continuity=True,
            cross_service_reconstruction=True,
        )
        proposal = _make_proposal(
            shape="multi_service_estate",
            required_components=["capability_registry"],
            rationale=["full design"],
            declared_surfaces={
                "budget_enforcement": True,
                "binding_requirements": True,
                "authority_posture": True,
                "recovery_class": True,
                "refresh_via": True,
                "verify_via": True,
                "followup_via": True,
                "cross_service_handoff": True,
                "cross_service_continuity": True,
                "cross_service_reconstruction": True,
            },
        )
        scenario = _make_scenario(
            name="all_true",
            category="orchestration",
            context={"task_id": "test"},
            expected_anip_support=[
                "refresh_path_guidance",
                "verification_path_guidance",
                "follow_up_guidance",
                "recovery_class",
                "binding_freshness_visibility",
                "cross_service_handoff_guidance",
            ],
        )

        result = evaluate(req, proposal, scenario)
        ev = result["evaluation"]
        # Should have many advisory surfaces handled
        advisory_handled = [h for h in ev["handled_by_anip"] if "advisory" in h]
        assert len(advisory_handled) >= 5, (
            f"All-true should credit at least 5 advisory surfaces, got {len(advisory_handled)}: {advisory_handled}"
        )
        # Should NOT have any "proposal does not declare" glue
        missing_glue = [g for g in ev["glue_you_will_still_write"] if "proposal does not declare" in g]
        assert len(missing_glue) == 0, f"All-true should not have missing-surface glue: {missing_glue}"

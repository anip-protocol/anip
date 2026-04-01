"""Tests for recovery_class on all failure resolutions (v0.16)."""
import pytest
from anip_service import ANIPService, Capability
from anip_core import (
    BindingRequirement,
    Budget,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    Cost,
    CostCertainty,
    FinancialCost,
    RECOVERY_CLASS_MAP,
    SideEffect,
    SideEffectType,
    recovery_class_for_action,
)


# ---------------------------------------------------------------------------
# Capability helpers
# ---------------------------------------------------------------------------

def _scope_cap():
    return Capability(
        declaration=CapabilityDeclaration(
            name="search",
            description="Search",
            inputs=[CapabilityInput(name="query", type="string", required=True, description="query")],
            output=CapabilityOutput(type="object", fields=["results"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["search:read"],
        ),
        handler=lambda ctx, params: {"results": []},
    )


def _budget_cap(amount: float = 100.0):
    return Capability(
        declaration=CapabilityDeclaration(
            name="book_flight",
            description="Book a flight",
            inputs=[CapabilityInput(name="route", type="string", required=True, description="route")],
            output=CapabilityOutput(type="object", fields=["booking_id"]),
            side_effect=SideEffect(type=SideEffectType.WRITE),
            minimum_scope=["book"],
            cost=Cost(
                certainty=CostCertainty.FIXED,
                financial=FinancialCost(currency="USD", amount=amount),
            ),
        ),
        handler=lambda ctx, params: {"booking_id": "BK-001"},
    )


def _binding_cap(max_age: str | None = None):
    return Capability(
        declaration=CapabilityDeclaration(
            name="book_flight",
            description="Book a flight",
            inputs=[
                CapabilityInput(name="route", type="string", required=True, description="route"),
                CapabilityInput(name="quote", type="object", required=False, description="quote reference"),
            ],
            output=CapabilityOutput(type="object", fields=["booking_id"]),
            side_effect=SideEffect(type=SideEffectType.WRITE),
            minimum_scope=["book"],
            requires_binding=[
                BindingRequirement(
                    type="quote",
                    field="quote",
                    source_capability="get_quote",
                    max_age=max_age,
                ),
            ],
        ),
        handler=lambda ctx, params: {"booking_id": "BK-001"},
    )


async def _issue_token(service, scope, capability, budget=None):
    token, _ = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope,
        capability=capability,
        ttl_hours=1,
        budget=budget,
    )
    return token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_scope_failure_recovery_class():
    """scope_insufficient failure must have recovery_class=redelegation_then_retry."""
    service = ANIPService(
        service_id="test-rc",
        capabilities=[_scope_cap()],
        storage=":memory:",
    )
    # Issue token with wrong scope so delegation validation fails
    token, _ = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=["other"],
        capability="search",
        ttl_hours=1,
    )
    result = await service.invoke("search", token, {"query": "hello"})
    assert result["success"] is False
    assert result["failure"]["type"] == "scope_insufficient"
    resolution = result["failure"]["resolution"]
    assert resolution is not None
    assert resolution["recovery_class"] == "redelegation_then_retry"


async def test_budget_failure_recovery_class():
    """budget_exceeded failure must have recovery_class=redelegation_then_retry."""
    service = ANIPService(
        service_id="test-rc",
        capabilities=[_budget_cap(amount=200.0)],
        storage=":memory:",
    )
    token = await _issue_token(
        service, ["book"], "book_flight",
        budget=Budget(currency="USD", max_amount=50.0),
    )
    result = await service.invoke("book_flight", token, {"route": "NYC-LAX"})
    assert result["success"] is False
    assert result["failure"]["type"] == "budget_exceeded"
    resolution = result["failure"]["resolution"]
    assert resolution is not None
    assert resolution["recovery_class"] == "redelegation_then_retry"


async def test_binding_stale_recovery_class():
    """binding_stale failure must have recovery_class=refresh_then_retry."""
    import time as _time
    service = ANIPService(
        service_id="test-rc",
        capabilities=[_binding_cap(max_age="PT5M")],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight")
    old_time = _time.time() - 600  # 10 minutes ago
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": {"quote_id": "qt-old", "price": 280, "issued_at": old_time},
    })
    assert result["success"] is False
    assert result["failure"]["type"] == "binding_stale"
    resolution = result["failure"]["resolution"]
    assert resolution is not None
    assert resolution["recovery_class"] == "refresh_then_retry"


async def test_recovery_class_consistent_with_action():
    """recovery_class in a failure must match RECOVERY_CLASS_MAP for that action."""
    service = ANIPService(
        service_id="test-rc",
        capabilities=[_binding_cap()],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight")
    result = await service.invoke("book_flight", token, {"route": "NYC-LAX"})
    assert result["success"] is False
    assert result["failure"]["type"] == "binding_missing"
    resolution = result["failure"]["resolution"]
    assert resolution is not None
    action = resolution["action"]
    expected_rc = RECOVERY_CLASS_MAP[action]
    assert resolution["recovery_class"] == expected_rc


async def test_recovery_class_present_on_all_failures():
    """Every failure returned by invoke must include a resolution with recovery_class."""
    import time as _time

    service = ANIPService(
        service_id="test-rc",
        capabilities=[_binding_cap(max_age="PT5M")],
        storage=":memory:",
    )

    failures_to_check = []

    # binding_missing
    token = await _issue_token(service, ["book"], "book_flight")
    result = await service.invoke("book_flight", token, {"route": "NYC-LAX"})
    failures_to_check.append(result)

    # binding_stale
    old_time = _time.time() - 600
    token = await _issue_token(service, ["book"], "book_flight")
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": {"quote_id": "qt-old", "price": 200, "issued_at": old_time},
    })
    failures_to_check.append(result)

    # unknown_capability
    token = await _issue_token(service, ["book"], "book_flight")
    result = await service.invoke("nonexistent", token, {})
    failures_to_check.append(result)

    for r in failures_to_check:
        assert r["success"] is False, f"Expected failure: {r}"
        failure = r["failure"]
        assert failure is not None
        resolution = failure.get("resolution")
        assert resolution is not None, f"Missing resolution on {failure['type']}"
        assert "recovery_class" in resolution, (
            f"Missing recovery_class on {failure['type']} resolution: {resolution}"
        )
        assert resolution["recovery_class"], f"Empty recovery_class on {failure['type']}"


async def test_retry_now_action():
    """provide_credentials maps to retry_now recovery class."""
    assert recovery_class_for_action("provide_credentials") == "retry_now"


async def test_revalidate_state_action():
    """revalidate_state maps to revalidate_then_retry recovery class."""
    assert recovery_class_for_action("revalidate_state") == "revalidate_then_retry"


def test_all_canonical_actions_have_mapping():
    """All 17 spec-defined canonical actions must be in RECOVERY_CLASS_MAP."""
    canonical_actions = [
        "retry_now",
        "wait_and_retry",
        "obtain_binding",
        "refresh_binding",
        "obtain_quote_first",
        "revalidate_state",
        "request_broader_scope",
        "request_budget_increase",
        "request_budget_bound_delegation",
        "request_matching_currency_delegation",
        "request_new_delegation",
        "request_capability_binding",
        "request_deeper_delegation",
        "escalate_to_root_principal",
        "provide_credentials",
        "check_manifest",
        "contact_service_owner",
    ]
    for action in canonical_actions:
        assert action in RECOVERY_CLASS_MAP, f"Missing mapping for canonical action: {action}"
        rc = RECOVERY_CLASS_MAP[action]
        assert rc in {
            "retry_now",
            "wait_then_retry",
            "refresh_then_retry",
            "revalidate_then_retry",
            "redelegation_then_retry",
            "terminal",
        }, f"Unknown recovery class '{rc}' for action '{action}'"

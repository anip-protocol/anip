"""Tests for control requirement enforcement in the invoke path (v0.13)."""
import time

from anip_service import ANIPService, Capability
from anip_core import (
    Budget,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    ControlRequirement,
    Cost,
    CostCertainty,
    FinancialCost,
    SideEffect,
    SideEffectType,
)


def _cap_with_control(control_requirements: list[ControlRequirement], cost=None):
    return Capability(
        declaration=CapabilityDeclaration(
            name="high_risk_action",
            description="An action requiring control requirements",
            inputs=[
                CapabilityInput(name="data", type="string", required=True, description="data"),
                CapabilityInput(name="ref", type="object", required=False, description="bound reference"),
            ],
            output=CapabilityOutput(type="object", fields=["result"]),
            side_effect=SideEffect(type=SideEffectType.WRITE),
            minimum_scope=["action"],
            cost=cost,
            control_requirements=control_requirements,
        ),
        handler=lambda ctx, params: {"result": "done"},
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


async def test_cost_ceiling_required_with_budget():
    """cost_ceiling control requirement satisfied when budget is present -> success."""
    cost = Cost(
        certainty=CostCertainty.FIXED,
        financial=FinancialCost(currency="USD", amount=50),
    )
    cap = _cap_with_control(
        [ControlRequirement(type="cost_ceiling")],
        cost=cost,
    )
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    token = await _issue_token(service, ["action"], "high_risk_action", budget=Budget(currency="USD", max_amount=100))
    result = await service.invoke("high_risk_action", token, {"data": "test"})
    assert result["success"] is True


async def test_cost_ceiling_required_without_budget():
    """cost_ceiling control requirement without budget -> control_requirement_unsatisfied."""
    cap = _cap_with_control([ControlRequirement(type="cost_ceiling")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    token = await _issue_token(service, ["action"], "high_risk_action")
    result = await service.invoke("high_risk_action", token, {"data": "test"})
    assert result["success"] is False
    assert result["failure"]["type"] == "control_requirement_unsatisfied"
    assert "cost_ceiling" in result["failure"]["detail"]


async def test_bound_reference_required_present():
    """bound_reference control requirement with field present -> success."""
    cap = _cap_with_control([ControlRequirement(type="bound_reference", field="ref")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    token = await _issue_token(service, ["action"], "high_risk_action")
    result = await service.invoke("high_risk_action", token, {
        "data": "test",
        "ref": {"reference_id": "ref-001"},
    })
    assert result["success"] is True


async def test_bound_reference_required_missing():
    """bound_reference control requirement with field missing -> control_requirement_unsatisfied."""
    cap = _cap_with_control([ControlRequirement(type="bound_reference", field="ref")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    token = await _issue_token(service, ["action"], "high_risk_action")
    result = await service.invoke("high_risk_action", token, {"data": "test"})
    assert result["success"] is False
    assert result["failure"]["type"] == "control_requirement_unsatisfied"
    assert "bound_reference" in result["failure"]["detail"]


async def test_freshness_window_within():
    """freshness_window control requirement within max_age -> success."""
    cap = _cap_with_control([ControlRequirement(type="freshness_window", field="ref", max_age="PT10M")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    token = await _issue_token(service, ["action"], "high_risk_action")
    # Fresh reference (issued 1 minute ago)
    result = await service.invoke("high_risk_action", token, {
        "data": "test",
        "ref": {"reference_id": "ref-001", "issued_at": time.time() - 60},
    })
    assert result["success"] is True


async def test_freshness_window_exceeded():
    """freshness_window control requirement older than max_age -> control_requirement_unsatisfied."""
    cap = _cap_with_control([ControlRequirement(type="freshness_window", field="ref", max_age="PT5M")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    token = await _issue_token(service, ["action"], "high_risk_action")
    # Stale reference (issued 10 minutes ago)
    result = await service.invoke("high_risk_action", token, {
        "data": "test",
        "ref": {"reference_id": "ref-001", "issued_at": time.time() - 600},
    })
    assert result["success"] is False
    assert result["failure"]["type"] == "control_requirement_unsatisfied"
    assert "freshness_window" in result["failure"]["detail"]


async def test_unmet_token_requirements_in_permissions():
    """cost_ceiling requirement with no budget -> shows as restricted in permissions."""
    cap = _cap_with_control([ControlRequirement(type="cost_ceiling")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    token = await _issue_token(service, ["action"], "high_risk_action")
    perms = service.discover_permissions(token)
    # Should be restricted because cost_ceiling is unmet (no budget in token)
    restricted_names = [r.capability for r in perms.restricted]
    assert "high_risk_action" in restricted_names
    restricted_cap = next(r for r in perms.restricted if r.capability == "high_risk_action")
    assert "cost_ceiling" in restricted_cap.unmet_token_requirements

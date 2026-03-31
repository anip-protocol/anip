"""Tests for control requirement enforcement in the invoke path (v0.14)."""

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


async def test_stronger_delegation_required_satisfied():
    """stronger_delegation_required with matching capability binding -> success."""
    cap = _cap_with_control([ControlRequirement(type="stronger_delegation_required")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    # Token issued with capability matching the declared capability name
    token = await _issue_token(service, ["action"], "high_risk_action")
    result = await service.invoke("high_risk_action", token, {"data": "test"})
    assert result["success"] is True


async def test_stronger_delegation_required_unsatisfied():
    """stronger_delegation_required with mismatched capability binding -> rejected.

    Purpose validation catches mismatched capabilities before the control
    requirement loop, so the failure type is 'purpose_mismatch'.  The result
    is the same: the invocation is rejected when the token's capability
    binding does not match the invoked capability.
    """
    cap = _cap_with_control([ControlRequirement(type="stronger_delegation_required")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    # Token issued for a different capability
    token = await _issue_token(service, ["action"], "some_other_capability")
    result = await service.invoke("high_risk_action", token, {"data": "test"})
    assert result["success"] is False
    assert result["failure"]["type"] == "purpose_mismatch"


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

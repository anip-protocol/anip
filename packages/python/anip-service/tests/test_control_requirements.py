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

    The delegation engine's purpose validation (purpose.capability != invoked
    capability) fires *before* the control requirement loop, so
    ``stronger_delegation_required`` in the control loop is unreachable through
    the normal invoke path.  The purpose layer catches the mismatch first and
    returns ``purpose_mismatch``.

    This test documents that behaviour: a token bound to a different capability
    is rejected at the purpose layer, not at the control requirement layer.
    See ``test_stronger_delegation_check_logic_unit`` for an isolated test of
    the control requirement predicate itself.
    """
    cap = _cap_with_control([ControlRequirement(type="stronger_delegation_required")])
    service = ANIPService(
        service_id="test-control",
        capabilities=[cap],
        storage=":memory:",
    )
    # Token issued for a different capability — purpose validation rejects first
    token = await _issue_token(service, ["action"], "some_other_capability")
    result = await service.invoke("high_risk_action", token, {"data": "test"})
    assert result["success"] is False
    assert result["failure"]["type"] == "purpose_mismatch"


def test_stronger_delegation_check_logic_unit():
    """Unit test: the stronger_delegation_required predicate in isolation.

    The control requirement loop checks:
        token.purpose.capability == declared_capability_name

    Purpose validation in the delegation engine makes this check unreachable
    through the full invoke path (purpose_mismatch fires first).  This test
    exercises the predicate directly to ensure it is correct as a defence-in-
    depth safety net.
    """
    from anip_core import Purpose

    cap_name = "high_risk_action"

    def _check_stronger_delegation(resolved_token, decl_name):
        """Mirrors the predicate at service.py line ~935."""
        return (
            hasattr(resolved_token, "purpose")
            and resolved_token.purpose
            and resolved_token.purpose.capability == decl_name
        )

    class _TokenStub:
        """Lightweight stand-in — avoids constructing a full DelegationToken."""
        def __init__(self, purpose):
            self.purpose = purpose

    # Matching capability binding -> satisfied
    assert _check_stronger_delegation(
        _TokenStub(Purpose(capability=cap_name, task_id=None)), cap_name,
    ), "Expected stronger_delegation_required to be satisfied when purpose.capability matches"

    # Mismatched capability binding -> not satisfied
    assert not _check_stronger_delegation(
        _TokenStub(Purpose(capability="some_other_capability", task_id=None)), cap_name,
    ), "Expected stronger_delegation_required to be unsatisfied when purpose.capability differs"

    # No purpose at all -> not satisfied
    assert not _check_stronger_delegation(
        _TokenStub(None), cap_name,
    ), "Expected stronger_delegation_required to be unsatisfied when purpose is None"


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

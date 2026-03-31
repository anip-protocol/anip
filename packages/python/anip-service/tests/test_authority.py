"""Tests for reason_type, resolution_hint, and canonical authority actions (v0.15)."""
from __future__ import annotations

import pytest

from anip_service import ANIPService, Capability
from anip_core import (
    Budget,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    ControlRequirement,
    Cost,
    CostCertainty,
    DeniedCapability,
    FinancialCost,
    RestrictedCapability,
    SideEffect,
    SideEffectType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cap(name: str, minimum_scope: list[str], control_requirements: list[ControlRequirement] | None = None, cost=None) -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description=f"Test capability: {name}",
            inputs=[CapabilityInput(name="x", type="string", required=True, description="input")],
            output=CapabilityOutput(type="object", fields=["result"]),
            side_effect=SideEffect(type=SideEffectType.WRITE),
            minimum_scope=minimum_scope,
            cost=cost,
            control_requirements=control_requirements or [],
        ),
        handler=lambda ctx, params: {"result": "ok"},
    )


async def _issue_token(service: ANIPService, scope: list[str], capability: str, budget=None):
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
# RestrictedCapability: reason_type = "insufficient_scope"
# ---------------------------------------------------------------------------


async def test_insufficient_scope_partial_overlap_is_restricted():
    """Partial scope match -> restricted with reason_type='insufficient_scope'."""
    # Capability requires two scopes; token has one of them
    cap = _make_cap("book_flight", minimum_scope=["flights.read", "flights.write"])
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    token = await _issue_token(service, ["flights.read"], "book_flight")
    perms = service.discover_permissions(token)

    restricted = [r for r in perms.restricted if r.capability == "book_flight"]
    assert restricted, "book_flight should be restricted due to partial scope overlap"
    r = restricted[0]
    assert r.reason_type == "insufficient_scope"


async def test_insufficient_scope_partial_overlap_resolution_hint():
    """Partial scope match -> resolution_hint='request_broader_scope'."""
    cap = _make_cap("book_flight", minimum_scope=["flights.read", "flights.write"])
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    token = await _issue_token(service, ["flights.read"], "book_flight")
    perms = service.discover_permissions(token)

    restricted = [r for r in perms.restricted if r.capability == "book_flight"]
    r = restricted[0]
    assert r.resolution_hint == "request_broader_scope"


async def test_no_scope_overlap_is_restricted():
    """No scope overlap at all -> restricted (not denied) with reason_type='insufficient_scope'.

    denied is reserved for non_delegable capabilities only.
    """
    cap = _make_cap("book_flight", minimum_scope=["flights.write"])
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    token = await _issue_token(service, ["other.read"], "book_flight")
    perms = service.discover_permissions(token)

    restricted = [r for r in perms.restricted if r.capability == "book_flight"]
    assert restricted, "book_flight should be restricted when no scope overlaps (not denied)"
    r = restricted[0]
    assert r.reason_type == "insufficient_scope"
    assert r.grantable_by == "human:test@example.com"
    assert r.resolution_hint == "request_broader_scope"


# ---------------------------------------------------------------------------
# DeniedCapability: admin scopes are NOT special — same insufficient_scope
# ---------------------------------------------------------------------------


async def test_admin_scope_is_not_special():
    """Admin scope requirement -> restricted with reason_type='insufficient_scope', NOT non_delegable.

    denied is reserved for non_delegable capabilities only.
    """
    cap = _make_cap("admin_action", minimum_scope=["admin.superpower"])
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    token = await _issue_token(service, ["other.read"], "admin_action")
    perms = service.discover_permissions(token)

    restricted = [r for r in perms.restricted if r.capability == "admin_action"]
    assert restricted, "admin_action should be restricted (not denied — denied is for non_delegable only)"
    r = restricted[0]
    assert r.reason_type == "insufficient_scope", (
        "admin.* scopes should use insufficient_scope, not non_delegable"
    )


# ---------------------------------------------------------------------------
# RestrictedCapability: reason_type = "unmet_control_requirement"
# ---------------------------------------------------------------------------


async def test_unmet_control_requirement_cost_ceiling_reason_type():
    """cost_ceiling unmet -> reason_type='unmet_control_requirement'."""
    cap = _make_cap(
        "pay_now",
        minimum_scope=["payments.write"],
        control_requirements=[ControlRequirement(type="cost_ceiling")],
    )
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    # Scope present but no budget in token
    token = await _issue_token(service, ["payments.write"], "pay_now")
    perms = service.discover_permissions(token)

    restricted = [r for r in perms.restricted if r.capability == "pay_now"]
    assert restricted, "pay_now should be restricted due to unmet cost_ceiling"
    r = restricted[0]
    assert r.reason_type == "unmet_control_requirement"


async def test_unmet_control_requirement_cost_ceiling_resolution_hint():
    """cost_ceiling unmet -> resolution_hint='request_budget_bound_delegation'."""
    cap = _make_cap(
        "pay_now",
        minimum_scope=["payments.write"],
        control_requirements=[ControlRequirement(type="cost_ceiling")],
    )
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    token = await _issue_token(service, ["payments.write"], "pay_now")
    perms = service.discover_permissions(token)

    restricted = [r for r in perms.restricted if r.capability == "pay_now"]
    r = restricted[0]
    assert r.resolution_hint == "request_budget_bound_delegation"


async def test_unmet_control_requirement_stronger_delegation_resolution_hint():
    """stronger_delegation_required unmet -> resolution_hint='request_capability_binding'."""
    cap = _make_cap(
        "sensitive_action",
        minimum_scope=["sensitive.write"],
        control_requirements=[ControlRequirement(type="stronger_delegation_required")],
    )
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    # Issue token with a DIFFERENT capability so purpose.capability != "sensitive_action"
    # That triggers purpose_mismatch at the delegation layer, but we test permissions directly
    token = await _issue_token(service, ["sensitive.write"], "other_capability")
    perms = service.discover_permissions(token)

    restricted = [r for r in perms.restricted if r.capability == "sensitive_action"]
    assert restricted, "sensitive_action should be restricted due to unmet stronger_delegation_required"
    r = restricted[0]
    assert r.reason_type == "unmet_control_requirement"
    assert r.resolution_hint == "request_capability_binding"


# ---------------------------------------------------------------------------
# Canonical action string in delegation failure
# ---------------------------------------------------------------------------


async def test_scope_insufficient_action_is_request_broader_scope():
    """scope_insufficient ANIPFailure resolution.action == 'request_broader_scope'."""
    cap = _make_cap("read_data", minimum_scope=["data.read"])
    service = ANIPService(service_id="test-authority", capabilities=[cap], storage=":memory:")
    # Token with wrong scope triggers scope_insufficient in the delegation engine
    token = await _issue_token(service, ["other.read"], "read_data")
    # Override token scope to trigger the delegation path
    # We invoke directly so delegation checks fire
    result = await service.invoke("read_data", token, {"x": "val"})
    assert result["success"] is False
    failure = result["failure"]
    assert failure["type"] == "scope_insufficient"
    assert failure["resolution"]["action"] == "request_broader_scope"


# ---------------------------------------------------------------------------
# Model field presence (unit tests — no service needed)
# ---------------------------------------------------------------------------


def test_restricted_capability_requires_reason_type():
    """RestrictedCapability: reason_type is required (no default)."""
    rc = RestrictedCapability(
        capability="foo",
        reason="missing scope",
        reason_type="insufficient_scope",
        grantable_by="human:admin",
    )
    assert rc.reason_type == "insufficient_scope"
    assert rc.resolution_hint is None  # optional, defaults to None


def test_restricted_capability_resolution_hint_optional():
    """RestrictedCapability: resolution_hint is optional."""
    rc = RestrictedCapability(
        capability="foo",
        reason="missing scope",
        reason_type="insufficient_scope",
        grantable_by="human:admin",
        resolution_hint="request_broader_scope",
    )
    assert rc.resolution_hint == "request_broader_scope"


def test_denied_capability_requires_reason_type():
    """DeniedCapability: reason_type is required (no default)."""
    dc = DeniedCapability(
        capability="bar",
        reason="requires admin principal",
        reason_type="non_delegable",
    )
    assert dc.reason_type == "non_delegable"


def test_denied_capability_reason_type_required_no_default():
    """DeniedCapability: reason_type must be supplied — validation error if absent."""
    with pytest.raises(Exception):
        DeniedCapability(capability="bar", reason="requires admin principal")


def test_restricted_capability_reason_type_required_no_default():
    """RestrictedCapability: reason_type must be supplied — validation error if absent."""
    with pytest.raises(Exception):
        RestrictedCapability(
            capability="foo",
            reason="missing scope",
            grantable_by="human:admin",
        )

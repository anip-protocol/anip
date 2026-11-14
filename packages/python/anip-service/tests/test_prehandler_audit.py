"""Every refusal made before the handler is audited (SPEC.md §6.3).

Budget, binding and control-requirement refusals are recorded like scope,
purpose and parameter refusals: one audit entry for the invocation, a
failure with the refusal's failure_type, and the event class the runtime
gives denials. Unary and streaming invocations are refused the same way.
"""
from __future__ import annotations

import time
from typing import Any

import pytest
from anip_core import (
    BindingRequirement,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    ControlRequirement,
    Cost,
    CostCertainty,
    FinancialCost,
    ResponseMode,
    SideEffect,
    SideEffectType,
)

from anip_service import ANIPService, Capability
from anip_service.classification import classify_event


class _Recorder:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def __call__(self, ctx, params):
        self.calls.append(params)
        return {"ok": True}


def _declaration(**overrides: Any) -> CapabilityDeclaration:
    fields: dict[str, Any] = dict(
        name="book",
        description="Book something",
        inputs=[CapabilityInput(name="quote", type="object", required=False)],
        output=CapabilityOutput(type="object", fields=["ok"]),
        side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
        minimum_scope=["book"],
        response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
    )
    fields.update(overrides)
    return CapabilityDeclaration(**fields)


ESTIMATED = dict(
    cost=Cost(certainty=CostCertainty.ESTIMATED,
              financial=FinancialCost(currency="USD", range_min=100, range_max=500)),
    requires_binding=[BindingRequirement(type="quote", field="quote", max_age="PT15M")],
)
FIXED = dict(cost=Cost(certainty=CostCertainty.FIXED,
                       financial=FinancialCost(currency="USD", amount=500)))
NOW = int(time.time())

# (case, declaration overrides, parameters, invoke budget hint, expected failure type)
CASES = [
    ("budget_exceeded_fixed", FIXED, {}, {"currency": "USD", "max_amount": 1}, "budget_exceeded"),
    ("budget_exceeded_bound", ESTIMATED, {"quote": {"price": 420, "issued_at": NOW}},
     {"currency": "USD", "max_amount": 100}, "budget_exceeded"),
    ("budget_currency_mismatch", FIXED, {}, {"currency": "EUR", "max_amount": 1000},
     "budget_currency_mismatch"),
    ("budget_not_enforceable", ESTIMATED, {"quote": {"issued_at": NOW}},
     {"currency": "USD", "max_amount": 1000}, "budget_not_enforceable"),
    ("binding_missing", ESTIMATED, {}, None, "binding_missing"),
    ("binding_stale", ESTIMATED, {"quote": {"price": 420, "issued_at": NOW - 86400}}, None,
     "binding_stale"),
    ("control_requirement", {"control_requirements": [ControlRequirement(type="cost_ceiling")]},
     {}, None, "control_requirement_unsatisfied"),
]


async def _setup(overrides: dict[str, Any]):
    handler = _Recorder()
    service = ANIPService(
        service_id="test-prehandler-audit",
        capabilities=[Capability(declaration=_declaration(**overrides), handler=handler)],
        storage=":memory:",
    )
    token, _ = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=["book"],
        capability="book",
        ttl_hours=1,
    )
    return service, token, handler


async def _single_entry(service: ANIPService, token, invocation_id: str) -> dict[str, Any]:
    found = await service.query_audit(token, {"invocation_id": invocation_id})
    entries = [e for e in found["entries"] if e.get("invocation_id") == invocation_id]
    assert len(entries) == 1, f"expected one audit entry for {invocation_id}, got {entries}"
    return entries[0]


@pytest.mark.parametrize("case,overrides,parameters,budget,expected",
                         CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("stream", [False, True], ids=["unary", "streaming"])
async def test_refusal_before_the_handler_is_audited(case, overrides, parameters, budget,
                                                     expected, stream):
    service, token, handler = await _setup(overrides)
    events: list[Any] = []

    async def sink(event):
        events.append(event)

    kwargs: dict[str, Any] = {"budget": budget}
    if stream:
        kwargs.update(stream=True, _progress_sink=sink)
    result = await service.invoke("book", token, dict(parameters), **kwargs)

    assert result["success"] is False
    assert result["failure"]["type"] == expected, result
    assert handler.calls == [] and events == []
    entry = await _single_entry(service, token, result["invocation_id"])
    assert entry["success"] is False
    assert entry["failure_type"] == expected
    # The classification the runtime gives every refusal (SPEC.md §6.8).
    assert entry["event_class"] == classify_event("irreversible", False, expected)

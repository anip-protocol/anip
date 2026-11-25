"""A streaming invocation runs the same pre-handler checks as a unary one.

One request per row, sent once unary and once with ``stream=True`` and a
progress sink to a streaming-capable capability. Both must be refused with
the same failure, before the handler, and audited alike.
"""
from __future__ import annotations

import time
from typing import Any

import pytest
from anip_core import (
    BindingRequirement,
    Budget,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    ControlRequirement,
    Cost,
    CostCertainty,
    FinancialCost,
    GrantPolicy,
    ResponseMode,
    SideEffect,
    SideEffectType,
)

from anip_service import ANIPError, ANIPService, Capability

STREAMING = [ResponseMode.UNARY, ResponseMode.STREAMING]


class Harness:
    def __init__(self) -> None:
        self.handler_calls: list[dict[str, Any]] = []
        self.progress: list[dict[str, Any]] = []

        async def handler(ctx, params):
            self.handler_calls.append(dict(params))
            await ctx.emit_progress({"step": 1})
            if params.get("needs_approval") and not ctx.approval_grant:
                raise ANIPError(
                    "approval_required", "needs approval",
                    resolution={"action": "request_approval", "recovery_class": "wait_then_retry"})
            return {"ok": True}

        def declaration(name: str, **extra: Any) -> CapabilityDeclaration:
            return CapabilityDeclaration(
                name=name,
                description=name,
                inputs=[
                    CapabilityInput(name="item", type="string"),
                    CapabilityInput(name="quote", type="object", required=False),
                    CapabilityInput(name="needs_approval", type="boolean", required=False),
                ],
                output=CapabilityOutput(type="object", fields=["ok"]),
                side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
                minimum_scope=["book"],
                response_modes=STREAMING,
                **extra,
            )

        self.service = ANIPService(
            service_id="test-streaming-checks",
            capabilities=[
                Capability(handler=handler, declaration=declaration(
                    "stream_book",
                    cost=Cost(
                        certainty=CostCertainty.ESTIMATED,
                        financial=FinancialCost(currency="USD", range_min=100, range_max=500)),
                    requires_binding=[BindingRequirement(
                        type="quote", field="quote", source_capability="search", max_age="PT5M")],
                    grant_policy=GrantPolicy(
                        allowed_grant_types=["one_time"], default_grant_type="one_time",
                        expires_in_seconds=900, max_uses=1),
                )),
                Capability(handler=handler, declaration=declaration(
                    "stream_ceiling",
                    control_requirements=[ControlRequirement(type="cost_ceiling")],
                )),
                Capability(handler=handler, declaration=declaration("stream_other")),
            ],
            storage=":memory:",
        )

    async def token(self, *, scope=("book",), capability="stream_book", budget: Budget | None = None):
        token, _ = await self.service._engine.issue_root_token(
            authenticated_principal="human:test@example.com",
            subject="human:test@example.com",
            scope=list(scope), capability=capability, ttl_hours=1, budget=budget,
        )
        return token

    async def sink(self, event: dict[str, Any]) -> None:
        self.progress.append(event)

    async def invoke(self, capability: str, token, parameters, *, stream: bool, **kwargs: Any):
        if stream:
            kwargs.update(stream=True, _progress_sink=self.sink)
        return await self.service.invoke(capability, token, parameters, **kwargs)

    async def audit_entries(self, token, invocation_id: str) -> list[dict[str, Any]]:
        found = await self.service.query_audit(token, {"invocation_id": invocation_id})
        return [e for e in found["entries"] if e.get("invocation_id") == invocation_id]


def _quote(**overrides: Any) -> dict[str, Any]:
    quote = {"id": "qt-1", "price": 420, "issued_at": int(time.time())}
    quote.update(overrides)
    return quote


def _without_price() -> dict[str, Any]:
    quote = _quote()
    del quote["price"]
    return quote


# (row, expected failure, capability, token arguments, parameters, invoke arguments)
ROWS = [
    ("1 budget exceeded", "budget_exceeded", "stream_book",
     {"budget": Budget(currency="USD", max_amount=1)},
     lambda: {"item": "x", "quote": _quote()}, {}),
    ("2 budget_not_enforceable", "budget_not_enforceable", "stream_book",
     {"budget": Budget(currency="USD", max_amount=100000)},
     lambda: {"item": "x", "quote": _without_price()}, {}),
    ("3 binding_missing", "binding_missing", "stream_book", {},
     lambda: {"item": "x"}, {}),
    ("4 binding_stale", "binding_stale", "stream_book", {},
     lambda: {"item": "x", "quote": _quote(issued_at=int(time.time()) - 3600)}, {}),
    ("5 control requirement", "control_requirement_unsatisfied", "stream_ceiling",
     {"capability": "stream_ceiling"},
     lambda: {"item": "x"}, {}),
    ("6 purpose mismatch", "purpose_mismatch", "stream_book",
     {"capability": "stream_other"},
     lambda: {"item": "x", "quote": _quote()}, {}),
    ("7 insufficient scope", "scope_insufficient", "stream_book",
     {"scope": ("unrelated",)},
     lambda: {"item": "x", "quote": _quote()}, {}),
    ("8 blank approval grant", "grant_not_found", "stream_book", {},
     lambda: {"item": "x", "quote": _quote()}, {"approval_grant": ""}),
    ("9 unknown approval grant", "grant_not_found", "stream_book", {},
     lambda: {"item": "x", "quote": _quote()}, {"approval_grant": "grant_000000000000"}),
    ("10 parameter validation", "invalid_parameters", "stream_book", {},
     lambda: {"quote": _quote()}, {}),
]


@pytest.mark.parametrize(
    "expected,capability,token_args,parameters,invoke_args",
    [row[1:] for row in ROWS], ids=[row[0] for row in ROWS])
async def test_streaming_refuses_like_unary(
    expected, capability, token_args, parameters, invoke_args
):
    harness = Harness()
    token = await harness.token(**token_args)

    unary = await harness.invoke(capability, token, parameters(), stream=False, **invoke_args)
    assert unary["success"] is False
    assert unary["failure"]["type"] == expected, f"unary control: {unary}"
    assert harness.handler_calls == [], "unary control: the handler ran"
    unary_audit = await harness.audit_entries(token, unary["invocation_id"])

    streamed = await harness.invoke(capability, token, parameters(), stream=True, **invoke_args)

    assert streamed["success"] is False, f"the streaming invocation was not refused: {streamed}"
    assert streamed["failure"] == unary["failure"]
    assert "result" not in streamed
    assert harness.handler_calls == [], "the handler ran on the streaming path"
    assert harness.progress == [], "progress was emitted before the refusal"
    streamed_audit = await harness.audit_entries(token, streamed["invocation_id"])
    assert len(streamed_audit) == len(unary_audit)
    assert [e["failure_type"] for e in streamed_audit] == [e["failure_type"] for e in unary_audit]
    assert all(e["success"] is False for e in streamed_audit)


async def test_valid_streaming_invocation_runs_the_handler():
    """Control: the request the rows above vary is otherwise accepted."""
    harness = Harness()
    token = await harness.token()

    streamed = await harness.invoke(
        "stream_book", token, {"item": "x", "quote": _quote()}, stream=True)

    assert streamed["success"] is True, streamed
    assert len(harness.handler_calls) == 1
    assert len(harness.progress) == 1


async def test_refused_streaming_continuation_does_not_reserve_the_grant():
    harness = Harness()
    token = await harness.token()
    approved = {"item": "x", "quote": _quote(), "needs_approval": True}
    first = await harness.invoke("stream_book", token, dict(approved), stream=True)
    assert first["failure"]["type"] == "approval_required", first
    grant = await harness.service.issue_approval_grant(
        first["failure"]["approval_required"]["approval_request_id"],
        "one_time", {"subject": "human:approver"})
    calls_before = len(harness.handler_calls)

    async def use_count() -> int:
        return (await harness.service._storage.get_grant(grant["grant_id"]))["use_count"]

    # Refused before the handler: missing input, then a stale binding.
    for parameters in (
        {"quote": approved["quote"], "needs_approval": True},
        {**approved, "quote": _quote(issued_at=int(time.time()) - 3600)},
    ):
        refused = await harness.invoke(
            "stream_book", token, parameters, stream=True, approval_grant=grant["grant_id"])
        assert refused["success"] is False
        assert refused["failure"]["type"] in ("invalid_parameters", "binding_stale")
        assert await use_count() == 0
    # Drift is found at grant validation, still before reservation.
    drifted = await harness.invoke(
        "stream_book", token, {**approved, "item": "y"},
        stream=True, approval_grant=grant["grant_id"])
    assert drifted["failure"]["type"] == "grant_param_drift"
    assert await use_count() == 0
    assert len(harness.handler_calls) == calls_before

    continued = await harness.invoke(
        "stream_book", token, dict(approved), stream=True, approval_grant=grant["grant_id"])
    assert continued["success"] is True, continued
    assert await use_count() == 1

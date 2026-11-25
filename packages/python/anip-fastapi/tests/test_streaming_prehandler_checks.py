"""A streaming invocation over HTTP is refused before the handler for the
same reasons as a unary one.

This binding delivers a pre-handler refusal of a streaming invocation as an
SSE ``failed`` event with HTTP 200; the unary refusal is JSON with the status
of its failure type. The failure object is the same.
"""
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_core import (
    BindingRequirement, CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    ControlRequirement, Cost, CostCertainty, FinancialCost, GrantPolicy, ResponseMode,
    SideEffect, SideEffectType, failure_status_code,
)
from anip_fastapi import mount_anip
from anip_service import ANIPService, Capability

API_KEY = "test-key-123"


@pytest.fixture
def harness():
    calls: list = []

    async def handler(ctx, params):
        calls.append(dict(params))
        await ctx.emit_progress({"step": 1})
        return {"ok": True}

    def declaration(name, **extra):
        return CapabilityDeclaration(
            name=name,
            description=name,
            inputs=[
                CapabilityInput(name="item", type="string", description="Item"),
                CapabilityInput(name="quote", type="object", required=False, description="Quote"),
            ],
            output=CapabilityOutput(type="object", fields=["ok"]),
            side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
            minimum_scope=["book"],
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
            **extra,
        )

    service = ANIPService(
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
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    return TestClient(app), calls


def _quote(**overrides):
    quote = {"id": "qt-1", "price": 420, "issued_at": int(time.time())}
    quote.update(overrides)
    return quote


def _without_price():
    quote = _quote()
    del quote["price"]
    return quote


# (row, expected failure, capability, token request, parameters, extra body members)
ROWS = [
    ("1 budget exceeded", "budget_exceeded", "stream_book",
     {"budget": {"currency": "USD", "max_amount": 1}},
     lambda: {"item": "x", "quote": _quote()}, {}),
    ("2 budget_not_enforceable", "budget_not_enforceable", "stream_book",
     {"budget": {"currency": "USD", "max_amount": 100000}},
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
     {"scope": ["unrelated"]},
     lambda: {"item": "x", "quote": _quote()}, {}),
    ("8 blank approval grant", "grant_not_found", "stream_book", {},
     lambda: {"item": "x", "quote": _quote()}, {"approval_grant": ""}),
    ("9 unknown approval grant", "grant_not_found", "stream_book", {},
     lambda: {"item": "x", "quote": _quote()}, {"approval_grant": "grant_000000000000"}),
    ("10 parameter validation", "invalid_parameters", "stream_book", {},
     lambda: {"quote": _quote()}, {}),
]


def _events(resp) -> list[tuple[str, dict]]:
    events = []
    for block in resp.text.split("\n\n"):
        if not block.strip():
            continue
        name, data = block.split("\n", 1)
        events.append((name[len("event: "):], json.loads(data[len("data: "):])))
    return events


@pytest.mark.parametrize(
    "expected,capability,token_request,parameters,extra",
    [row[1:] for row in ROWS], ids=[row[0] for row in ROWS])
def test_streaming_refuses_like_unary(harness, expected, capability, token_request, parameters, extra):
    client, calls = harness
    issued = client.post(
        "/anip/tokens",
        json={"scope": ["book"], "capability": "stream_book", **token_request},
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert issued.status_code == 200, issued.text
    headers = {"Authorization": f"Bearer {issued.json()['token']}"}

    unary = client.post(
        f"/anip/invoke/{capability}", json={"parameters": parameters(), **extra}, headers=headers)
    assert unary.json()["failure"]["type"] == expected, f"unary control: {unary.text}"
    assert unary.status_code == failure_status_code(expected)
    assert calls == [], "unary control: the handler ran"

    streamed = client.post(
        f"/anip/invoke/{capability}",
        json={"parameters": parameters(), "stream": True, **extra}, headers=headers)

    assert streamed.status_code == 200
    assert "text/event-stream" in streamed.headers.get("content-type", "")
    events = _events(streamed)
    assert [name for name, _ in events] == ["failed"], events
    payload = events[0][1]
    assert payload["success"] is False
    assert payload["failure"] == unary.json()["failure"]
    assert payload["invocation_id"].startswith("inv-")
    assert "result" not in payload
    assert calls == [], "the handler ran on the streaming path"


def test_valid_streaming_invocation_runs_the_handler(harness):
    """Control: the request the rows above vary is otherwise accepted."""
    client, calls = harness
    token = client.post(
        "/anip/tokens", json={"scope": ["book"], "capability": "stream_book"},
        headers={"Authorization": f"Bearer {API_KEY}"}).json()["token"]

    streamed = client.post(
        "/anip/invoke/stream_book",
        json={"parameters": {"item": "x", "quote": _quote()}, "stream": True},
        headers={"Authorization": f"Bearer {token}"})

    assert [name for name, _ in _events(streamed)] == ["progress", "completed"]
    assert len(calls) == 1

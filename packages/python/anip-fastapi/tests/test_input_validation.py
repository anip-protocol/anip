"""Parameter validation (SPEC.md §6.3) as seen through the FastAPI binding."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput, ResponseMode,
    SideEffect, SideEffectType,
)
from anip_fastapi import mount_anip
from anip_service import ANIPService, Capability

API_KEY = "test-key-123"

RESOLUTION = {
    "action": "retry_now",
    "recovery_class": "retry_now",
    "requires": "parameters that match the capability's declared inputs",
}


def _capability(name: str, calls: list, *, streaming: bool = False) -> Capability:
    def handler(ctx, params):
        calls.append(dict(params))
        return {"ok": True}

    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Reserve seats",
            contract_version="1.0",
            inputs=[
                CapabilityInput(name="flight", type="string", description="Flight"),
                CapabilityInput(name="seats", type="integer", required=False, description="Seats"),
            ],
            output=CapabilityOutput(type="object", fields=["ok"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["reserve"],
            response_modes=(
                [ResponseMode.UNARY, ResponseMode.STREAMING] if streaming else [ResponseMode.UNARY]
            ),
        ),
        handler=handler,
    )


@pytest.fixture
def harness():
    calls: list = []
    service = ANIPService(
        service_id="test-service",
        capabilities=[
            _capability("reserve", calls),
            _capability("reserve_stream", calls, streaming=True),
        ],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    return TestClient(app), calls


def _token(client: TestClient, capability: str) -> str:
    resp = client.post(
        "/anip/tokens",
        json={"scope": ["reserve"], "capability": capability},
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _invoke(client: TestClient, capability: str, body: dict):
    return client.post(
        f"/anip/invoke/{capability}", json=body,
        headers={"Authorization": f"Bearer {_token(client, capability)}"},
    )


def test_missing_required_input_is_400_invalid_parameters(harness):
    client, calls = harness

    resp = _invoke(client, "reserve", {"parameters": {"seats": 2}, "client_reference_id": "ref-9"})

    assert resp.status_code == 400
    data = resp.json()
    assert data["success"] is False
    assert data["failure"] == {
        "type": "invalid_parameters",
        "detail": "reserve is missing required input(s): flight",
        "resolution": RESOLUTION,
        "retry": False,
    }
    assert data["invocation_id"].startswith("inv-")
    assert data["client_reference_id"] == "ref-9"
    assert "result" not in data
    assert calls == []


def test_wrong_type_is_400_invalid_parameters(harness):
    client, calls = harness

    resp = _invoke(client, "reserve", {"parameters": {"flight": "AA1", "seats": "two"}})

    assert resp.status_code == 400
    assert resp.json()["failure"] == {
        "type": "invalid_parameters",
        "detail": "reserve has invalid input(s): 'seats' must be integer, got string",
        "resolution": RESOLUTION,
        "retry": False,
    }
    assert calls == []


@pytest.mark.parametrize("body", [{"parameters": None}, {"parameters": {}}])
def test_null_or_empty_parameters_are_missing_inputs(harness, body):
    client, calls = harness

    resp = _invoke(client, "reserve", body)

    assert resp.status_code == 400
    assert resp.json()["failure"]["type"] == "invalid_parameters"
    assert resp.json()["failure"]["detail"] == "reserve is missing required input(s): flight"
    assert calls == []


def test_integral_float_is_accepted(harness):
    client, calls = harness

    resp = client.post(
        "/anip/invoke/reserve",
        content=b'{"parameters": {"flight": "AA1", "seats": 2.0}}',
        headers={"Authorization": f"Bearer {_token(client, 'reserve')}",
                 "Content-Type": "application/json"},
    )

    assert resp.status_code == 200, resp.text
    assert calls == [{"flight": "AA1", "seats": 2.0}]


def test_refusal_is_audited(harness):
    client, _ = harness
    token = _token(client, "reserve")
    headers = {"Authorization": f"Bearer {token}"}
    refused = client.post("/anip/invoke/reserve", json={"parameters": {}}, headers=headers).json()

    resp = client.post(f"/anip/audit?invocation_id={refused['invocation_id']}", headers=headers)

    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["success"] is False
    assert entries[0]["failure_type"] == "invalid_parameters"


def test_streaming_invocation_delivers_the_same_failure_as_a_failed_event(harness):
    """A refusal made before the handler on a streaming invocation is an SSE
    ``failed`` event (HTTP 200) in this binding; the failure object is the
    same one a unary invocation returns."""
    client, calls = harness

    resp = _invoke(client, "reserve_stream", {"parameters": {"seats": 2}, "stream": True})

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    events = [block for block in resp.text.split("\n\n") if block.strip()]
    assert len(events) == 1
    name, data = events[0].split("\n", 1)
    assert name == "event: failed"
    payload = json.loads(data[len("data: "):])
    assert payload["success"] is False
    assert payload["failure"] == {
        "type": "invalid_parameters",
        "detail": "reserve_stream is missing required input(s): flight",
        "resolution": RESOLUTION,
        "retry": False,
    }
    assert payload["invocation_id"].startswith("inv-")
    assert calls == []


def test_requested_effects_of_the_wrong_type_gets_the_canonical_resolution(harness):
    client, calls = harness

    resp = _invoke(client, "reserve", {
        "parameters": {"flight": "AA1"}, "requested_effects": "booking.create"})

    assert resp.status_code == 400
    failure = resp.json()["failure"]
    assert failure["type"] == "invalid_parameters"
    assert failure["resolution"]["action"] == "retry_now"
    assert failure["resolution"]["recovery_class"] == "retry_now"
    assert failure["retry"] is False
    assert calls == []


@pytest.mark.parametrize("value,received", [
    (["x"], "array"), ("x", "string"), (1.5, "number"), (True, "boolean"),
])
def test_parameters_that_are_not_an_object_are_refused_before_binding_enforcement(value, received):
    """SPEC.md §6.3: a ``parameters`` value that is not an object does not
    match the request schema. It is refused like a body that is not JSON,
    so a capability with a binding requirement answers invalid_parameters,
    not binding_missing."""
    from anip_core import BindingRequirement

    calls: list = []
    capability = _capability("reserve", calls)
    capability.declaration.requires_binding = [
        BindingRequirement(type="quote", field="quote_id", source_capability="reserve"),
    ]
    service = ANIPService(
        service_id="test-service",
        capabilities=[capability],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    client = TestClient(app)

    resp = _invoke(client, "reserve", {"parameters": value})

    assert resp.status_code == 400, resp.text
    failure = resp.json()["failure"]
    assert failure["type"] == "invalid_parameters"
    assert failure["detail"] == f"reserve parameters must be an object, got {received}"
    assert failure["resolution"] == RESOLUTION
    assert failure["retry"] is False
    assert calls == []

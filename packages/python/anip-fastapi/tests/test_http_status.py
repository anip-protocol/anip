"""One HTTP status per failure type (SPEC.md §6.3 "HTTP Status Codes")."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_core import (
    BindingRequirement, CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    FAILURE_STATUS_CODES, SideEffect, SideEffectType, failure_status_code,
)
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability

API_KEY = "test-key-123"

# Every type the table lists and one it does not list. approval_required is
# left to the approval tests: raising it makes the runtime persist a request.
FAILURE_TYPES = sorted(set(FAILURE_STATUS_CODES) - {"approval_required"}) + ["seat_map_unavailable"]


def _raise_capability() -> Capability:
    """A capability whose handler fails with the type it is asked for."""

    def handler(ctx, params):
        raise ANIPError(
            params["type"], "provoked",
            resolution={"action": "contact_service_owner", "recovery_class": "terminal"})

    return Capability(
        declaration=CapabilityDeclaration(
            name="fail",
            description="Fail on request",
            inputs=[CapabilityInput(name="type", type="string", description="Failure type")],
            output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["fail"],
        ),
        handler=handler,
    )


def _bound_capability() -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name="bound",
            description="Needs a quote",
            inputs=[CapabilityInput(name="quote", type="object", required=False, description="Quote")],
            output=CapabilityOutput(type="object", fields=["ok"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["fail"],
            requires_binding=[BindingRequirement(type="quote", field="quote")],
        ),
        handler=lambda ctx, params: {"ok": True},
    )


@pytest.fixture
def client():
    service = ANIPService(
        service_id="test-status",
        capabilities=[_raise_capability(), _bound_capability()],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    return TestClient(app, raise_server_exceptions=False)


def _token(client: TestClient, capability: str = "fail", scope=("fail",)) -> str:
    resp = client.post(
        "/anip/tokens",
        json={"scope": list(scope), "capability": capability},
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("failure_type", FAILURE_TYPES)
def test_invoke_answers_with_the_status_of_the_failure_type(client, failure_type):
    resp = client.post(
        "/anip/invoke/fail", json={"parameters": {"type": failure_type}},
        headers=_auth(_token(client)))

    assert resp.json()["failure"]["type"] == failure_type
    assert resp.status_code == failure_status_code(failure_type)


def test_refusal_before_the_handler_uses_the_table(client):
    resp = client.post(
        "/anip/invoke/bound", json={"parameters": {}}, headers=_auth(_token(client, "bound")))
    assert resp.json()["failure"]["type"] == "binding_missing"
    assert resp.status_code == 403

    resp = client.post(
        "/anip/invoke/fail", json={"parameters": {"type": "x"}},
        headers=_auth(_token(client, "bound")))
    assert resp.json()["failure"]["type"] == "purpose_mismatch"
    assert resp.status_code == 403

    resp = client.post(
        "/anip/invoke/nothing_here", json={"parameters": {}}, headers=_auth(_token(client)))
    assert resp.json()["failure"]["type"] == "unknown_capability"
    assert resp.status_code == 404


def test_token_endpoint_uses_the_table(client):
    parent = client.post(
        "/anip/tokens", json={"scope": ["fail"], "capability": "fail"},
        headers=_auth(API_KEY)).json()

    resp = client.post(
        "/anip/tokens",
        json={"scope": ["fail", "admin"], "capability": "fail",
              "parent_token": parent["token_id"], "subject": "agent:child"},
        headers=_auth(parent["token"]))

    failure_type = resp.json()["failure"]["type"]
    assert failure_type in ("scope_escalation", "insufficient_authority")
    assert resp.status_code == 403


# --- a request body that is not JSON ------------------------------------------


def _assert_invalid_parameters(resp) -> dict:
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    failure = body["failure"]
    assert failure["type"] == "invalid_parameters"
    assert failure["detail"]
    assert failure["resolution"]["action"] == "retry_now"
    assert failure["resolution"]["recovery_class"] == "retry_now"
    assert failure["retry"] is False
    return failure


JSON = {"Content-Type": "application/json"}


@pytest.mark.parametrize("content", [b'{"parameters": ', b"", b"not json", b"\xff\xfe"])
def test_invoke_body_that_is_not_json_is_invalid_parameters(client, content):
    resp = client.post(
        "/anip/invoke/fail", content=content, headers={**_auth(_token(client)), **JSON})

    _assert_invalid_parameters(resp)


@pytest.mark.parametrize("content", [b"[1, 2]", b'"text"', b"5", b"null"])
def test_invoke_body_that_is_not_an_object_is_invalid_parameters(client, content):
    resp = client.post(
        "/anip/invoke/fail", content=content, headers={**_auth(_token(client)), **JSON})

    _assert_invalid_parameters(resp)


@pytest.mark.parametrize("parameters", [[1, 2], "text", 5, True])
def test_invoke_parameters_that_are_not_an_object_are_invalid_parameters(client, parameters):
    resp = client.post(
        "/anip/invoke/fail", json={"parameters": parameters}, headers=_auth(_token(client)))

    failure = _assert_invalid_parameters(resp)
    assert "parameters must be an object" in failure["detail"]
    assert resp.json()["invocation_id"].startswith("inv-")


def test_invoke_checks_the_credential_before_the_body(client):
    missing = client.post("/anip/invoke/fail", content=b'{"parameters": ', headers=JSON)
    assert missing.status_code == 401
    assert missing.json()["failure"]["type"] == "authentication_required"

    invalid = client.post(
        "/anip/invoke/fail", content=b'{"parameters": ', headers={**_auth("not-a-token"), **JSON})
    assert invalid.status_code == 401
    assert invalid.json()["failure"]["type"] == "invalid_token"


@pytest.mark.parametrize("content", [b'{"scope": ', b"", b"[1]", b'"text"', b"null"])
def test_token_request_body_that_is_not_a_json_object_is_invalid_parameters(client, content):
    resp = client.post("/anip/tokens", content=content, headers={**_auth(API_KEY), **JSON})

    _assert_invalid_parameters(resp)


def test_token_endpoint_checks_the_credential_before_the_body(client):
    resp = client.post("/anip/tokens", content=b'{"scope": ', headers=JSON)

    assert resp.status_code == 401
    assert resp.json()["failure"]["type"] == "authentication_required"


def test_binding_has_no_status_table_of_its_own():
    import anip_fastapi.routes as routes

    assert not hasattr(routes, "_failure_status")
    assert routes.failure_status_code is failure_status_code

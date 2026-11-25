"""Conformance tests for the checks that run before the handler on a
streaming invocation (``stream: true``).

Spec references: §6.3 ("Parameter Validation": "The check is the same in
every runtime, for unary and streaming invocations"; delegation, budget,
binding and control-requirement enforcement) and §6.6 (streaming).

A streaming invocation goes through the same checks, in the same order, as
a unary one. How a refusal made before the handler is delivered on a
streaming call is not specified yet: a JSON failure with the status of §6.3
"HTTP Status Codes", or an SSE ``failed`` event on a 200 stream. The tests
accept either and compare the failure with the unary answer to the same
request.

The tests need a capability that declares ``streaming`` in its
``response_modes`` and has an entry in ``--sample-inputs``; they skip with
the reason when the service has none.
"""
from __future__ import annotations

import copy
import json

import pytest

from conftest import issue_token


def _failure_of(resp) -> dict | None:
    """The failure object of a JSON response or of an SSE stream's terminal event."""
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        terminal = None
        event = None
        for line in resp.text.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event in ("completed", "failed"):
                terminal = (event, json.loads(line.split(":", 1)[1].strip()))
        assert terminal is not None, f"The stream has no terminal event: {resp.text[:300]!r}"
        event, data = terminal
        assert event == "failed", f"The streaming invocation completed: {data}"
        return data.get("failure")
    body = resp.json()
    assert body.get("success") is False, f"The streaming invocation succeeded: {body}"
    return body.get("failure")


@pytest.fixture(scope="module")
def streaming(client, bootstrap_bearer, manifest_capabilities, sample_inputs):
    """(name, declaration, sample) for a streaming-capable capability."""
    for name, declaration in manifest_capabilities.items():
        if "streaming" in (declaration.get("response_modes") or []) \
                and isinstance(sample_inputs.get(name), dict):
            return name, declaration, sample_inputs[name]
    pytest.skip("no capability declares the streaming response mode and has an entry "
                "in --sample-inputs")


def _invoke(client, token, name, parameters, *, stream):
    return client.post(
        f"/anip/invoke/{name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "stream": stream},
    )


def _same_refusal(client, token, name, parameters, expected_type):
    """The streaming call is refused with the same failure type as the unary call."""
    unary = _invoke(client, token, name, parameters, stream=False).json()
    assert (unary.get("failure") or {}).get("type") == expected_type, (
        f"Control: the unary call was expected to fail with {expected_type}, got {unary}"
    )
    failure = _failure_of(_invoke(client, token, name, parameters, stream=True))
    assert isinstance(failure, dict) and failure.get("type") == expected_type, (
        f"The unary call is refused with {expected_type}; the streaming call answered {failure}"
    )


class TestStreamingPreHandlerChecks:
    def test_missing_required_input(self, client, bootstrap_bearer, streaming):
        name, declaration, sample = streaming
        bindings = {b["field"] for b in declaration.get("requires_binding") or []}
        required = [
            i["name"] for i in declaration.get("inputs", [])
            if i.get("required", True) is not False and i["name"] in sample
            and i["name"] not in bindings and not (i.get("resolution") or {}).get("on_missing")
        ]
        if not required:
            pytest.skip(f"{name} declares no plain required input that the sample supplies")
        token = issue_token(client, declaration.get("minimum_scope", []), name,
                            bootstrap_bearer, task_id=None)
        parameters = copy.deepcopy(sample)
        del parameters[required[0]]
        _same_refusal(client, token, name, parameters, "invalid_parameters")

    def test_binding_missing(self, client, bootstrap_bearer, streaming):
        name, declaration, sample = streaming
        bindings = declaration.get("requires_binding") or []
        if not bindings:
            pytest.skip(f"{name} declares no binding requirement")
        token = issue_token(client, declaration.get("minimum_scope", []), name,
                            bootstrap_bearer, task_id=None)
        parameters = copy.deepcopy(sample)
        parameters.pop(bindings[0]["field"], None)
        _same_refusal(client, token, name, parameters, "binding_missing")

    def test_budget_exceeded(self, client, bootstrap_bearer, streaming):
        name, declaration, sample = streaming
        cost = declaration.get("cost") or {}
        financial = cost.get("financial") or {}
        if cost.get("certainty") != "fixed" or not financial.get("amount"):
            pytest.skip(f"{name} declares no fixed financial cost")
        token = issue_token(
            client, declaration.get("minimum_scope", []), name, bootstrap_bearer, task_id=None,
            budget={"currency": financial["currency"], "max_amount": financial["amount"] / 2})
        _same_refusal(client, token, name, copy.deepcopy(sample), "budget_exceeded")

    def test_unknown_approval_grant(self, client, bootstrap_bearer, streaming):
        name, declaration, sample = streaming
        token = issue_token(client, declaration.get("minimum_scope", []), name,
                            bootstrap_bearer, task_id=None)
        body = {"parameters": copy.deepcopy(sample), "approval_grant": "grant_conformance_none"}
        unary = client.post(f"/anip/invoke/{name}", headers={"Authorization": f"Bearer {token}"},
                            json=body).json()
        assert (unary.get("failure") or {}).get("type") == "grant_not_found", (
            f"Control: expected grant_not_found on the unary call, got {unary}"
        )
        failure = _failure_of(client.post(
            f"/anip/invoke/{name}", headers={"Authorization": f"Bearer {token}"},
            json={**body, "stream": True}))
        assert isinstance(failure, dict) and failure.get("type") == "grant_not_found", (
            f"The streaming call answered {failure}"
        )

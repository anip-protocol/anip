"""Conformance tests for the HTTP status of each failure type.

Spec reference: §6.3 "HTTP Status Codes": one status per failure type, the
same in every runtime and every HTTP binding, and 400 for a type the table
does not list.

Each test provokes one failure over HTTP, checks that it is the failure type
the test means to provoke, and compares the response status with the table.
Failures that need a capability, a binding requirement or an approval path
the service does not have are skipped with the reason.
"""
from __future__ import annotations

import copy
import time
import uuid

import pytest

from conftest import issue_token, issue_token_full

# §6.3 "HTTP Status Codes". A type that is not listed is 400.
HTTP_STATUS = {
    "authentication_required": 401,
    "invalid_token": 401,
    "token_expired": 401,
    "token_not_registered": 401,
    "scope_insufficient": 403,
    "insufficient_authority": 403,
    "purpose_mismatch": 403,
    "scope_escalation": 403,
    "constraint_escalation": 403,
    "broken_delegation_chain": 403,
    "delegation_depth_exceeded": 403,
    "parent_token_expired": 403,
    "budget_exceeded": 403,
    "budget_currency_mismatch": 403,
    "budget_not_enforceable": 403,
    "binding_missing": 403,
    "binding_stale": 403,
    "control_requirement_unsatisfied": 403,
    "approver_not_authorized": 403,
    "grant_requester_mismatch": 403,
    "unknown_capability": 404,
    "not_found": 404,
    "approval_request_not_found": 404,
    "unavailable": 409,
    "concurrent_lock": 409,
    "concurrent_request_rejected": 409,
    "approval_request_already_decided": 409,
    "approval_request_expired": 409,
    "grant_consumed": 409,
    "grant_expired": 409,
    "internal_error": 500,
    "service_unavailable": 503,
    # 400, stated in the table so that nobody has to infer it:
    "invalid_parameters": 400,
    "streaming_not_supported": 400,
    "approval_required": 400,
    "grant_not_found": 400,
    "grant_capability_mismatch": 400,
    "grant_scope_mismatch": 400,
    "grant_param_drift": 400,
    "grant_session_invalid": 400,
    "grant_type_not_allowed_by_policy": 400,
}
DEFAULT_STATUS = 400


def _failure_type(body) -> str | None:
    failure = body.get("failure") if isinstance(body, dict) else None
    return failure.get("type") if isinstance(failure, dict) else None


def _check(resp, expected_type=None) -> None:
    """The response is a failure of the expected type with the table's status."""
    try:
        body = resp.json()
    except ValueError:
        body = None
    failure_type = _failure_type(body)
    assert failure_type, (
        f"Expected an ANIP failure object, got {resp.status_code} {resp.text[:300]!r}"
    )
    if expected_type is not None:
        expected = (expected_type,) if isinstance(expected_type, str) else tuple(expected_type)
        assert failure_type in expected, (
            f"Expected failure type {' or '.join(expected)}, got {resp.status_code} {body['failure']}"
        )
    wanted = HTTP_STATUS.get(failure_type, DEFAULT_STATUS)
    assert resp.status_code == wanted, (
        f"'{failure_type}' is HTTP {wanted} (§6.3 HTTP Status Codes), got {resp.status_code}"
    )


def _invoke(client, token, capability, parameters, **body):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return client.post(f"/anip/invoke/{capability}", headers=headers,
                       json={"parameters": parameters, **body})


# --- invocation: authentication, delegation --------------------------------


class TestAuthenticationAndDelegation:
    def test_missing_credential(self, client, read_capability):
        name, _ = read_capability
        _check(_invoke(client, None, name, {}), "authentication_required")

    def test_invalid_token(self, client, read_capability):
        name, _ = read_capability
        _check(_invoke(client, "not-a-token", name, {}), "invalid_token")

    def test_unknown_capability(self, client, bootstrap_bearer, read_capability):
        name, scope = read_capability
        token = issue_token(client, scope, name, bootstrap_bearer, task_id=None)
        _check(_invoke(client, token, f"conformance_{uuid.uuid4().hex[:8]}", {}),
               "unknown_capability")

    def test_scope_does_not_cover_the_capability(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        read_name, read_scope = read_capability
        write_name, write_scope = write_capability
        if not write_scope or set(write_scope) <= set(read_scope):
            pytest.skip("needs a capability whose scope the read scope does not cover")
        token = issue_token(client, read_scope, write_name, bootstrap_bearer, task_id=None)
        _check(_invoke(client, token, write_name, {}),
               ("scope_insufficient", "insufficient_authority"))

    def test_token_bound_to_another_capability(
        self, client, bootstrap_bearer, read_capability, write_capability, all_scopes
    ):
        read_name, _ = read_capability
        write_name, _ = write_capability
        if read_name == write_name:
            pytest.skip("needs two capabilities")
        token = issue_token(client, all_scopes, write_name, bootstrap_bearer, task_id=None)
        _check(_invoke(client, token, read_name, {}), "purpose_mismatch")

    def test_task_id_differs_from_the_token(self, client, bootstrap_bearer, read_capability):
        name, scope = read_capability
        token = issue_token(client, scope, name, bootstrap_bearer, task_id="conformance-task-a")
        _check(_invoke(client, token, name, {}, task_id="conformance-task-b"),
               "purpose_mismatch")

    def test_streaming_requested_from_a_unary_capability(
        self, client, bootstrap_bearer, manifest_capabilities, sample_inputs
    ):
        unary = [
            n for n, d in manifest_capabilities.items()
            if "streaming" not in (d.get("response_modes") or ["unary"])
        ]
        if not unary:
            pytest.skip("every capability supports streaming")
        name = unary[0]
        token = issue_token(client, manifest_capabilities[name].get("minimum_scope", []),
                            name, bootstrap_bearer, task_id=None)
        _check(_invoke(client, token, name, copy.deepcopy(sample_inputs.get(name, {})),
                       stream=True),
               "streaming_not_supported")

    def test_child_token_with_broader_scope(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        read_name, read_scope = read_capability
        _, write_scope = write_capability
        if not write_scope or set(write_scope) <= set(read_scope):
            pytest.skip("needs a scope the read scope does not cover")
        status, parent = issue_token_full(client, read_scope, read_name, bootstrap_bearer,
                                          task_id=None)
        assert status == 200, f"Parent issuance failed: {status} {parent}"
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {parent['token']}"},
            json={"scope": list(read_scope) + list(write_scope), "capability": read_name,
                  "purpose_parameters": {}, "parent_token": parent["token_id"],
                  "subject": "agent:conformance-child"},
        )
        _check(resp, ("scope_escalation", "insufficient_authority"))

    def test_token_endpoint_without_credential(self, client, read_capability):
        name, scope = read_capability
        resp = client.post("/anip/tokens", json={
            "scope": scope, "capability": name, "purpose_parameters": {}})
        _check(resp, "authentication_required")

    def test_token_endpoint_with_an_unrecognised_credential(self, client, read_capability):
        """§6.3 Token Issuance: a credential the service does not recognise
        is ``authentication_required``, like no credential at all."""
        name, scope = read_capability
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer conformance-unknown-{uuid.uuid4().hex}"},
            json={"scope": scope, "capability": name, "purpose_parameters": {}})
        _check(resp, "authentication_required")

    @pytest.mark.parametrize("endpoint", ["permissions", "audit"])
    def test_protected_endpoint_without_credential(self, client, discovery, endpoint):
        path = discovery["endpoints"].get(endpoint)
        if not path:
            pytest.skip(f"the service does not advertise endpoints.{endpoint}")
        _check(client.post(path, json={}), "authentication_required")


# --- invocation: budget and binding ----------------------------------------


@pytest.fixture(scope="module")
def priced_binding(manifest_capabilities, sample_inputs):
    """(name, declaration, sample) for a capability with an estimated cost, a
    binding that carries the price, and a sample invocation."""
    for name, declaration in manifest_capabilities.items():
        cost = declaration.get("cost") or {}
        bindings = declaration.get("requires_binding") or []
        sample = sample_inputs.get(name)
        if (cost.get("certainty") == "estimated" and cost.get("financial") and bindings
                and isinstance(sample, dict)
                and isinstance(sample.get(bindings[0]["field"]), dict)
                and "price" in sample[bindings[0]["field"]]):
            return name, declaration, sample
    pytest.skip("no capability with an estimated cost, a priced binding and a sample invocation")


class TestBudgetAndBinding:
    def test_budget_exceeded(self, client, bootstrap_bearer, priced_binding):
        name, declaration, sample = priced_binding
        currency = declaration["cost"]["financial"]["currency"]
        token = issue_token(client, declaration.get("minimum_scope", []), name,
                            bootstrap_bearer, task_id=None,
                            budget={"currency": currency, "max_amount": 1})
        _check(_invoke(client, token, name, copy.deepcopy(sample)), "budget_exceeded")

    def test_budget_currency_mismatch(self, client, bootstrap_bearer, priced_binding):
        name, declaration, sample = priced_binding
        currency = declaration["cost"]["financial"]["currency"]
        other = "EUR" if currency != "EUR" else "GBP"
        token = issue_token(client, declaration.get("minimum_scope", []), name,
                            bootstrap_bearer, task_id=None,
                            budget={"currency": other, "max_amount": 100000})
        _check(_invoke(client, token, name, copy.deepcopy(sample)),
               "budget_currency_mismatch")

    def test_budget_not_enforceable(self, client, bootstrap_bearer, priced_binding):
        name, declaration, sample = priced_binding
        field = declaration["requires_binding"][0]["field"]
        currency = declaration["cost"]["financial"]["currency"]
        token = issue_token(client, declaration.get("minimum_scope", []), name,
                            bootstrap_bearer, task_id=None,
                            budget={"currency": currency, "max_amount": 100000})
        parameters = copy.deepcopy(sample)
        del parameters[field]["price"]
        _check(_invoke(client, token, name, parameters), "budget_not_enforceable")

    def test_binding_missing(self, client, bootstrap_bearer, binding_capability, sample_inputs):
        if binding_capability is None:
            pytest.skip("no capability with binding requirements")
        name, scope, bindings = binding_capability
        token = issue_token(client, scope, name, bootstrap_bearer, task_id=None)
        parameters = copy.deepcopy(sample_inputs.get(name, {}))
        for binding in bindings:
            parameters.pop(binding["field"], None)
        _check(_invoke(client, token, name, parameters), "binding_missing")

    def test_binding_stale(self, client, bootstrap_bearer, binding_capability, sample_inputs):
        if binding_capability is None:
            pytest.skip("no capability with binding requirements")
        name, scope, bindings = binding_capability
        aged = [b for b in bindings if b.get("max_age")]
        sample = sample_inputs.get(name)
        if not aged or not isinstance(sample, dict) \
                or not isinstance(sample.get(aged[0]["field"]), dict) \
                or "issued_at" not in sample[aged[0]["field"]]:
            pytest.skip("no binding with max_age whose sample value carries issued_at")
        token = issue_token(client, scope, name, bootstrap_bearer, task_id=None)
        parameters = copy.deepcopy(sample)
        parameters[aged[0]["field"]]["issued_at"] = int(time.time()) - 400 * 24 * 3600
        _check(_invoke(client, token, name, parameters), "binding_stale")

    def test_control_requirement_unsatisfied(
        self, client, bootstrap_bearer, cost_ceiling_capability, sample_inputs
    ):
        if cost_ceiling_capability is None:
            pytest.skip("no capability with a cost_ceiling control requirement")
        name, scope = cost_ceiling_capability
        token = issue_token(client, scope, name, bootstrap_bearer, task_id=None)
        _check(_invoke(client, token, name, copy.deepcopy(sample_inputs.get(name, {}))),
               "control_requirement_unsatisfied")


# --- invocation: parameters ------------------------------------------------


class TestParameters:
    def test_invalid_parameters(self, client, bootstrap_bearer, manifest_capabilities):
        for name, declaration in manifest_capabilities.items():
            required = [i["name"] for i in declaration.get("inputs", [])
                        if i.get("required", True) is not False]
            if required and not declaration.get("requires_binding"):
                break
        else:
            pytest.skip("no capability without requires_binding declares a required input")
        token = issue_token(client, declaration.get("minimum_scope", []), name,
                            bootstrap_bearer, task_id=None)
        _check(_invoke(client, token, name, {}), "invalid_parameters")


    def test_invoke_body_is_not_json(self, client, bootstrap_bearer, read_capability):
        """§6.3: a request body that is not JSON is ``invalid_parameters``,
        as it is at POST {approval_grants} (§4.9 step 2)."""
        name, scope = read_capability
        token = issue_token(client, scope, name, bootstrap_bearer, task_id=None)
        resp = client.post(
            f"/anip/invoke/{name}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            content=b'{"parameters": ',
        )
        _check(resp, "invalid_parameters")

    def test_token_request_body_is_not_json(self, client, bootstrap_bearer):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}",
                     "Content-Type": "application/json"},
            content=b'{"scope": ',
        )
        _check(resp, "invalid_parameters")


# --- approvals -------------------------------------------------------------


class Approvals:
    def __init__(self, client, bootstrap_bearer, discovery, capability, declaration, sample):
        self.client = client
        self.bootstrap_bearer = bootstrap_bearer
        self.capability = capability
        self.scope = list(declaration.get("minimum_scope", []))
        self.policy = declaration["grant_policy"]
        self.sample = sample
        self.grants_path = discovery["endpoints"]["approval_grants"]
        self.requester = issue_token(client, self.scope, capability, bootstrap_bearer,
                                     task_id=None)
        self.approver = issue_token(client, [f"approver:{capability}"], capability,
                                    bootstrap_bearer, task_id=None)

    def parameters(self, key="parameters"):
        if key not in self.sample:
            pytest.skip(f"$approval.{key} is not in --sample-inputs")
        return copy.deepcopy(self.sample[key])

    def invoke(self, parameters, *, token=None, capability=None, **body):
        return _invoke(self.client, token or self.requester, capability or self.capability,
                       parameters, **body)

    def request(self) -> str:
        resp = self.invoke(self.parameters())
        body = resp.json()
        assert _failure_type(body) == "approval_required", (
            f"Expected the $approval sample to need approval, got {resp.status_code} {body}"
        )
        return body["failure"]["approval_required"]["approval_request_id"]

    def post_grant(self, body, *, token=None):
        return self.client.post(
            self.grants_path, headers={"Authorization": f"Bearer {token or self.approver}"},
            json=body)

    def grant(self) -> str:
        resp = self.post_grant({"approval_request_id": self.request(), "grant_type": "one_time"})
        assert resp.status_code == 200, f"Grant issuance failed: {resp.status_code} {resp.text[:300]}"
        return resp.json()["grant_id"]


@pytest.fixture(scope="module")
def approvals(client, bootstrap_bearer, discovery, manifest_capabilities, sample_inputs):
    sample = sample_inputs.get("$approval")
    if not sample:
        pytest.skip("--sample-inputs has no '$approval' entry")
    capability = sample.get("capability")
    declaration = manifest_capabilities.get(capability) or {}
    if not declaration.get("grant_policy") or "approval_grants" not in discovery["endpoints"]:
        pytest.skip(f"'{capability}' declares no grant_policy on this service")
    return Approvals(client, bootstrap_bearer, discovery, capability, declaration, sample)


class TestApprovals:
    def test_approval_required(self, approvals):
        _check(approvals.invoke(approvals.parameters()), "approval_required")

    def test_grant_consumed(self, approvals):
        """A spent one_time grant is a state conflict: 409."""
        grant = approvals.grant()
        first = approvals.invoke(approvals.parameters(), approval_grant=grant)
        assert first.status_code == 200, f"The continuation failed: {first.text[:300]}"

        _check(approvals.invoke(approvals.parameters(), approval_grant=grant), "grant_consumed")

    def test_grant_not_found(self, approvals):
        _check(approvals.invoke(approvals.parameters(),
                                approval_grant=f"grant_{uuid.uuid4().hex[:12]}"),
               "grant_not_found")

    def test_grant_param_drift(self, approvals):
        grant = approvals.grant()
        _check(approvals.invoke(approvals.parameters("drifted_parameters"), approval_grant=grant),
               "grant_param_drift")

    def test_grant_capability_mismatch(self, approvals, read_capability, sample_inputs):
        other, other_scope = read_capability
        if other == approvals.capability:
            pytest.skip("needs a second capability")
        token = issue_token(approvals.client, approvals.scope + other_scope, other,
                            approvals.bootstrap_bearer, task_id=None)
        grant = approvals.grant()
        _check(approvals.invoke(copy.deepcopy(sample_inputs.get(other, {})), token=token,
                                capability=other, approval_grant=grant),
               "grant_capability_mismatch")

    def test_grant_scope_mismatch(self, approvals):
        dotted = [s for s in approvals.scope if "." in s]
        if not dotted:
            pytest.skip("needs a dotted minimum scope")
        parents = [s.rsplit(".", 1)[0] if s in dotted else s for s in approvals.scope]
        token = issue_token(approvals.client, parents, approvals.capability,
                            approvals.bootstrap_bearer, task_id=None)
        grant = approvals.grant()
        _check(approvals.invoke(approvals.parameters(), token=token, approval_grant=grant),
               "grant_scope_mismatch")

    def test_grant_requester_mismatch(self, approvals, other_bootstrap_bearer):
        """The grant belongs to another principal: its authority does not
        cover the request, 403."""
        token = issue_token(approvals.client, approvals.scope, approvals.capability,
                            other_bootstrap_bearer, task_id=None)
        grant = approvals.grant()
        _check(approvals.invoke(approvals.parameters(), token=token, approval_grant=grant),
               "grant_requester_mismatch")

    def test_approval_request_not_found(self, approvals):
        _check(approvals.post_grant({"approval_request_id": f"apr_{uuid.uuid4().hex[:12]}",
                                     "grant_type": "one_time"}),
               "approval_request_not_found")

    def test_approval_request_already_decided(self, approvals):
        request_id = approvals.request()
        body = {"approval_request_id": request_id, "grant_type": "one_time"}
        assert approvals.post_grant(body).status_code == 200

        _check(approvals.post_grant(body), "approval_request_already_decided")

    def test_approver_not_authorized(self, approvals):
        _check(approvals.post_grant({"approval_request_id": approvals.request(),
                                     "grant_type": "one_time"}, token=approvals.requester),
               "approver_not_authorized")

    def test_grant_type_not_allowed_by_policy(self, approvals):
        refused = [t for t in ("one_time", "session_bound")
                   if t not in approvals.policy["allowed_grant_types"]]
        if not refused:
            pytest.skip("the capability's grant_policy allows every grant type")
        body = {"approval_request_id": approvals.request(), "grant_type": refused[0]}
        if refused[0] == "session_bound":
            body["session_id"] = "conformance-session"
        _check(approvals.post_grant(body), "grant_type_not_allowed_by_policy")

    def test_malformed_grant_request(self, approvals):
        _check(approvals.post_grant({"grant_type": "one_time"}), "invalid_parameters")

    def test_grant_endpoint_without_credential(self, approvals):
        resp = approvals.client.post(approvals.grants_path, json={
            "approval_request_id": "apr_none", "grant_type": "one_time"})
        _check(resp, "authentication_required")

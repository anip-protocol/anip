"""Conformance tests for approval requests and approval grants.

Spec references: §4.7 (Approval Requests), §4.8 (Approval Grants), §4.9
(Approval Grant Issuance, ``POST {approval_grants}``), §4.5 (failure
semantics) and §6.1 (``endpoints.approval_grants``: "required when service
emits approval_required").

The tests need a service that declares a capability with a ``grant_policy``
and a ``$approval`` entry in ``--sample-inputs`` telling the suite how to
reach the approval path::

    "$approval": {
      "capability": "book_flight",
      "parameters": {...},                  # invocation that needs approval
      "drifted_parameters": {...},          # optional: also needs approval, differs
      "handler_failure_parameters": {...},  # optional: needs approval, then fails
      "request_expires_within_seconds": 3   # optional: lifetime of a request
    }

Without either, every test here skips with the reason.

A refusal is checked three ways: the specific failure type, no ``result`` in
the response, and the audit entry of that invocation recording a failure.
The audit log is the only view of a handler's effect that the protocol
itself offers; the tests do not look at service state by other means.

Tokens come from the ``--bootstrap-bearer`` credential, so requester and
approver share a root principal, except in ``TestRequesterBinding``, which
also needs ``--other-bootstrap-bearer`` (a second principal) and skips
without it.
"""
from __future__ import annotations

import copy
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from conftest import assert_complete_failure as _assert_complete_failure, issue_token

GRANT_TYPES = {"one_time", "session_bound"}

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


# --- helpers ---------------------------------------------------------------


def _failure_type(body) -> str | None:
    failure = body.get("failure") if isinstance(body, dict) else None
    return failure.get("type") if isinstance(failure, dict) else None


def _json(resp: httpx.Response):
    try:
        return resp.json()
    except ValueError:
        return None


def _timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp with any number of fractional digits."""
    match = re.fullmatch(r"(.*?)(\.\d+)?(Z|[+-]\d{2}:\d{2})", value)
    assert match, f"not an ISO 8601 timestamp with a UTC offset: {value!r}"
    head, fraction, zone = match.groups()
    fraction = (fraction or ".0")[:7]
    zone = "+00:00" if zone == "Z" else zone
    return datetime.fromisoformat(f"{head}{fraction}{zone}")


def _token(client, bootstrap_bearer, scope, capability, **extra) -> dict:
    """Issue a token and return the whole issuance response."""
    body = {"scope": scope, "capability": capability, "purpose_parameters": {}}
    body.update(extra)
    resp = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {bootstrap_bearer}"},
        json=body,
    )
    data = resp.json()
    assert resp.status_code == 200 and data.get("issued") is True, (
        f"Token issuance failed: {resp.status_code} {data}"
    )
    return data


class ApprovalFlow:
    """One service's approval path and the calls the tests make along it."""

    def __init__(self, client, bootstrap_bearer, discovery, capability, declaration, sample):
        self.client = client
        self.bootstrap_bearer = bootstrap_bearer
        self.capability = capability
        self.scope = list(declaration.get("minimum_scope", []))
        self.policy = declaration["grant_policy"]
        self.sample = sample
        self.grants_path = discovery["endpoints"]["approval_grants"]
        self.requester = issue_token(
            client, self.scope, capability, bootstrap_bearer, task_id=None)
        self.approver = issue_token(
            client, [f"approver:{capability}"], capability, bootstrap_bearer, task_id=None)

    def parameters(self, key: str = "parameters") -> dict:
        if key not in self.sample:
            pytest.skip(f"$approval.{key} is not in --sample-inputs")
        return copy.deepcopy(self.sample[key])

    def invoke(self, parameters, *, token=None, capability=None, **body) -> dict:
        resp = self.client.post(
            f"/anip/invoke/{capability or self.capability}",
            headers={"Authorization": f"Bearer {token or self.requester}"},
            json={"parameters": parameters, **body},
        )
        data = _json(resp)
        assert isinstance(data, dict), (
            f"Invoke answered {resp.status_code} without a JSON object: {resp.text[:200]!r}"
        )
        return data

    def request_approval(self, parameters=None, *, token=None) -> dict:
        """Invoke so that approval is required; return the failure metadata."""
        data = self.invoke(parameters or self.parameters(), token=token)
        assert _failure_type(data) == "approval_required", (
            f"Expected the sample parameters to need approval, got {data}"
        )
        return data["failure"]["approval_required"]

    def post_grant(self, body=None, *, token=None, **kwargs) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token or self.approver}"}
        if "content" in kwargs:
            headers["Content-Type"] = "application/json"
            return self.client.post(self.grants_path, headers=headers, **kwargs)
        return self.client.post(self.grants_path, headers=headers, json=body)

    def issue_grant(self, request_id: str, grant_type: str = "one_time", **extra) -> dict:
        resp = self.post_grant(
            {"approval_request_id": request_id, "grant_type": grant_type, **extra})
        data = _json(resp)
        assert resp.status_code == 200 and isinstance(data, dict) and "grant_id" in data, (
            f"Grant issuance failed: {resp.status_code} {resp.text[:300]}"
        )
        return data

    def approved_grant(self, parameters=None, *, token=None, grant_type="one_time", **extra) -> dict:
        """Request approval and have the approver issue a grant."""
        meta = self.request_approval(parameters, token=token)
        return self.issue_grant(meta["approval_request_id"], grant_type, **extra)

    def audit(self, query: str, *, token=None) -> list[dict]:
        resp = self.client.post(
            f"/anip/audit?{query}",
            headers={"Authorization": f"Bearer {token or self.requester}"},
        )
        assert resp.status_code == 200, f"Audit query failed: {resp.status_code} {resp.text[:200]}"
        return resp.json()["entries"]

    def audit_entry(self, invocation_id: str, *, token=None) -> dict:
        """§6.3: "The invocation_id filter returns the single entry for that
        invocation."""
        entries = [
            e for e in self.audit(f"invocation_id={invocation_id}", token=token)
            if e.get("invocation_id") == invocation_id
        ]
        assert len(entries) == 1, (
            f"Expected one audit entry for {invocation_id}, got {len(entries)}"
        )
        return entries[0]

    def assert_refused(self, data: dict, failure_type: str, *, token=None) -> None:
        """The invocation was refused with this type and did not execute."""
        assert data.get("success") is False, f"Expected a refusal, got {data}"
        assert data.get("result") is None, f"A refused invocation returned a result: {data}"
        assert _failure_type(data) == failure_type, (
            f"Expected failure type '{failure_type}', got {data.get('failure')}"
        )
        _assert_complete_failure(data["failure"])
        entry = self.audit_entry(data["invocation_id"], token=token)
        assert entry["success"] is False, (
            f"The audit log records the refused invocation as executed: {entry}"
        )

    def assert_executed(self, data: dict, *, token=None) -> None:
        assert data.get("success") is True, f"Expected the invocation to succeed, got {data}"
        assert isinstance(data.get("result"), dict), f"No result on success: {data}"
        entry = self.audit_entry(data["invocation_id"], token=token)
        assert entry["success"] is True, f"The audit log records a failure: {entry}"

    def assert_no_grant(self, resp: httpx.Response, failure_type: str | None) -> None:
        """No grant came back; the response is an ANIP failure object."""
        data = _json(resp)
        assert resp.status_code != 200, f"A grant request was accepted: {resp.text[:300]}"
        assert isinstance(data, dict) and "grant_id" not in data, (
            f"Expected an ANIP failure object, got {resp.status_code} {resp.text[:300]!r}"
        )
        assert isinstance(data.get("failure"), dict) and data["failure"].get("type"), (
            f"Expected an ANIP failure object, got {data}"
        )
        _assert_complete_failure(data["failure"])
        if failure_type is not None:
            assert _failure_type(data) == failure_type, (
                f"Expected failure type '{failure_type}', got {data['failure']}"
            )


@pytest.fixture(scope="module")
def approval_capabilities(manifest_capabilities) -> dict:
    """Capabilities that can emit approval_required: those with a grant_policy."""
    return {
        name: decl for name, decl in manifest_capabilities.items()
        if decl.get("grant_policy")
    }


@pytest.fixture(scope="module")
def flow(client, bootstrap_bearer, discovery, approval_capabilities, sample_inputs) -> ApprovalFlow:
    if not approval_capabilities:
        pytest.skip("the service declares no capability with a grant_policy, "
                    "so it cannot emit approval_required")
    sample = sample_inputs.get("$approval")
    if not sample:
        pytest.skip("--sample-inputs has no '$approval' entry describing how to "
                    f"trigger approval (candidates: {sorted(approval_capabilities)})")
    capability = sample.get("capability")
    if capability not in approval_capabilities:
        pytest.skip(f"$approval.capability '{capability}' declares no grant_policy on this service")
    if "approval_grants" not in discovery.get("endpoints", {}):
        pytest.fail("the service declares a grant_policy but discovery has no "
                    "endpoints.approval_grants (§6.1)")
    return ApprovalFlow(client, bootstrap_bearer, discovery, capability,
                        approval_capabilities[capability], sample)


@pytest.fixture(scope="module")
def session_bound(flow) -> ApprovalFlow:
    if "session_bound" not in flow.policy["allowed_grant_types"]:
        pytest.skip("the capability's grant_policy does not allow session_bound grants")
    return flow


# --- §6.1 discovery --------------------------------------------------------


class TestDiscovery:
    def test_discovery_advertises_the_approval_grants_endpoint(self, discovery, approval_capabilities):
        """§6.1: ``approval_grants`` is "required when service emits
        approval_required"."""
        if not approval_capabilities:
            pytest.skip("the service declares no capability with a grant_policy")
        path = discovery["endpoints"].get("approval_grants")
        assert isinstance(path, str) and path.startswith("/"), (
            f"endpoints.approval_grants missing from discovery although "
            f"{sorted(approval_capabilities)} can require approval: {discovery['endpoints']}"
        )

    def test_advertised_endpoint_exists(self, client, discovery, approval_capabilities):
        """§8.2: "All declared endpoints resolve (return non-404)"."""
        if not approval_capabilities:
            pytest.skip("the service declares no capability with a grant_policy")
        path = discovery["endpoints"].get("approval_grants")
        assert path, "endpoints.approval_grants missing from discovery"
        resp = client.post(path, json={"approval_request_id": "apr_none", "grant_type": "one_time"})
        assert resp.status_code not in (404, 405), (
            f"POST {path} is advertised but answers {resp.status_code}"
        )


# --- §4.7 approval requests ------------------------------------------------


class TestApprovalRequired:
    def test_invocation_under_the_threshold_needs_no_approval(self, flow, sample_inputs):
        """Control: the capability's ordinary sample input executes directly."""
        if flow.capability not in sample_inputs:
            pytest.skip(f"no ordinary sample input for {flow.capability}")
        data = flow.invoke(copy.deepcopy(sample_inputs[flow.capability]))
        flow.assert_executed(data)

    def test_approval_required_failure_shape(self, flow):
        """§4.7 "Approval-Required Failure Response": the failure carries
        ApprovalRequiredMetadata and the request_approval resolution."""
        data = flow.invoke(flow.parameters())

        flow.assert_refused(data, "approval_required")
        failure = data["failure"]
        assert isinstance(failure.get("detail"), str) and failure["detail"]
        resolution = failure.get("resolution")
        assert isinstance(resolution, dict), f"No resolution on the failure: {failure}"
        assert resolution.get("action") == "request_approval"
        assert resolution.get("recovery_class") == "wait_then_retry"

        meta = failure.get("approval_required")
        assert isinstance(meta, dict), f"No approval_required metadata: {failure}"
        assert set(meta) == {
            "approval_request_id", "preview_digest",
            "requested_parameters_digest", "grant_policy",
        }, f"Unexpected ApprovalRequiredMetadata fields: {sorted(meta)}"
        assert isinstance(meta["approval_request_id"], str) and meta["approval_request_id"]
        assert DIGEST.fullmatch(meta["preview_digest"]), meta["preview_digest"]
        assert DIGEST.fullmatch(meta["requested_parameters_digest"]), meta["requested_parameters_digest"]

        policy = meta["grant_policy"]
        assert set(policy) == {
            "allowed_grant_types", "default_grant_type", "expires_in_seconds", "max_uses",
        }, f"Unexpected grant_policy fields: {sorted(policy)}"
        assert policy["allowed_grant_types"], "allowed_grant_types is empty"
        assert set(policy["allowed_grant_types"]) <= GRANT_TYPES
        assert policy["default_grant_type"] in policy["allowed_grant_types"]
        assert type(policy["expires_in_seconds"]) is int and policy["expires_in_seconds"] >= 1
        assert type(policy["max_uses"]) is int and policy["max_uses"] >= 1
        assert policy == flow.policy, (
            f"The failure's grant_policy {policy} differs from the declared one {flow.policy}"
        )

    def test_approval_required_is_marked_not_retryable(self, flow):
        """§4.7 shows ``retry: false`` on the failure; §4.5: retry says
        "whether the same request could succeed after the resolution is
        applied", and the schema default for an absent ``retry`` is true."""
        data = flow.invoke(flow.parameters())

        assert _failure_type(data) == "approval_required", data
        assert data["failure"].get("retry") is False, (
            f"Expected retry: false on approval_required, got "
            f"{data['failure'].get('retry', '<absent>')!r}"
        )

    def test_each_approval_required_names_a_new_request(self, flow):
        """§4.7: approval_request_id is a "collision-resistant identifier";
        the same parameters yield the same parameters digest."""
        parameters = flow.parameters()
        first = flow.request_approval(parameters)
        second = flow.request_approval(parameters)

        assert first["approval_request_id"] != second["approval_request_id"]
        assert first["requested_parameters_digest"] == second["requested_parameters_digest"]

    def test_different_parameters_have_a_different_digest(self, flow):
        first = flow.request_approval(flow.parameters())
        second = flow.request_approval(flow.parameters("drifted_parameters"))

        assert first["requested_parameters_digest"] != second["requested_parameters_digest"]


# --- §4.9 grant issuance ---------------------------------------------------


class TestGrantIssuance:
    def test_approver_receives_a_signed_grant(self, flow):
        """§4.9: "Response (200): A signed ApprovalGrant (§4.8)", with
        capability, scope, digests and requester copied from the request."""
        meta = flow.request_approval()
        before = datetime.now(timezone.utc)

        resp = flow.post_grant(
            {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"})

        grant = _json(resp)
        assert resp.status_code == 200, f"Issuance failed: {resp.status_code} {resp.text[:300]}"
        required = {
            "grant_id", "approval_request_id", "grant_type", "capability", "scope",
            "approved_parameters_digest", "preview_digest", "requester", "approver",
            "issued_at", "expires_at", "max_uses", "use_count", "signature",
        }
        assert required <= set(grant), f"Grant lacks {sorted(required - set(grant))}"
        assert set(grant) <= required | {"session_id"}, (
            f"Grant has fields outside §4.8: {sorted(set(grant) - required - {'session_id'})}"
        )
        assert isinstance(grant["grant_id"], str) and grant["grant_id"]
        assert grant["approval_request_id"] == meta["approval_request_id"]
        assert grant["grant_type"] == "one_time"
        assert grant["capability"] == flow.capability
        assert isinstance(grant["scope"], list) and all(isinstance(s, str) for s in grant["scope"])
        assert grant["approved_parameters_digest"] == meta["requested_parameters_digest"]
        assert grant["preview_digest"] == meta["preview_digest"]
        assert isinstance(grant["requester"], dict) and grant["requester"]
        assert isinstance(grant["approver"], dict) and grant["approver"]
        assert grant["max_uses"] == 1, "§4.8: a one_time grant MUST set max_uses: 1"
        assert grant["use_count"] == 0
        assert grant.get("session_id") is None, "§4.8: session_id MUST be null unless session_bound"
        assert isinstance(grant["signature"], str) and grant["signature"]

        issued, expires = _timestamp(grant["issued_at"]), _timestamp(grant["expires_at"])
        assert abs(issued - before) < timedelta(seconds=30), f"issued_at is not now: {grant['issued_at']}"
        # One second of slack for clock reads taken apart inside the service.
        limit = timedelta(seconds=flow.policy["expires_in_seconds"] + 1)
        assert timedelta(0) < expires - issued <= limit, (
            f"Grant lifetime {expires - issued} exceeds grant_policy.expires_in_seconds"
        )

    def test_grant_ids_are_unique(self, flow):
        first, second = flow.approved_grant(), flow.approved_grant()

        assert first["grant_id"] != second["grant_id"]
        assert first["approval_request_id"] != second["approval_request_id"]

    def test_approver_may_shorten_the_grant_lifetime(self, flow):
        """§4.7: "Approvers MAY issue shorter; MUST NOT exceed"."""
        grant = flow.approved_grant(expires_in_seconds=1)

        lifetime = _timestamp(grant["expires_at"]) - _timestamp(grant["issued_at"])
        assert timedelta(0) < lifetime <= timedelta(seconds=2), f"Lifetime is {lifetime}"

    def test_grant_content_comes_from_the_request_not_the_body(self, flow, read_capability):
        """§4.8: capability and scope "are NOT taken from approver-supplied
        input". The issuance schema allows no such fields, so a service may
        instead reject the body as malformed."""
        meta = flow.request_approval()

        resp = flow.post_grant({
            "approval_request_id": meta["approval_request_id"], "grant_type": "one_time",
            "capability": read_capability[0], "scope": ["conformance.other"],
            "approved_parameters_digest": "sha256:" + "0" * 64,
        })

        if resp.status_code == 200:
            grant = resp.json()
            assert grant["capability"] == flow.capability
            assert "conformance.other" not in grant["scope"]
            assert grant["approved_parameters_digest"] == meta["requested_parameters_digest"]
        else:
            flow.assert_no_grant(resp, "invalid_parameters")

    @pytest.mark.parametrize("credential,failure_type", [
        ("missing", "authentication_required"), ("invalid", "invalid_token"),
    ])
    def test_unauthenticated_caller_gets_no_grant(self, flow, credential, failure_type):
        """§4.9 step 1: the bearer is authenticated before anything else.
        "Missing → authentication_required; invalid → invalid_token (HTTP
        401, as on every other protected endpoint)"."""
        meta = flow.request_approval()
        body = {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"}
        headers = {} if credential == "missing" else {"Authorization": "Bearer not-a-token"}

        resp = flow.client.post(flow.grants_path, headers=headers, json=body)

        assert resp.status_code == 401, f"Expected 401, got {resp.status_code} {resp.text[:200]}"
        flow.assert_no_grant(resp, failure_type)
        # The request was left pending: the approver can still decide it.
        flow.issue_grant(meta["approval_request_id"])

    def test_bootstrap_credential_is_not_an_approver_token(self, flow):
        """§4.9: the caller authenticates with a "Bearer token whose scope
        includes approver:<capability>". The bootstrap credential carries no
        scope and issues no grant."""
        meta = flow.request_approval()

        resp = flow.post_grant(
            {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"},
            token=flow.bootstrap_bearer)

        flow.assert_no_grant(resp, "invalid_token")
        flow.issue_grant(meta["approval_request_id"])

    def test_requester_cannot_approve_its_own_request(self, flow):
        """§4.9 step 5: "Approver scope must cover this specific capability.
        Missing → approver_not_authorized". The capability's own scope is
        not approver scope."""
        meta = flow.request_approval()

        resp = flow.post_grant(
            {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"},
            token=flow.requester)

        flow.assert_no_grant(resp, "approver_not_authorized")
        flow.issue_grant(meta["approval_request_id"])

    def test_approver_scope_for_another_capability_is_refused(self, flow, read_capability):
        """§4.9 step 5: authority is checked "against the loaded request's
        capability"."""
        other = read_capability[0]
        if other == flow.capability:
            pytest.skip("needs a second capability")
        token = issue_token(flow.client, [f"approver:{other}"], other,
                            flow.bootstrap_bearer, task_id=None)
        meta = flow.request_approval()

        resp = flow.post_grant(
            {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"},
            token=token)

        flow.assert_no_grant(resp, "approver_not_authorized")
        flow.issue_grant(meta["approval_request_id"])

    def test_unknown_request_is_not_found(self, flow):
        """§4.9 step 3: "Missing → approval_request_not_found"."""
        resp = flow.post_grant({
            "approval_request_id": f"apr_{uuid.uuid4().hex[:12]}", "grant_type": "one_time"})

        flow.assert_no_grant(resp, "approval_request_not_found")

    def test_decided_request_cannot_be_granted_again(self, flow):
        """§4.9 step 4: "If decided → approval_request_already_decided";
        §4.8: approval_request_id is "UNIQUE across grants"."""
        meta = flow.request_approval()
        first = flow.issue_grant(meta["approval_request_id"])

        resp = flow.post_grant(
            {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"})

        flow.assert_no_grant(resp, "approval_request_already_decided")
        # The grant already issued is unaffected.
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=first["grant_id"]))

    def test_decided_state_is_checked_before_approver_authority(self, flow):
        """§4.9 "Validation order (security-relevant)": step 4 (pending and
        not expired) precedes step 5 ("**Now** validate approver
        authority")."""
        meta = flow.request_approval()
        flow.issue_grant(meta["approval_request_id"])

        resp = flow.post_grant(
            {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"},
            token=flow.requester)

        flow.assert_no_grant(resp, "approval_request_already_decided")

    def test_expired_request_cannot_be_granted(self, flow):
        """§4.9 step 4: "If expired → approval_request_expired"."""
        lifetime = flow.sample.get("request_expires_within_seconds")
        if lifetime is None:
            pytest.skip("$approval.request_expires_within_seconds is not in --sample-inputs: "
                        "the lifetime of an approval request is not visible over HTTP")
        if lifetime > 30:
            pytest.skip(f"approval requests live {lifetime}s, too long to wait for")
        meta = flow.request_approval()
        time.sleep(lifetime + 1)

        resp = flow.post_grant(
            {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"})

        flow.assert_no_grant(resp, "approval_request_expired")

    @pytest.mark.parametrize("case", ["not_json", "no_grant_type", "no_request_id"])
    def test_malformed_body_is_invalid_parameters(self, flow, case):
        """§4.9 step 2: "Parse body. Malformed → invalid_parameters"."""
        meta = flow.request_approval()
        if case == "not_json":
            resp = flow.post_grant(content=b'{"approval_request_id": ')
        elif case == "no_grant_type":
            resp = flow.post_grant({"approval_request_id": meta["approval_request_id"]})
        else:
            resp = flow.post_grant({"grant_type": "one_time"})

        flow.assert_no_grant(resp, "invalid_parameters")
        flow.issue_grant(meta["approval_request_id"])

    @pytest.mark.parametrize("case", [
        "session_bound_without_session_id", "one_time_with_session_id",
        "one_time_with_max_uses_2", "expires_in_seconds_zero", "max_uses_zero",
    ])
    def test_body_outside_the_issuance_schema_is_invalid_parameters(self, flow, case):
        """§4.9 step 2 with the IssueApprovalGrantRequest schema (§9: the
        schemas are "authoritative for structure"): session_id is required
        for session_bound and null for one_time, one_time allows max_uses 1
        only, expires_in_seconds and max_uses are at least 1."""
        extra = {
            "session_bound_without_session_id": {"grant_type": "session_bound"},
            "one_time_with_session_id": {"grant_type": "one_time", "session_id": "conformance"},
            "one_time_with_max_uses_2": {"grant_type": "one_time", "max_uses": 2},
            "expires_in_seconds_zero": {"grant_type": "one_time", "expires_in_seconds": 0},
            "max_uses_zero": {"grant_type": "one_time", "max_uses": 0},
        }[case]
        meta = flow.request_approval()

        resp = flow.post_grant({"approval_request_id": meta["approval_request_id"], **extra})

        flow.assert_no_grant(resp, "invalid_parameters")
        flow.issue_grant(meta["approval_request_id"])

    @pytest.mark.parametrize("field", ["expires_in_seconds", "max_uses"])
    def test_grant_cannot_exceed_the_policy(self, flow, field):
        """§4.9 step 7: expires_at "≤ now + grant_policy.expires_in_seconds",
        max_uses "≤ grant_policy.max_uses". The spec names no failure type
        for this step, so none is asserted."""
        body = {"grant_type": "one_time", field: flow.policy[field] + 1}
        if field == "max_uses":
            if "session_bound" not in flow.policy["allowed_grant_types"]:
                pytest.skip("only a session_bound grant may ask for more than one use")
            body.update(grant_type="session_bound", session_id="conformance")
        meta = flow.request_approval()

        resp = flow.post_grant({"approval_request_id": meta["approval_request_id"], **body})

        flow.assert_no_grant(resp, None)
        flow.issue_grant(meta["approval_request_id"])

    def test_concurrent_issuance_yields_one_grant(self, flow, base_url):
        """§4.9 step 10: the atomic transition "prevents two approvers from
        concurrently issuing two grants for the same request"."""
        meta = flow.request_approval()
        body = {"approval_request_id": meta["approval_request_id"], "grant_type": "one_time"}

        def issue(_):
            with httpx.Client(base_url=base_url, timeout=30) as own:
                resp = own.post(flow.grants_path, json=body,
                                headers={"Authorization": f"Bearer {flow.approver}"})
                return resp.status_code, _json(resp)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(issue, range(8)))

        grants = [data for status, data in results if status == 200]
        refusals = [_failure_type(data) for status, data in results if status != 200]
        assert len(grants) == 1, f"{len(grants)} grants were issued for one request"
        assert refusals == ["approval_request_already_decided"] * 7, refusals


# --- §4.8 continuation -----------------------------------------------------


class TestContinuation:
    def test_grant_authorizes_the_approved_invocation(self, flow):
        """§4.8 "Continuation Invocation": the grant_id in ``approval_grant``
        lets the approved invocation run."""
        grant = flow.approved_grant()

        data = flow.invoke(flow.parameters(), approval_grant=grant["grant_id"])

        flow.assert_executed(data)

    def test_one_time_grant_is_consumed_by_its_first_use(self, flow):
        """§4.8: "Subsequent invocations with the same grant return
        grant_consumed"."""
        grant = flow.approved_grant()
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))

        again = flow.invoke(flow.parameters(), approval_grant=grant["grant_id"])

        flow.assert_refused(again, "grant_consumed")

    def test_parameter_key_order_is_not_drift(self, flow):
        """§4.7: the digest is over the "canonical JSON" of the parameters,
        so the order in which a client writes the keys does not matter."""
        parameters = flow.parameters()
        grant = flow.approved_grant(parameters)
        reordered = dict(reversed(list(parameters.items())))

        data = flow.invoke(reordered, approval_grant=grant["grant_id"])

        flow.assert_executed(data)

    def test_integral_float_is_not_drift_and_another_integer_is(self, flow, manifest_capabilities):
        """§4.7: "canonical JSON" is RFC 8785 (JCS), which serialises numbers
        as ECMAScript does: ``5`` and ``5.0`` are the same JSON number and
        have the same digest. ``6`` is another number: §4.8 step 6,
        "Mismatch → grant_param_drift"."""
        declared = {
            i["name"]: i.get("type")
            for i in manifest_capabilities[flow.capability].get("inputs", [])
        }
        approved = flow.parameters()
        names = [
            name for name, value in approved.items()
            if declared.get(name) == "integer"
            and isinstance(value, int) and not isinstance(value, bool)
        ]
        if not names:
            pytest.skip("$approval.parameters has no integer value for a declared integer input")
        name = names[0]
        grant = flow.approved_grant(approved)

        other = dict(approved, **{name: approved[name] + 1})
        data = flow.invoke(other, approval_grant=grant["grant_id"])
        flow.assert_refused(data, "grant_param_drift")

        as_float = dict(approved, **{name: float(approved[name])})
        assert f"{approved[name]}.0" in httpx.Request("POST", "http://x", json=as_float).content.decode(), (
            "the client does not write the value with a fraction part"
        )
        data = flow.invoke(as_float, approval_grant=grant["grant_id"])
        flow.assert_executed(data)

    def test_unknown_grant_is_not_found(self, flow):
        """§4.8 step 1: "Missing → grant_not_found"."""
        data = flow.invoke(flow.parameters(), approval_grant=f"grant_{uuid.uuid4().hex[:12]}")

        flow.assert_refused(data, "grant_not_found")

    def test_unknown_grant_is_refused_even_when_no_approval_is_needed(self, flow, sample_inputs):
        """§4.8: validation runs "when invoke() receives a request with
        approval_grant", before the handler."""
        if flow.capability not in sample_inputs:
            pytest.skip(f"no ordinary sample input for {flow.capability}")
        data = flow.invoke(copy.deepcopy(sample_inputs[flow.capability]),
                           approval_grant=f"grant_{uuid.uuid4().hex[:12]}")

        flow.assert_refused(data, "grant_not_found")

    @pytest.mark.parametrize("grant", ["", "   "], ids=["empty", "whitespace"])
    def test_blank_grant_is_not_found(self, flow, grant):
        """§4.8 step 1: ``approval_grant`` is a string (schema: no minimum
        length); no grant has a blank id, so: "Missing → grant_not_found",
        and the invocation that needs approval does not run."""
        data = flow.invoke(flow.parameters(), approval_grant=grant)

        flow.assert_refused(data, "grant_not_found")

    @pytest.mark.parametrize("grant", ["", "   "], ids=["empty", "whitespace"])
    def test_blank_grant_is_refused_even_when_no_approval_is_needed(self, flow, sample_inputs, grant):
        """A supplied grant is validated before the handler, blank or not."""
        if flow.capability not in sample_inputs:
            pytest.skip(f"no ordinary sample input for {flow.capability}")
        data = flow.invoke(copy.deepcopy(sample_inputs[flow.capability]), approval_grant=grant)

        flow.assert_refused(data, "grant_not_found")

    def test_grant_cannot_be_used_for_another_capability(self, flow, read_capability, sample_inputs):
        """§4.8 step 4: "Mismatch → grant_capability_mismatch". Phase A is
        "read-side (no state change)", so the grant is still usable."""
        other, other_scope = read_capability
        if other == flow.capability:
            pytest.skip("needs a second capability")
        token = issue_token(flow.client, flow.scope + other_scope, other,
                            flow.bootstrap_bearer, task_id=None)
        grant = flow.approved_grant()

        data = flow.invoke(copy.deepcopy(sample_inputs.get(other, {})), token=token,
                           capability=other, approval_grant=grant["grant_id"])

        flow.assert_refused(data, "grant_capability_mismatch", token=token)
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))

    def test_grant_cannot_be_used_with_changed_parameters(self, flow):
        """§4.8 step 6: "Mismatch → grant_param_drift"."""
        grant = flow.approved_grant()

        data = flow.invoke(flow.parameters("drifted_parameters"), approval_grant=grant["grant_id"])

        flow.assert_refused(data, "grant_param_drift")
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))

    def test_added_declared_input_is_drift(self, flow, manifest_capabilities):
        """§4.8 step 7: a declared input the approved parameters left out
        changes the digest."""
        approved = flow.parameters()
        free = [
            i for i in manifest_capabilities[flow.capability].get("inputs", [])
            if i["name"] not in approved and i.get("type") == "string"
        ]
        if not free:
            pytest.skip("$approval.parameters leaves out no declared string input")
        grant = flow.approved_grant(approved)

        data = flow.invoke(dict(approved, **{free[0]["name"]: "conformance"}),
                           approval_grant=grant["grant_id"])

        flow.assert_refused(data, "grant_param_drift")

    def test_added_undeclared_parameter_is_refused_before_the_grant(self, flow):
        """§6.3: an undeclared parameter is ``invalid_parameters``, checked
        before the grant is validated or reserved, so the grant stays usable."""
        grant = flow.approved_grant()
        parameters = flow.parameters()
        parameters["conformance_extra"] = "x"

        data = flow.invoke(parameters, approval_grant=grant["grant_id"])

        flow.assert_refused(data, "invalid_parameters")
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))

    def test_token_scope_must_contain_the_grant_scope(self, flow, sample_inputs):
        """§4.8 "Scope Subset Rule": "Any element of grant.scope absent from
        invocation_token.scope → grant_scope_mismatch". A token holding the
        parent scope may invoke the capability, and its scope list does not
        contain the grant's scope."""
        dotted = [s for s in flow.scope if "." in s]
        if not dotted or flow.capability not in sample_inputs:
            pytest.skip("needs a dotted minimum scope and an ordinary sample input")
        parents = [s.rsplit(".", 1)[0] if s in dotted else s for s in flow.scope]
        token = issue_token(flow.client, parents, flow.capability,
                            flow.bootstrap_bearer, task_id=None)
        control = flow.invoke(copy.deepcopy(sample_inputs[flow.capability]), token=token)
        if control.get("success") is not True:
            pytest.skip(f"the service does not let scope {parents} invoke {flow.capability}")
        grant = flow.approved_grant()
        assert not set(grant["scope"]) <= set(parents)

        data = flow.invoke(flow.parameters(), token=token, approval_grant=grant["grant_id"])

        flow.assert_refused(data, "grant_scope_mismatch", token=token)
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))

    def test_expired_grant_is_refused(self, flow):
        """§4.8 step 3: "Expired → grant_expired"."""
        grant = flow.approved_grant(expires_in_seconds=1)
        time.sleep(2.5)

        data = flow.invoke(flow.parameters(), approval_grant=grant["grant_id"])

        flow.assert_refused(data, "grant_expired")

    def test_failed_execution_still_consumes_the_grant(self, flow):
        """§4.8 "Failure handling": "if the handler raises after reservation,
        the grant stays consumed ... The caller MUST request a fresh approval
        to retry." Step 11: the audit entry is written "regardless of handler
        success/failure"."""
        parameters = flow.parameters("handler_failure_parameters")
        grant = flow.approved_grant(parameters)

        failed = flow.invoke(parameters, approval_grant=grant["grant_id"])

        assert failed.get("success") is False, f"Expected the handler to fail: {failed}"
        failure_type = _failure_type(failed)
        assert failure_type != "approval_required" and not failure_type.startswith("grant_"), (
            f"The sample parameters did not reach the handler: {failed['failure']}"
        )
        entry = flow.audit_entry(failed["invocation_id"])
        assert entry.get("approval_grant_id") == grant["grant_id"], (
            f"The failed continuation's audit entry does not reference the grant: {entry}"
        )

        retry = flow.invoke(parameters, approval_grant=grant["grant_id"])

        flow.assert_refused(retry, "grant_consumed")

    def test_concurrent_use_executes_once(self, flow, base_url):
        """§4.8: "Two concurrent requests with the same grant MUST NOT both
        pass validation."
        """
        grant = flow.approved_grant()
        body = {"parameters": flow.parameters(), "approval_grant": grant["grant_id"]}

        def use(_):
            with httpx.Client(base_url=base_url, timeout=30) as own:
                return own.post(f"/anip/invoke/{flow.capability}", json=body,
                                headers={"Authorization": f"Bearer {flow.requester}"}).json()

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(use, range(8)))

        executed = [r for r in results if r.get("success") is True]
        refusals = [_failure_type(r) for r in results if r.get("success") is not True]
        assert len(executed) == 1, f"A one_time grant executed {len(executed)} times"
        assert refusals == ["grant_consumed"] * 7, refusals

    def test_grant_refusals_are_complete_failure_objects(self, flow):
        """§4.5: "The Resolution object MUST include a recovery_class field"
        and "Services MUST use the mapping below"; §8.2: failure objects
        include ``resolution``."""
        grant = flow.approved_grant()
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))
        refusals = {
            "grant_not_found": flow.invoke(
                flow.parameters(), approval_grant=f"grant_{uuid.uuid4().hex[:12]}"),
            "grant_consumed": flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]),
        }

        for expected, data in refusals.items():
            assert _failure_type(data) == expected, data
            _assert_complete_failure(data["failure"])


# --- §4.8 the grant binds its requester ------------------------------------


class TestRequesterBinding:
    """§4.8: a grant "binds the approved action to specific parameters,
    scope, capability, requester, ...". Phase A compares the root principal
    of the invoking token with the root principal recorded in the grant's
    ``requester``: "Mismatch → grant_requester_mismatch", before the grant
    is reserved."""

    def test_grant_is_refused_for_another_principal(self, flow, other_bootstrap_bearer):
        grant = flow.approved_grant()
        other = issue_token(flow.client, flow.scope, flow.capability,
                            other_bootstrap_bearer, task_id=None)

        resp = flow.client.post(
            f"/anip/invoke/{flow.capability}",
            headers={"Authorization": f"Bearer {other}"},
            json={"parameters": flow.parameters(), "approval_grant": grant["grant_id"]},
        )
        data = _json(resp)

        assert isinstance(data, dict), f"Invoke answered {resp.status_code}: {resp.text[:200]!r}"
        flow.assert_refused(data, "grant_requester_mismatch", token=other)
        assert resp.status_code == 403, (
            f"grant_requester_mismatch is HTTP 403 (§6.3 HTTP Status Codes), got {resp.status_code}"
        )
        # Phase A changes no state: the grant still works for its requester.
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))

    def test_requester_check_precedes_the_scope_check(self, flow, other_bootstrap_bearer, sample_inputs):
        """§4.8 Phase A: the requester is compared after the capability and
        before the scope, so another principal whose token also lacks the
        grant's scope learns only that the grant is not its own."""
        dotted = [s for s in flow.scope if "." in s]
        if not dotted or flow.capability not in sample_inputs:
            pytest.skip("needs a dotted minimum scope and an ordinary sample input")
        parents = [s.rsplit(".", 1)[0] if s in dotted else s for s in flow.scope]
        other = issue_token(flow.client, parents, flow.capability,
                            other_bootstrap_bearer, task_id=None)
        control = flow.invoke(copy.deepcopy(sample_inputs[flow.capability]), token=other)
        if control.get("success") is not True:
            pytest.skip(f"the service does not let scope {parents} invoke {flow.capability}")
        grant = flow.approved_grant()

        data = flow.invoke(flow.parameters(), token=other, approval_grant=grant["grant_id"])

        flow.assert_refused(data, "grant_requester_mismatch", token=other)
        flow.assert_executed(flow.invoke(flow.parameters(), approval_grant=grant["grant_id"]))

    def test_another_token_of_the_same_principal_may_use_the_grant(self, flow):
        """Tokens of the requester's root principal, including one delegated
        from a fresh root token, may redeem the grant."""
        grant = flow.approved_grant()
        parent = _token(flow.client, flow.bootstrap_bearer, flow.scope, flow.capability)
        child = _token(flow.client, flow.bootstrap_bearer, flow.scope, flow.capability,
                       parent_token=parent["token_id"])["token"]

        data = flow.invoke(flow.parameters(), token=child, approval_grant=grant["grant_id"])

        flow.assert_executed(data, token=child)


# --- §4.8 session_bound grants ---------------------------------------------


class TestSessionBoundGrants:
    """§4.8: a session_bound grant is "reusable within a declared session up
    to max_uses. The continuation invocation's token MUST belong to the
    session indicated by session_id. Outside the session, returns
    grant_session_invalid". The token request schema binds a session to a
    token with ``session_id`` at root issuance."""

    def _session_token(self, flow, session_id: str) -> str:
        return _token(flow.client, flow.bootstrap_bearer, flow.scope, flow.capability,
                      session_id=session_id)["token"]

    def _session_grant(self, flow, session_id: str, **extra) -> dict:
        grant = flow.approved_grant(grant_type="session_bound", session_id=session_id, **extra)
        assert grant["grant_type"] == "session_bound"
        assert grant["session_id"] == session_id
        return grant

    def test_session_bound_grant_is_reusable_up_to_max_uses(self, session_bound):
        flow = session_bound
        session_id = f"conformance-{uuid.uuid4().hex[:8]}"
        token = self._session_token(flow, session_id)
        uses = flow.policy["max_uses"]
        grant = self._session_grant(flow, session_id, max_uses=uses)
        assert grant["max_uses"] == uses

        for _ in range(uses):
            data = flow.invoke(flow.parameters(), token=token, approval_grant=grant["grant_id"])
            flow.assert_executed(data, token=token)

        over = flow.invoke(flow.parameters(), token=token, approval_grant=grant["grant_id"])
        flow.assert_refused(over, "grant_consumed", token=token)

    @pytest.mark.parametrize("outside", ["no_session", "another_session"])
    def test_session_bound_grant_is_refused_outside_its_session(self, session_bound, outside):
        flow = session_bound
        session_id = f"conformance-{uuid.uuid4().hex[:8]}"
        grant = self._session_grant(flow, session_id)
        token = (flow.requester if outside == "no_session"
                 else self._session_token(flow, f"conformance-{uuid.uuid4().hex[:8]}"))

        data = flow.invoke(flow.parameters(), token=token, approval_grant=grant["grant_id"])

        flow.assert_refused(data, "grant_session_invalid", token=token)
        # Phase A changes no state: the grant still works inside its session.
        inside = self._session_token(flow, session_id)
        flow.assert_executed(
            flow.invoke(flow.parameters(), token=inside, approval_grant=grant["grant_id"]),
            token=inside)

    def test_session_is_read_from_the_token_not_the_request_body(self, session_bound):
        """§4.8 step 7: "verify session_id from invocation token"."""
        flow = session_bound
        session_id = f"conformance-{uuid.uuid4().hex[:8]}"
        grant = self._session_grant(flow, session_id)

        data = flow.invoke(flow.parameters(), approval_grant=grant["grant_id"],
                           session_id=session_id)

        flow.assert_refused(data, "grant_session_invalid")

    def test_delegated_token_stays_in_its_parents_session(self, session_bound):
        """Token request schema: session_id is "only honored at root
        issuance — child tokens inherit parent.session_id verbatim"."""
        flow = session_bound
        parent_session = f"conformance-{uuid.uuid4().hex[:8]}"
        other_session = f"conformance-{uuid.uuid4().hex[:8]}"
        parent = _token(flow.client, flow.bootstrap_bearer, flow.scope, flow.capability,
                        session_id=parent_session)
        child = _token(flow.client, flow.bootstrap_bearer, flow.scope, flow.capability,
                       parent_token=parent["token_id"], session_id=other_session)["token"]
        other_grant = self._session_grant(flow, other_session)
        parent_grant = self._session_grant(flow, parent_session)

        refused = flow.invoke(flow.parameters(), token=child,
                              approval_grant=other_grant["grant_id"])
        flow.assert_refused(refused, "grant_session_invalid", token=child)

        allowed = flow.invoke(flow.parameters(), token=child,
                              approval_grant=parent_grant["grant_id"])
        flow.assert_executed(allowed, token=child)


# --- §4.9 audit linkage ----------------------------------------------------


class TestAuditLinkage:
    def test_audit_links_invocation_request_grant_and_continuation(self, flow):
        """§4.9 "Audit Linkage Requirements": "Every approval flow MUST be
        reconstructible from audit entries", along
        parent_invocation_id → approval_request_id → grant_id →
        continuation_invocation_id."""
        since = (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        first = flow.invoke(flow.parameters())
        request_id = first["failure"]["approval_required"]["approval_request_id"]
        grant = flow.issue_grant(request_id)
        continuation = flow.invoke(flow.parameters(), approval_grant=grant["grant_id"])
        flow.assert_executed(continuation)

        # "The approval_request_created event provides the invocation → request link."
        created = [
            e for e in flow.audit(f"parent_invocation_id={first['invocation_id']}")
            if e.get("approval_request_id") == request_id
        ]
        assert len(created) == 1, (
            f"Expected one audit entry linking invocation {first['invocation_id']} to "
            f"request {request_id}, got {len(created)}"
        )
        assert created[0]["capability"] == flow.capability

        # "The approval_grant_issued event provides the request → grant link."
        recent = flow.audit(f"capability={flow.capability}&since={since}&limit=1000",
                            token=flow.approver)
        issued = [
            e for e in recent
            if e.get("approval_request_id") == request_id
            and e.get("approval_grant_id") == grant["grant_id"]
        ]
        assert len(issued) == 1, (
            f"Expected one audit entry linking request {request_id} to grant "
            f"{grant['grant_id']}, got {len(issued)}"
        )

        # "The continuation invocation's audit entry references the grant."
        entry = flow.audit_entry(continuation["invocation_id"])
        assert entry.get("approval_grant_id") == grant["grant_id"], entry
        assert entry["success"] is True

"""Conformance tests for validation of invocation parameters against the
capability's declared inputs.

Spec references: §4.1 (capability declaration: ``inputs``, and ``required``
defaults to ``true``), §6.3 "Parameter Validation" (when the check runs, what
it checks, the ``invalid_parameters`` failure and its HTTP status) and §4.5
(failure semantics).

The tests read the declared inputs from the manifest and need an ordinary
sample invocation for the capability in ``--sample-inputs``. A capability is
usable when it has a sample invocation that succeeds; a test skips with the
reason when the service declares nothing it can use.

A refusal is checked four ways: the failure type, no ``result`` in the
response, HTTP 400, and the audit entry of that invocation recording a
failure. A handler that ran is visible to the protocol as ``success: true``,
as a handler-raised failure such as ``approval_required``, or as an audit
entry recording success; the tests look for all three.
"""
from __future__ import annotations

import copy

import pytest

from conftest import assert_complete_failure, issue_token

PRIMITIVE_TYPES = ("string", "integer", "number", "boolean", "array", "object")

# One value of every JSON type, keyed by the name §6.3 uses for it in a detail.
JSON_VALUES = {
    "string": "conformance",
    "number": 1.5,
    "boolean": True,
    "array": ["conformance"],
    "object": {"conformance": True},
}

# JSON types that a declared primitive type does not accept (§6.3).
WRONG_JSON_TYPES = {
    "string": ("number", "boolean", "array", "object"),
    "integer": ("string", "number", "boolean", "array", "object"),
    "number": ("string", "boolean", "array", "object"),
    "boolean": ("string", "number", "array", "object"),
    "array": ("string", "number", "boolean", "object"),
    "object": ("string", "number", "boolean", "array"),
}


def _failure_type(body) -> str | None:
    failure = body.get("failure") if isinstance(body, dict) else None
    return failure.get("type") if isinstance(failure, dict) else None


def _is_required(declared_input: dict) -> bool:
    """§4.1: ``required`` defaults to ``true`` when a declaration omits it."""
    return declared_input.get("required", True) is not False


class Target:
    """One capability with a sample invocation, and the calls made on it."""

    def __init__(self, client, bootstrap_bearer, name, declaration, sample):
        self.client = client
        self.name = name
        self.declaration = declaration
        self.sample = sample
        self.inputs = {i["name"]: i for i in declaration.get("inputs", [])}
        self.binding_fields = {b["field"] for b in declaration.get("requires_binding") or []}
        self.token = issue_token(
            client, list(declaration.get("minimum_scope", [])), name, bootstrap_bearer,
            task_id=None)

    def parameters(self) -> dict:
        return copy.deepcopy(self.sample)

    def invoke(self, parameters):
        resp = self.client.post(
            f"/anip/invoke/{self.name}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"parameters": parameters},
        )
        try:
            data = resp.json()
        except ValueError:
            data = None
        assert isinstance(data, dict), (
            f"Invoke answered {resp.status_code} without a JSON object: {resp.text[:200]!r}"
        )
        return resp.status_code, data

    def audit_entry(self, invocation_id: str) -> dict:
        resp = self.client.post(
            f"/anip/audit?invocation_id={invocation_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200, f"Audit query failed: {resp.status_code} {resp.text[:200]}"
        entries = [e for e in resp.json()["entries"] if e.get("invocation_id") == invocation_id]
        assert len(entries) == 1, (
            f"Expected one audit entry for {invocation_id}, got {len(entries)}"
        )
        return entries[0]

    # Inputs the tests can vary one at a time. A field named in
    # requires_binding is refused as binding_missing when absent (§6.3 puts
    # binding enforcement before parameter validation), so it is left out of
    # the "absent" cases and kept for the type cases.
    def required_inputs(self) -> list[str]:
        return [
            n for n, i in self.inputs.items()
            if _is_required(i) and n in self.sample and n not in self.binding_fields
        ]

    def optional_inputs(self) -> list[str]:
        return [
            n for n, i in self.inputs.items()
            if not _is_required(i) and n in self.sample and n not in self.binding_fields
        ]

    def primitive_inputs(self) -> list[tuple[str, str]]:
        return [
            (n, i["type"]) for n, i in self.inputs.items()
            if i.get("type") in PRIMITIVE_TYPES and n in self.sample
        ]


def _assert_refused(target: Target, status: int, data: dict, context: str) -> dict:
    """The call was refused as invalid_parameters and the handler did not run."""
    assert data.get("success") is False, (
        f"{context}: expected a refusal, got {status} {data}"
    )
    assert _failure_type(data) == "invalid_parameters", (
        f"{context}: expected failure type 'invalid_parameters', got {status} {data.get('failure')}"
    )
    assert data.get("result") is None, f"{context}: a refused invocation returned a result: {data}"
    assert_complete_failure(data["failure"])
    assert data["failure"].get("retry") is False, (
        f"{context}: the same request cannot succeed, so retry is false: {data['failure']}"
    )
    assert status == 400, f"{context}: invalid_parameters is HTTP 400 (§6.3), got {status}"
    assert isinstance(data.get("invocation_id"), str), f"{context}: no invocation_id: {data}"
    entry = target.audit_entry(data["invocation_id"])
    assert entry["success"] is False, (
        f"{context}: the audit log records the refused invocation as executed: {entry}"
    )
    assert entry.get("failure_type") == "invalid_parameters", (
        f"{context}: the audit entry does not record the failure type: {entry}"
    )
    return data["failure"]


def _assert_executed(target: Target, status: int, data: dict, context: str) -> None:
    assert status == 200 and data.get("success") is True, (
        f"{context}: expected the invocation to succeed, got {status} {data}"
    )
    assert isinstance(data.get("result"), dict), f"{context}: no result on success: {data}"
    entry = target.audit_entry(data["invocation_id"])
    assert entry["success"] is True, f"{context}: the audit log records a failure: {entry}"


@pytest.fixture(scope="module")
def targets(client, bootstrap_bearer, manifest_capabilities, sample_inputs) -> list[Target]:
    """Capabilities with declared inputs and an ordinary sample invocation."""
    found = [
        Target(client, bootstrap_bearer, name, declaration, sample_inputs[name])
        for name, declaration in manifest_capabilities.items()
        if declaration.get("inputs") and isinstance(sample_inputs.get(name), dict)
    ]
    if not found:
        pytest.skip("no capability has both declared inputs and an entry in --sample-inputs")
    return found


def _cases(targets, select, what: str) -> list[tuple[Target, object]]:
    cases = [(t, item) for t in targets for item in select(t)]
    if not cases:
        names = ", ".join(t.name for t in targets)
        pytest.skip(f"no capability with a sample invocation declares {what} (looked at: {names})")
    return cases


# --- control ---------------------------------------------------------------


class TestValidCalls:
    def test_sample_invocation_succeeds(self, targets):
        """Control: every refusal below differs from this call in one input."""
        for target in targets:
            status, data = target.invoke(target.parameters())
            _assert_executed(target, status, data, f"{target.name} with its sample input")

    def test_optional_input_may_be_omitted(self, targets):
        """§4.1: an input with ``required: false`` may be left out."""
        for target, name in _cases(targets, Target.optional_inputs,
                                   "an optional input that the sample supplies"):
            parameters = target.parameters()
            del parameters[name]

            status, data = target.invoke(parameters)

            _assert_executed(target, status, data, f"{target.name} without optional '{name}'")

    def test_integral_number_is_an_integer(self, targets):
        """§6.3: ``integer`` accepts any JSON number with an integral value,
        so ``1.0`` is the integer ``1``."""
        for target, (name, _) in _cases(
            targets,
            lambda t: [(n, ty) for n, ty in t.primitive_inputs()
                       if ty == "integer" and isinstance(t.sample[n], int)
                       and not isinstance(t.sample[n], bool)],
            "an integer input that the sample supplies",
        ):
            parameters = target.parameters()
            parameters[name] = float(parameters[name])

            status, data = target.invoke(parameters)

            _assert_executed(target, status, data,
                             f"{target.name} with {name}={parameters[name]!r}")


# --- required inputs -------------------------------------------------------


class TestRequiredInputs:
    def test_missing_required_input_is_refused(self, targets):
        """§6.3: a declared input with ``required: true`` that is absent →
        ``invalid_parameters``; the detail names the input."""
        for target, name in _cases(targets, Target.required_inputs, "a required input"):
            parameters = target.parameters()
            del parameters[name]

            status, data = target.invoke(parameters)

            failure = _assert_refused(target, status, data, f"{target.name} without '{name}'")
            assert name in failure["detail"], (
                f"The detail does not name the missing input '{name}': {failure['detail']!r}"
            )

    def test_null_for_required_input_is_refused(self, targets):
        """§6.3: JSON ``null`` for a required input is the same as leaving it out."""
        for target, name in _cases(targets, Target.required_inputs, "a required input"):
            parameters = target.parameters()
            parameters[name] = None

            status, data = target.invoke(parameters)

            failure = _assert_refused(target, status, data, f"{target.name} with {name}=null")
            assert name in failure["detail"], (
                f"The detail does not name the null input '{name}': {failure['detail']!r}"
            )

    def test_detail_names_every_missing_input(self, targets):
        """§6.3: "The detail names every missing input"."""
        usable = [t for t in targets if len(t.required_inputs()) >= 2]
        if not usable:
            pytest.skip("no capability with a sample invocation declares two required inputs")
        for target in usable:
            missing = target.required_inputs()
            parameters = {k: v for k, v in target.parameters().items() if k not in missing}

            status, data = target.invoke(parameters)

            failure = _assert_refused(target, status, data,
                                      f"{target.name} without {missing}")
            absent = [name for name in missing if name not in failure["detail"]]
            assert not absent, (
                f"The detail leaves out missing inputs {absent}: {failure['detail']!r}"
            )

    def test_empty_parameters_are_refused(self, targets):
        """No parameters at all is the plainest case of a missing required input."""
        usable = [t for t in targets
                  if any(_is_required(i) and n not in t.binding_fields
                         for n, i in t.inputs.items())
                  and not t.binding_fields]
        if not usable:
            pytest.skip("no capability without requires_binding declares a required input")
        for target in usable:
            status, data = target.invoke({})

            _assert_refused(target, status, data, f"{target.name} with no parameters")


    @pytest.mark.parametrize("received", ["array", "string", "number", "boolean"])
    def test_parameters_must_be_an_object(self, targets, received):
        """§6.3: a ``parameters`` value that is not an object (or null) does
        not match the request schema: ``invalid_parameters``, HTTP 400. The
        refusal may be made by the binding, like a body that is not JSON, so
        the audit log is not consulted here."""
        target = targets[0]
        resp = target.client.post(
            f"/anip/invoke/{target.name}",
            headers={"Authorization": f"Bearer {target.token}"},
            json={"parameters": JSON_VALUES[received]},
        )
        data = resp.json()
        assert data.get("success") is False and _failure_type(data) == "invalid_parameters", (
            f"parameters={JSON_VALUES[received]!r}: expected invalid_parameters, "
            f"got {resp.status_code} {data}"
        )
        assert data.get("result") is None
        assert_complete_failure(data["failure"])
        assert data["failure"].get("retry") is False, f"retry is not false: {data['failure']}"
        assert resp.status_code == 400, f"invalid_parameters is HTTP 400, got {resp.status_code}"
        detail = data["failure"]["detail"]
        assert "parameters must be an object" in detail and received in detail, (
            f"The detail does not say that parameters must be an object, got {received}: {detail!r}"
        )

    def test_null_parameters_are_the_empty_object(self, targets):
        """§6.3: ``parameters: null`` is the empty object, so what is wrong
        with it is the missing required inputs."""
        usable = [t for t in targets if t.required_inputs() and not t.binding_fields]
        if not usable:
            pytest.skip("no capability without requires_binding declares a required input")
        target = usable[0]

        status, data = target.invoke(None)

        failure = _assert_refused(target, status, data, f"{target.name} with parameters=null")
        absent = [n for n in target.required_inputs() if n not in failure["detail"]]
        assert not absent, f"The detail leaves out missing inputs {absent}: {failure['detail']!r}"


    def test_required_input_with_on_missing_is_left_to_the_service(self, targets):
        """§6.3 (exception) and §4.10: a required input whose declaration
        sets ``resolution.on_missing`` is answered through that path; the
        runtime does not refuse its absence as a missing required input."""
        cases = _cases(
            targets,
            lambda t: [n for n, i in t.inputs.items()
                       if _is_required(i) and (i.get("resolution") or {}).get("on_missing")
                       and n in t.sample and n not in t.binding_fields],
            "a required input with resolution.on_missing that the sample supplies",
        )
        for target, name in cases:
            parameters = target.parameters()
            del parameters[name]

            _, data = target.invoke(parameters)

            detail = str((data.get("failure") or {}).get("detail", ""))
            assert not (_failure_type(data) == "invalid_parameters"
                        and "missing required input" in detail and name in detail), (
                f"The runtime refused the absent '{name}' although it declares "
                f"on_missing={target.inputs[name]['resolution']['on_missing']}: {data.get('failure')}"
            )


# --- primitive types -------------------------------------------------------


class TestPrimitiveTypes:
    @pytest.mark.parametrize("declared", PRIMITIVE_TYPES)
    def test_value_of_another_json_type_is_refused(self, targets, declared):
        """§6.3: for a declared primitive type, "a supplied value of another
        JSON type → invalid_parameters, naming the input, the expected type
        and what was received"."""
        for target, (name, _) in _cases(
            targets,
            lambda t: [(n, ty) for n, ty in t.primitive_inputs() if ty == declared],
            f"an input of type '{declared}'",
        ):
            for received in WRONG_JSON_TYPES[declared]:
                parameters = target.parameters()
                parameters[name] = JSON_VALUES[received]
                context = f"{target.name} with {name}={JSON_VALUES[received]!r} (declared {declared})"

                status, data = target.invoke(parameters)

                failure = _assert_refused(target, status, data, context)
                for expected in (name, declared, received):
                    assert expected in failure["detail"], (
                        f"{context}: the detail does not mention '{expected}': {failure['detail']!r}"
                    )

    def test_boolean_is_not_an_integer(self, targets):
        """§6.3: ``integer`` "rejects booleans" (in several languages a
        boolean is a number unless the check says otherwise)."""
        for target, (name, _) in _cases(
            targets,
            lambda t: [(n, ty) for n, ty in t.primitive_inputs() if ty == "integer"],
            "an input of type 'integer'",
        ):
            for value in (True, False):
                parameters = target.parameters()
                parameters[name] = value

                status, data = target.invoke(parameters)

                failure = _assert_refused(target, status, data,
                                          f"{target.name} with {name}={value!r}")
                assert "boolean" in failure["detail"], (
                    f"The detail does not say a boolean was received: {failure['detail']!r}"
                )

    def test_fractional_number_is_not_an_integer(self, targets):
        for target, (name, _) in _cases(
            targets,
            lambda t: [(n, ty) for n, ty in t.primitive_inputs() if ty == "integer"],
            "an input of type 'integer'",
        ):
            parameters = target.parameters()
            parameters[name] = 1.5

            status, data = target.invoke(parameters)

            _assert_refused(target, status, data, f"{target.name} with {name}=1.5")

    def test_domain_types_are_not_type_checked(self, targets):
        """§6.3: a declared type that is not one of the six primitive names
        (``airport_code``, ``date``, ...) is not type-checked by the runtime.
        A boolean is offered; a refusal whose detail reports that a boolean
        was received is a type check. What the handler makes of the value is
        the handler's business."""
        cases = _cases(
            targets,
            lambda t: [n for n, i in t.inputs.items()
                       if i.get("type") not in PRIMITIVE_TYPES and n in t.sample
                       and n not in t.binding_fields],
            "an input with a domain type",
        )
        for target, name in cases:
            parameters = target.parameters()
            parameters[name] = True

            _, data = target.invoke(parameters)

            detail = str((data.get("failure") or {}).get("detail", ""))
            assert "boolean" not in detail, (
                f"The runtime type-checked '{name}' of domain type "
                f"'{target.inputs[name]['type']}': {data.get('failure')}"
            )


# --- the refused call has no effect ----------------------------------------


class TestRefusalHasNoEffect:
    def test_invalid_call_does_not_reach_a_handler_that_asks_for_approval(
        self, client, bootstrap_bearer, manifest_capabilities, sample_inputs
    ):
        """§6.3: validation runs before the handler. The ``$approval`` sample
        makes the handler answer ``approval_required`` (and the runtime
        persist an ApprovalRequest); with one more input of the wrong type
        the answer is ``invalid_parameters`` instead."""
        sample = sample_inputs.get("$approval")
        if not sample or sample.get("capability") not in manifest_capabilities:
            pytest.skip("--sample-inputs has no usable '$approval' entry")
        target = Target(client, bootstrap_bearer, sample["capability"],
                        manifest_capabilities[sample["capability"]], sample["parameters"])
        candidates = [(n, ty) for n, ty in target.primitive_inputs() if ty == "string"]
        if not candidates:
            pytest.skip(f"{target.name} declares no string input that the $approval sample supplies")
        name, _ = candidates[0]

        status, data = target.invoke(target.parameters())
        assert _failure_type(data) == "approval_required", (
            f"Control: expected the $approval sample to need approval, got {status} {data}"
        )

        parameters = target.parameters()
        parameters[name] = 12345
        status, data = target.invoke(parameters)

        _assert_refused(target, status, data, f"{target.name} with {name}=12345")
        assert "approval_required" not in data["failure"], (
            f"A refused call carries approval metadata: {data['failure']}"
        )

    def test_invalid_continuation_does_not_spend_the_grant(
        self, client, bootstrap_bearer, discovery, manifest_capabilities, sample_inputs
    ):
        """§6.3: validation runs "before approval-grant reservation". A
        continuation with an invalid parameter is refused as
        ``invalid_parameters`` and the one-time grant is still usable."""
        sample = sample_inputs.get("$approval")
        if not sample or sample.get("capability") not in manifest_capabilities:
            pytest.skip("--sample-inputs has no usable '$approval' entry")
        declaration = manifest_capabilities[sample["capability"]]
        grants_path = discovery.get("endpoints", {}).get("approval_grants")
        if not declaration.get("grant_policy") or not grants_path:
            pytest.skip("the service does not offer approval grants for the $approval capability")
        target = Target(client, bootstrap_bearer, sample["capability"], declaration,
                        sample["parameters"])
        candidates = [(n, ty) for n, ty in target.primitive_inputs() if ty == "string"]
        if not candidates:
            pytest.skip(f"{target.name} declares no string input that the $approval sample supplies")
        name, _ = candidates[0]
        approver = issue_token(client, [f"approver:{target.name}"], target.name,
                               bootstrap_bearer, task_id=None)

        _, data = target.invoke(target.parameters())
        assert _failure_type(data) == "approval_required", f"Expected approval_required, got {data}"
        request_id = data["failure"]["approval_required"]["approval_request_id"]
        resp = client.post(
            grants_path, headers={"Authorization": f"Bearer {approver}"},
            json={"approval_request_id": request_id, "grant_type": "one_time"})
        assert resp.status_code == 200, f"Grant issuance failed: {resp.status_code} {resp.text[:300]}"
        grant_id = resp.json()["grant_id"]

        def continue_with(parameters):
            r = client.post(
                f"/anip/invoke/{target.name}",
                headers={"Authorization": f"Bearer {target.token}"},
                json={"parameters": parameters, "approval_grant": grant_id},
            )
            return r.status_code, r.json()

        parameters = target.parameters()
        parameters[name] = 12345
        status, data = continue_with(parameters)
        _assert_refused(target, status, data,
                        f"continuation of {target.name} with {name}=12345")

        status, data = continue_with(target.parameters())
        _assert_executed(target, status, data,
                         f"continuation of {target.name} after the refused attempt")

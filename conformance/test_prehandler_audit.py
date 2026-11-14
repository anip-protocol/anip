"""Conformance tests: every refusal made before the handler is audited.

Spec references: §6.3 (budget, binding and control-requirement enforcement
run before the handler; "Parameter Validation": a refused invocation "is
recorded in the audit log as a failure ... like other refusals made before
the handler"), §5.4 and §6.8 (the audit log records failed invocations) and
§6.3 "Audit Log" (``invocation_id`` filter).

Each test provokes one refusal on a capability whose manifest declaration
makes it possible (estimated cost bound by ``requires_binding``, a fixed
financial cost, ``max_age``), using the capability's ``--sample-inputs``
entry, and checks three things: the failure type, no ``result``, and one
audit entry for that invocation recording a failure with the same
``failure_type``. A test skips with the reason when the service declares
nothing that can provoke the refusal.
"""
from __future__ import annotations

import copy
import time

import pytest

from conftest import assert_complete_failure, issue_token


def _failure_type(body) -> str | None:
    failure = body.get("failure") if isinstance(body, dict) else None
    return failure.get("type") if isinstance(failure, dict) else None


def _bound_capability(manifest_capabilities, sample_inputs, *, needs=None):
    """(name, declaration, sample, binding) for a capability with a binding
    requirement and a sample invocation that carries the bound field."""
    for name, declaration in manifest_capabilities.items():
        sample = sample_inputs.get(name)
        if not isinstance(sample, dict):
            continue
        for binding in declaration.get("requires_binding") or []:
            if binding["field"] in sample and (needs is None or needs(declaration, binding, sample)):
                return name, declaration, sample, binding
    return None


def _estimated_cost(declaration, binding, sample=None) -> bool:
    cost = declaration.get("cost") or {}
    return cost.get("certainty") == "estimated" and bool((cost.get("financial") or {}).get("currency"))


def _invoke(client, token, name, parameters):
    resp = client.post(
        f"/anip/invoke/{name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    data = resp.json()
    assert isinstance(data, dict), f"Invoke answered {resp.status_code}: {resp.text[:200]!r}"
    return data


def _assert_refused_and_audited(client, token, data, failure_type):
    assert data.get("success") is False, f"Expected a refusal, got {data}"
    assert _failure_type(data) == failure_type, (
        f"Expected failure type '{failure_type}', got {data.get('failure')}"
    )
    assert data.get("result") is None, f"A refused invocation returned a result: {data}"
    assert_complete_failure(data["failure"])
    invocation_id = data.get("invocation_id")
    assert isinstance(invocation_id, str), f"No invocation_id: {data}"
    resp = client.post(
        f"/anip/audit?invocation_id={invocation_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Audit query failed: {resp.status_code} {resp.text[:200]}"
    entries = [e for e in resp.json()["entries"] if e.get("invocation_id") == invocation_id]
    assert len(entries) == 1, (
        f"The '{failure_type}' refusal of {invocation_id} is not in the audit log "
        f"(found {len(entries)} entries)"
    )
    entry = entries[0]
    assert entry["success"] is False, f"The audit log records the refusal as executed: {entry}"
    assert entry.get("failure_type") == failure_type, (
        f"The audit entry does not record failure_type '{failure_type}': {entry}"
    )


class TestBudgetRefusalsAreAudited:
    def test_budget_exceeded(self, client, bootstrap_bearer, manifest_capabilities, sample_inputs):
        found = _bound_capability(
            manifest_capabilities, sample_inputs,
            needs=lambda d, b, s: _estimated_cost(d, b) and isinstance(s[b["field"]], dict)
            and isinstance(s[b["field"]].get("price"), (int, float)),
        )
        if found is None:
            pytest.skip("no capability has an estimated cost bound by a priced binding in --sample-inputs")
        name, declaration, sample, binding = found
        price = sample[binding["field"]]["price"]
        currency = declaration["cost"]["financial"]["currency"]
        token = issue_token(client, declaration.get("minimum_scope", []), name, bootstrap_bearer,
                            task_id=None, budget={"currency": currency, "max_amount": price / 2})

        data = _invoke(client, token, name, copy.deepcopy(sample))

        _assert_refused_and_audited(client, token, data, "budget_exceeded")

    def test_budget_currency_mismatch(self, client, bootstrap_bearer, manifest_capabilities, sample_inputs):
        found = _bound_capability(manifest_capabilities, sample_inputs, needs=_estimated_cost)
        if found is None:
            pytest.skip("no capability has a financial cost and a binding in --sample-inputs")
        name, declaration, sample, _ = found
        currency = declaration["cost"]["financial"]["currency"]
        other = "EUR" if currency != "EUR" else "USD"
        token = issue_token(client, declaration.get("minimum_scope", []), name, bootstrap_bearer,
                            task_id=None, budget={"currency": other, "max_amount": 100000})

        data = _invoke(client, token, name, copy.deepcopy(sample))

        _assert_refused_and_audited(client, token, data, "budget_currency_mismatch")

    def test_budget_not_enforceable(self, client, bootstrap_bearer, manifest_capabilities, sample_inputs):
        """§6.3 "Budget Enforcement": an estimated cost whose binding carries
        no price cannot be checked against the budget."""
        found = _bound_capability(
            manifest_capabilities, sample_inputs,
            needs=lambda d, b, s: _estimated_cost(d, b) and isinstance(s[b["field"]], dict),
        )
        if found is None:
            pytest.skip("no capability has an estimated cost bound by an object binding in --sample-inputs")
        name, declaration, sample, binding = found
        currency = declaration["cost"]["financial"]["currency"]
        token = issue_token(client, declaration.get("minimum_scope", []), name, bootstrap_bearer,
                            task_id=None, budget={"currency": currency, "max_amount": 100000})
        parameters = copy.deepcopy(sample)
        parameters[binding["field"]].pop("price", None)

        data = _invoke(client, token, name, parameters)

        _assert_refused_and_audited(client, token, data, "budget_not_enforceable")


class TestBindingRefusalsAreAudited:
    def test_binding_missing(self, client, bootstrap_bearer, manifest_capabilities, sample_inputs):
        found = _bound_capability(manifest_capabilities, sample_inputs)
        if found is None:
            pytest.skip("no capability has a binding requirement and a sample invocation carrying it")
        name, declaration, sample, binding = found
        token = issue_token(client, declaration.get("minimum_scope", []), name, bootstrap_bearer,
                            task_id=None)
        parameters = copy.deepcopy(sample)
        del parameters[binding["field"]]

        data = _invoke(client, token, name, parameters)

        _assert_refused_and_audited(client, token, data, "binding_missing")

    def test_binding_stale(self, client, bootstrap_bearer, manifest_capabilities, sample_inputs):
        found = _bound_capability(
            manifest_capabilities, sample_inputs,
            needs=lambda d, b, s: bool(b.get("max_age")) and isinstance(s[b["field"]], dict)
            and "issued_at" in s[b["field"]],
        )
        if found is None:
            pytest.skip("no capability has a binding with max_age and a sample carrying issued_at")
        name, declaration, sample, binding = found
        token = issue_token(client, declaration.get("minimum_scope", []), name, bootstrap_bearer,
                            task_id=None)
        parameters = copy.deepcopy(sample)
        # Older than any max_age a service would declare for a quote.
        parameters[binding["field"]]["issued_at"] = int(time.time()) - 30 * 24 * 3600

        data = _invoke(client, token, name, parameters)

        _assert_refused_and_audited(client, token, data, "binding_stale")


class TestControlRequirementRefusalsAreAudited:
    def test_cost_ceiling_without_budget(self, client, bootstrap_bearer, cost_ceiling_capability,
                                         sample_inputs):
        if cost_ceiling_capability is None:
            pytest.skip("no capability declares the cost_ceiling control requirement")
        name, scope = cost_ceiling_capability
        if not isinstance(sample_inputs.get(name), dict):
            pytest.skip(f"no sample invocation for {name}")
        token = issue_token(client, scope, name, bootstrap_bearer, task_id=None)

        data = _invoke(client, token, name, copy.deepcopy(sample_inputs[name]))

        _assert_refused_and_audited(client, token, data, "control_requirement_unsatisfied")

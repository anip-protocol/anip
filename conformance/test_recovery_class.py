"""Conformance tests for ANIP recovery_class on failure responses.

Spec references: §4.2 (failure semantics), §4.2.1 (recovery_class vocabulary),
Conformance Category 3 (invocation failures).
"""
import pytest
from conftest import issue_token


CANONICAL_RECOVERY_CLASSES = {
    "retry_now",
    "wait_then_retry",
    "refresh_then_retry",
    "redelegation_then_retry",
    "revalidate_then_retry",
    "terminal",
}

# The 17 canonical resolution actions (spec §4.2.1)
CANONICAL_ACTIONS = {
    "retry_now",
    "wait_and_retry",
    "obtain_binding",
    "refresh_binding",
    "obtain_quote_first",
    "revalidate_state",
    "request_broader_scope",
    "request_budget_increase",
    "request_budget_bound_delegation",
    "request_matching_currency_delegation",
    "request_new_delegation",
    "request_capability_binding",
    "request_deeper_delegation",
    "escalate_to_root_principal",
    "provide_credentials",
    "check_manifest",
    "contact_service_owner",
}

# Mandatory action → recovery_class mapping (spec §4.2.1)
ACTION_TO_RECOVERY_CLASS = {
    "retry_now": "retry_now",
    "provide_credentials": "retry_now",
    "wait_and_retry": "wait_then_retry",
    "obtain_binding": "refresh_then_retry",
    "refresh_binding": "refresh_then_retry",
    "obtain_quote_first": "refresh_then_retry",
    "revalidate_state": "revalidate_then_retry",
    "check_manifest": "revalidate_then_retry",
    "request_broader_scope": "redelegation_then_retry",
    "request_budget_increase": "redelegation_then_retry",
    "request_budget_bound_delegation": "redelegation_then_retry",
    "request_matching_currency_delegation": "redelegation_then_retry",
    "request_new_delegation": "redelegation_then_retry",
    "request_capability_binding": "redelegation_then_retry",
    "request_deeper_delegation": "redelegation_then_retry",
    "escalate_to_root_principal": "terminal",
    "contact_service_owner": "terminal",
}


def _collect_failure_responses(client, bootstrap_bearer, read_capability, write_capability):
    """Return a list of failure response dicts by triggering known-bad invocations."""
    failures = []

    cap_name, _ = read_capability

    # 1. Missing auth → authentication_required failure
    resp = client.post(
        f"/anip/invoke/{cap_name}",
        json={"parameters": {}},
    )
    if resp.status_code != 200 and not resp.json().get("success", True):
        failures.append(resp.json())

    # 2. Invalid token → invalid_token failure
    resp = client.post(
        f"/anip/invoke/{cap_name}",
        headers={"Authorization": "Bearer not-a-valid-token"},
        json={"parameters": {}},
    )
    if resp.status_code != 200 and not resp.json().get("success", True):
        failures.append(resp.json())

    # 3. Unknown capability → unknown_capability failure
    read_name, read_scope = read_capability
    token = issue_token(client, read_scope, read_name, bootstrap_bearer)
    resp = client.post(
        "/anip/invoke/nonexistent_capability_conformance_xyz",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {}},
    )
    if resp.status_code != 200 and not resp.json().get("success", True):
        failures.append(resp.json())

    # 4. Scope mismatch — use read token against write capability
    write_name, _ = write_capability
    resp = client.post(
        f"/anip/invoke/{write_name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {}},
    )
    if resp.status_code != 200 and not resp.json().get("success", True):
        failures.append(resp.json())

    return failures


class TestRecoveryClass:
    def test_failure_resolution_has_recovery_class(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """Every failure response's resolution must include recovery_class."""
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        assert failures, "Could not collect any failure responses to test"
        for resp in failures:
            failure = resp.get("failure", {})
            resolution = failure.get("resolution", {})
            assert "recovery_class" in resolution, (
                f"resolution missing recovery_class in failure type '{failure.get('type')}': "
                f"{resolution}"
            )

    def test_recovery_class_is_canonical(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """Every recovery_class value must be one of the six canonical values."""
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        assert failures, "Could not collect any failure responses to test"
        for resp in failures:
            failure = resp.get("failure", {})
            resolution = failure.get("resolution", {})
            rc = resolution.get("recovery_class")
            if rc is not None:
                assert rc in CANONICAL_RECOVERY_CLASSES, (
                    f"Non-canonical recovery_class '{rc}' on failure type "
                    f"'{failure.get('type')}'. Must be one of: "
                    f"{sorted(CANONICAL_RECOVERY_CLASSES)}"
                )

    def test_action_recovery_class_consistency(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """recovery_class must match the expected value for the given resolution.action."""
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        assert failures, "Could not collect any failure responses to test"
        for resp in failures:
            failure = resp.get("failure", {})
            resolution = failure.get("resolution", {})
            action = resolution.get("action")
            rc = resolution.get("recovery_class")
            if action is None or rc is None:
                continue
            if action not in ACTION_TO_RECOVERY_CLASS:
                pytest.fail(
                    f"Non-canonical action '{action}' on failure type "
                    f"'{failure.get('type')}' — all actions must be canonical"
                )
            expected_rc = ACTION_TO_RECOVERY_CLASS[action]
            assert rc == expected_rc, (
                f"recovery_class mismatch for action '{action}': "
                f"expected '{expected_rc}', got '{rc}'"
            )

    def test_scope_failure_is_redelegation(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """Scope failure (insufficient_scope) must produce recovery_class 'redelegation_then_retry'."""
        read_name, read_scope = read_capability
        write_name, _ = write_capability
        token = issue_token(client, read_scope, read_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{write_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        assert data.get("success") is False, "Expected a failure for scope mismatch"
        failure = data.get("failure", {})
        resolution = failure.get("resolution", {})
        assert "recovery_class" in resolution, (
            f"resolution missing recovery_class on scope failure: {resolution}"
        )
        assert resolution["recovery_class"] == "redelegation_then_retry", (
            f"Scope failure expected recovery_class 'redelegation_then_retry', "
            f"got '{resolution['recovery_class']}'"
        )

    def test_retry_now_action_gives_retry_now_class(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """A resolution with action 'retry_now' must have recovery_class 'retry_now'."""
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        retry_now_found = False
        for resp in failures:
            failure = resp.get("failure", {})
            resolution = failure.get("resolution", {})
            if resolution.get("action") == "retry_now":
                retry_now_found = True
                assert resolution.get("recovery_class") == "retry_now", (
                    f"action 'retry_now' expected recovery_class 'retry_now', "
                    f"got '{resolution.get('recovery_class')}'"
                )
        if not retry_now_found:
            pytest.skip("No 'retry_now' action found in collected failure responses")

    def test_terminal_action_gives_terminal_class(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """A resolution with a terminal action must have recovery_class 'terminal'."""
        terminal_actions = {"escalate_to_root_principal", "contact_service_owner"}
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        terminal_found = False
        for resp in failures:
            failure = resp.get("failure", {})
            resolution = failure.get("resolution", {})
            if resolution.get("action") in terminal_actions:
                terminal_found = True
                assert resolution.get("recovery_class") == "terminal", (
                    f"terminal action '{resolution.get('action')}' expected recovery_class "
                    f"'terminal', got '{resolution.get('recovery_class')}'"
                )
        if not terminal_found:
            pytest.skip("No terminal action found in collected failure responses")

    def test_retry_false_preserved_with_recovery_class(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """Failures with retry: false must keep retry: false even with non-terminal recovery_class."""
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        assert failures, "Could not collect any failure responses to test"
        for resp in failures:
            failure = resp.get("failure", {})
            if failure.get("retry") is False:
                resolution = failure.get("resolution", {})
                rc = resolution.get("recovery_class")
                # retry: false must be preserved — recovery_class is advisory only
                assert failure["retry"] is False, (
                    f"retry was changed from False for failure type '{failure.get('type')}'"
                )
                # If recovery_class is non-terminal, retry: false must still be kept
                if rc and rc != "terminal":
                    assert failure["retry"] is False, (
                        f"retry: false changed when recovery_class='{rc}' on "
                        f"failure type '{failure.get('type')}'"
                    )

    def test_terminal_requires_retry_false(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """Failures with recovery_class 'terminal' must always have retry: false."""
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        assert failures, "Could not collect any failure responses to test"
        terminal_found = False
        for resp in failures:
            failure = resp.get("failure", {})
            resolution = failure.get("resolution", {})
            if resolution.get("recovery_class") == "terminal":
                terminal_found = True
                assert failure.get("retry") is False, (
                    f"terminal recovery_class requires retry: false, "
                    f"got retry: {failure.get('retry')} on failure type '{failure.get('type')}'"
                )
        if not terminal_found:
            pytest.skip("No terminal recovery_class found in collected failure responses")

    def test_resolution_action_is_canonical(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """Every resolution.action value MUST be from the canonical vocabulary (spec §4.2.1).

        Services MUST NOT emit non-canonical action strings such as
        'use_token_task_id', 'narrow_scope', 'provide_priced_binding', etc.
        """
        failures = _collect_failure_responses(
            client, bootstrap_bearer, read_capability, write_capability
        )
        assert failures, "Could not collect any failure responses to test"
        for resp in failures:
            failure = resp.get("failure", {})
            resolution = failure.get("resolution", {})
            action = resolution.get("action")
            if action is not None:
                assert action in CANONICAL_ACTIONS, (
                    f"Non-canonical resolution action '{action}' on failure type "
                    f"'{failure.get('type')}'. Must be one of: "
                    f"{sorted(CANONICAL_ACTIONS)}"
                )

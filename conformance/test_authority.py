"""Conformance tests for ANIP v0.15 authority fields.

Validates reason_type on restricted/denied capabilities, resolution.action
canonical value for scope failures, and resolution_hint presence.

Spec references: §4.4 (permission discovery), §4.5 (failure semantics) v0.15.
"""
import pytest
from conftest import issue_token


class TestAuthorityReasonType:
    def _get_permissions_full_scope(self, client, bootstrap_bearer, read_capability, all_scopes):
        """Helper: fetch permissions with all scopes."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        return resp.json()

    def _get_permissions_narrow_scope(self, client, bootstrap_bearer, read_capability):
        """Helper: fetch permissions with only the read capability's scope."""
        cap_name, read_scope = read_capability
        token = issue_token(client, read_scope, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        return resp.json()

    def test_restricted_has_reason_type(
        self, client, bootstrap_bearer, read_capability
    ):
        """Restricted capabilities in /anip/permissions must include reason_type."""
        data = self._get_permissions_narrow_scope(client, bootstrap_bearer, read_capability)
        restricted = data.get("restricted", [])

        if not restricted:
            pytest.skip("No restricted capabilities returned — cannot test reason_type on restricted")

        for entry in restricted:
            assert "reason_type" in entry, (
                f"Restricted capability '{entry.get('capability')}' is missing 'reason_type'. "
                f"Full entry: {entry}"
            )

    def test_denied_has_reason_type(
        self, client, bootstrap_bearer, read_capability, all_scopes
    ):
        """Denied capabilities in /anip/permissions must include reason_type."""
        # First try with full scope (most services return non-delegable or admin-class denials)
        data = self._get_permissions_full_scope(client, bootstrap_bearer, read_capability, all_scopes)
        denied = data.get("denied", [])

        if not denied:
            # Try narrow scope in case that produces denials
            data = self._get_permissions_narrow_scope(client, bootstrap_bearer, read_capability)
            denied = data.get("denied", [])

        if not denied:
            pytest.skip("No denied capabilities returned — cannot test reason_type on denied")

        for entry in denied:
            assert "reason_type" in entry, (
                f"Denied capability '{entry.get('capability')}' is missing 'reason_type'. "
                f"Full entry: {entry}"
            )

    def test_scope_failure_uses_canonical_action(
        self, client, bootstrap_bearer, write_capability, read_capability
    ):
        """Invoke failure for scope insufficiency must use resolution.action == 'request_broader_scope'.

        The deprecated 'request_scope_grant' value must NOT appear. Only the canonical
        v0.15 value 'request_broader_scope' is conformant.
        """
        write_name, _ = write_capability
        read_name, read_scope = read_capability

        # Issue a token scoped only for read, then attempt a write invocation
        token = issue_token(client, read_scope, read_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{write_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )

        data = resp.json()
        # Should be a failure (scope mismatch / insufficient authority)
        if data.get("success") is True:
            pytest.skip(
                f"Invocation of '{write_name}' with read-only scope succeeded — "
                "no scope failure to inspect"
            )

        failure = data.get("failure", {})
        failure_type = failure.get("type", "")

        # Only check canonical action for scope-related failures
        scope_failure_types = {
            "scope_insufficient",
            "authorization_denied",
            "insufficient_scope",
            "scope_mismatch",
        }
        if failure_type not in scope_failure_types:
            pytest.skip(
                f"Failure type '{failure_type}' is not a scope failure type "
                f"({scope_failure_types}) — skipping canonical action check"
            )

        resolution = failure.get("resolution", {})
        action = resolution.get("action")

        assert action == "request_broader_scope", (
            f"Scope failure resolution.action must be 'request_broader_scope' (canonical v0.15), "
            f"got '{action}'. The deprecated 'request_scope_grant' value is not conformant."
        )

    def test_resolution_hint_present_on_restricted(
        self, client, bootstrap_bearer, read_capability
    ):
        """Restricted capabilities should include resolution_hint."""
        data = self._get_permissions_narrow_scope(client, bootstrap_bearer, read_capability)
        restricted = data.get("restricted", [])

        if not restricted:
            pytest.skip("No restricted capabilities returned — cannot test resolution_hint")

        for entry in restricted:
            assert "resolution_hint" in entry, (
                f"Restricted capability '{entry.get('capability')}' is missing 'resolution_hint'. "
                f"Full entry: {entry}"
            )

    # --- Vocabulary validation tests (v0.15) ---

    CANONICAL_REASON_TYPES = {
        "insufficient_scope",
        "insufficient_delegation_depth",
        "stronger_delegation_required",
        "unmet_control_requirement",
        "non_delegable",
    }

    CANONICAL_RESOLUTION_ACTIONS = {
        "request_broader_scope",
        "request_budget_bound_delegation",
        "request_capability_binding",
        "invoke_as_root_principal",
        "wait",
        "contact_administrator",
    }

    def test_reason_type_values_are_canonical(
        self, client, bootstrap_bearer, read_capability
    ):
        """Every reason_type value in restricted/denied must be one of the 5 canonical values."""
        data = self._get_permissions_narrow_scope(client, bootstrap_bearer, read_capability)
        restricted = data.get("restricted", [])
        denied = data.get("denied", [])

        if not restricted and not denied:
            pytest.skip("No restricted or denied capabilities returned — cannot validate reason_type vocabulary")

        for entry in restricted + denied:
            reason_type = entry.get("reason_type")
            assert reason_type in self.CANONICAL_REASON_TYPES, (
                f"Capability '{entry.get('capability')}' has non-canonical reason_type "
                f"'{reason_type}'. Must be one of: {sorted(self.CANONICAL_REASON_TYPES)}"
            )

    def test_resolution_hint_is_canonical_action(
        self, client, bootstrap_bearer, read_capability
    ):
        """Every resolution_hint on restricted entries must be a known canonical action value."""
        data = self._get_permissions_narrow_scope(client, bootstrap_bearer, read_capability)
        restricted = data.get("restricted", [])

        if not restricted:
            pytest.skip("No restricted capabilities returned — cannot validate resolution_hint vocabulary")

        for entry in restricted:
            hint = entry.get("resolution_hint")
            if hint is None:
                continue  # resolution_hint is optional
            assert hint in self.CANONICAL_RESOLUTION_ACTIONS, (
                f"Capability '{entry.get('capability')}' has non-canonical resolution_hint "
                f"'{hint}'. Must be one of: {sorted(self.CANONICAL_RESOLUTION_ACTIONS)}"
            )

    def test_resolution_hint_consistency(
        self, client, bootstrap_bearer, read_capability, write_capability
    ):
        """If a restricted capability has resolution_hint, invoking that capability
        should produce a failure with a matching resolution.action value."""
        data = self._get_permissions_narrow_scope(client, bootstrap_bearer, read_capability)
        restricted = data.get("restricted", [])

        if not restricted:
            pytest.skip("No restricted capabilities returned — cannot test resolution_hint consistency")

        # Find a restricted entry that has a resolution_hint
        target = None
        for entry in restricted:
            if entry.get("resolution_hint"):
                target = entry
                break

        if target is None:
            pytest.skip("No restricted capability with resolution_hint found")

        cap_name = target["capability"]
        expected_action = target["resolution_hint"]

        # Issue a narrow-scope token and attempt to invoke the restricted capability
        read_name, read_scope = read_capability
        token = issue_token(client, read_scope, read_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()

        if data.get("success") is True:
            pytest.skip(
                f"Invocation of restricted capability '{cap_name}' unexpectedly succeeded"
            )

        failure = data.get("failure", {})
        resolution = failure.get("resolution", {})
        action = resolution.get("action")

        assert action == expected_action, (
            f"Restricted capability '{cap_name}' has resolution_hint='{expected_action}' "
            f"but invocation failure resolution.action='{action}'. These must match."
        )

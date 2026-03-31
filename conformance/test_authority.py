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

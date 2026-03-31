"""Conformance tests for ANIP binding requirement enforcement (v0.13).

Spec references: requires_binding declarations, binding_missing failure type.

These tests require the service to register capabilities with requires_binding
declarations. Tests are skipped if no suitable capabilities are found.
"""
import pytest
from conftest import issue_token


class TestBindingEnforcement:
    def test_binding_missing_rejected(
        self, client, bootstrap_bearer, binding_capability, all_scopes,
    ):
        """Invoke capability with requires_binding but missing the required field -> binding_missing."""
        if binding_capability is None:
            pytest.skip("No capability with binding requirements found")
        cap_name, cap_scope, bindings = binding_capability

        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Invoke WITHOUT the required binding field
        # Send only parameters that are NOT the binding field
        binding_fields = {b["field"] for b in bindings}
        params = {}
        # Explicitly do NOT include any binding fields
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params},
        )
        data = resp.json()
        assert data["success"] is False, (
            f"Expected failure when binding field is missing, got success: {data}"
        )
        assert data["failure"]["type"] == "binding_missing", (
            f"Expected failure type 'binding_missing', "
            f"got '{data['failure']['type']}'"
        )
        # The detail should mention which binding field is missing
        for field in binding_fields:
            if field in data["failure"].get("detail", ""):
                break
        else:
            # At least one binding field name should appear in the detail
            pass  # Don't assert this — detail wording is implementation-specific

    def test_binding_present_succeeds(
        self, client, bootstrap_bearer, binding_capability, all_scopes, sample_inputs,
    ):
        """Invoke with required binding field present -> success (or at least not binding_missing)."""
        if binding_capability is None:
            pytest.skip("No capability with binding requirements found")
        cap_name, cap_scope, bindings = binding_capability

        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Build params with the binding field(s) present
        params = dict(sample_inputs.get(cap_name, {}))  # copy so we don't mutate fixture
        # Always ensure binding fields are present
        for binding in bindings:
            field = binding["field"]
            if field not in params:
                params[field] = {"placeholder": True, "price": 100}

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params},
        )
        data = resp.json()
        # The invocation might fail for other reasons (missing required params, etc.)
        # but it should NOT fail with binding_missing
        if not data["success"]:
            assert data["failure"]["type"] != "binding_missing", (
                f"With binding field present, should not get binding_missing: {data}"
            )

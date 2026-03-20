"""Conformance tests for ANIP capability invocation.

Spec references: §4.1-4.5 (invocation, failure semantics),
Conformance Categories 3 and 5.
"""
import re

import pytest
from conftest import issue_token


class TestInvocationSuccess:
    def test_invoke_with_sample_inputs(self, client, bootstrap_bearer, discovery, read_capability, all_scopes, sample_inputs):
        """Test successful invocation using sample inputs if provided."""
        cap_name, _ = read_capability
        params = sample_inputs.get(cap_name)
        if params is None:
            pytest.skip(f"No sample inputs for '{cap_name}' — provide via --sample-inputs")
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "invocation_id" in data
        assert re.match(r"^inv-[0-9a-f]{12}$", data["invocation_id"])

    def test_invocation_id_format(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        # invocation_id must be present even on failure (spec §6.3)
        assert "invocation_id" in data
        assert re.match(r"^inv-[0-9a-f]{12}$", data["invocation_id"])

    def test_client_reference_id_echoed(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        ref_id = "conformance-test-ref-001"
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "parameters": {},
                "client_reference_id": ref_id,
            },
        )
        data = resp.json()
        assert data.get("client_reference_id") == ref_id


class TestInvocationFailures:
    def test_unknown_capability_returns_404(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/invoke/nonexistent_capability_xyz",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "unknown_capability"

    def test_missing_auth_returns_401(self, client, read_capability):
        cap_name, _ = read_capability
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            json={"parameters": {}},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"

    def test_invalid_token_returns_401(self, client, read_capability):
        cap_name, _ = read_capability
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": "Bearer garbage-not-a-jwt"},
            json={"parameters": {}},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"

    def test_missing_auth_vs_invalid_token_distinct(self, client, read_capability):
        """Missing auth and invalid token must produce different failure.type values."""
        cap_name, _ = read_capability

        # Missing auth
        resp_missing = client.post(
            f"/anip/invoke/{cap_name}",
            json={"parameters": {}},
        )
        # Invalid token
        resp_invalid = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": "Bearer garbage-not-a-jwt"},
            json={"parameters": {}},
        )
        type_missing = resp_missing.json()["failure"]["type"]
        type_invalid = resp_invalid.json()["failure"]["type"]
        assert type_missing != type_invalid, (
            f"Missing auth and invalid token should have different failure types, "
            f"both returned '{type_missing}'"
        )

    def test_failure_has_required_fields(self, client, read_capability):
        """Every failure response must include type, detail, resolution, retry."""
        cap_name, _ = read_capability
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": "Bearer garbage-not-a-jwt"},
            json={"parameters": {}},
        )
        failure = resp.json()["failure"]
        assert "type" in failure
        assert "detail" in failure
        assert "resolution" in failure
        assert "retry" in failure
        assert isinstance(failure["retry"], bool)

    def test_scope_mismatch(self, client, bootstrap_bearer, write_capability, read_capability):
        """Token scoped for read should be denied for write capability."""
        write_name, _ = write_capability
        read_name, read_scope = read_capability
        # Issue token with only read scope
        token = issue_token(client, read_scope, read_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{write_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        assert data["success"] is False


class TestCostSignaling:
    def test_financial_capability_includes_cost_actual(self, client, bootstrap_bearer, discovery, all_scopes, sample_inputs):
        """If a capability declares financial=true and sample inputs are provided,
        successful invoke should include cost_actual."""
        for name, meta in discovery["capabilities"].items():
            if meta.get("financial") is True:
                params = sample_inputs.get(name)
                if params is None:
                    pytest.skip(f"No sample inputs for financial capability '{name}' — provide via --sample-inputs")
                token = issue_token(client, all_scopes, name, bootstrap_bearer)
                resp = client.post(
                    f"/anip/invoke/{name}",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"parameters": params},
                )
                assert resp.status_code == 200, (
                    f"Financial capability '{name}' invocation failed: {resp.status_code}"
                )
                data = resp.json()
                assert data["success"] is True
                assert "cost_actual" in data, (
                    f"Financial capability '{name}' should include cost_actual"
                )
                break  # only need to test one

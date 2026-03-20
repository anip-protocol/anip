"""Conformance tests for ANIP audit log queries.

Spec references: §5.4 (observability), Conformance Category 6.
"""
from conftest import issue_token


class TestAudit:
    def test_audit_response_shape(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Make an invocation so there's at least one audit entry
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )

        resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_audit_entry_required_fields(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Ensure at least one entry
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )

        resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["count"] >= 1
        entry = data["entries"][0]
        assert "invocation_id" in entry
        assert "capability" in entry
        assert "timestamp" in entry
        assert "success" in entry

    def test_audit_filter_by_capability(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Make an invocation
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )

        resp = client.post(
            f"/anip/audit?capability={cap_name}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("capability_filter") == cap_name
        # All returned entries should match the filter
        for entry in data["entries"]:
            assert entry["capability"] == cap_name

    def test_audit_filter_combination(self, client, bootstrap_bearer, read_capability, all_scopes):
        """Combined filters (capability + since) should work together."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        resp = client.post(
            f"/anip/audit?capability={cap_name}&since=2020-01-01T00:00:00Z",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "entries" in data

    def test_audit_unauthenticated_returns_401(self, client):
        resp = client.post("/anip/audit")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert "failure" in data

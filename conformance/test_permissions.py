"""Conformance tests for ANIP permission discovery.

Spec references: §4.4 (permission discovery), Conformance Category 4.
"""
from conftest import issue_token


class TestPermissions:
    def test_permissions_response_shape(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "restricted" in data
        assert "denied" in data
        assert isinstance(data["available"], list)
        assert isinstance(data["restricted"], list)
        assert isinstance(data["denied"], list)

    def test_full_scope_shows_available(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        available_names = [c["capability"] for c in data["available"]]
        # At least one capability should be available with full scope
        assert len(available_names) > 0

    def test_narrow_scope_restricts_capabilities(self, client, bootstrap_bearer, read_capability, write_capability):
        read_name, read_scope = read_capability
        write_name, _ = write_capability
        # Issue token with only read scope
        token = issue_token(client, read_scope, read_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        restricted_names = [c["capability"] for c in data["restricted"]]
        # The write capability should be restricted when we only have read scope
        assert write_name in restricted_names, (
            f"Expected '{write_name}' in restricted with scope {read_scope}, "
            f"got restricted: {restricted_names}"
        )

    def test_available_entry_has_capability_field(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        for entry in resp.json()["available"]:
            assert "capability" in entry

    def test_restricted_entry_has_reason(self, client, bootstrap_bearer, read_capability):
        cap_name, read_scope = read_capability
        token = issue_token(client, read_scope, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        for entry in resp.json()["restricted"]:
            assert "capability" in entry
            assert "reason" in entry

    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/anip/permissions")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert "failure" in data

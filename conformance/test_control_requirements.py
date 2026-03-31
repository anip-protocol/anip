"""Conformance tests for ANIP control requirement enforcement (v0.13).

Spec references: control_requirements declarations, control_requirement_unsatisfied
failure type, unmet_token_requirements in permission discovery.

These tests require the service to register capabilities with control_requirements
declarations (particularly cost_ceiling). Tests are skipped if no suitable
capabilities are found.
"""
import pytest
from conftest import issue_token


class TestControlRequirementEnforcement:
    def test_cost_ceiling_without_budget_rejected(
        self, client, bootstrap_bearer, cost_ceiling_capability, all_scopes,
    ):
        """Invoke capability with cost_ceiling control requirement, but token has no budget
        -> control_requirement_unsatisfied."""
        if cost_ceiling_capability is None:
            pytest.skip("No capability with cost_ceiling control requirement found")
        cap_name, cap_scope = cost_ceiling_capability

        # Issue token WITHOUT budget — cost_ceiling requires a budget to be present
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        assert data["success"] is False, (
            f"Expected failure without budget on cost_ceiling capability, "
            f"got success: {data}"
        )
        assert data["failure"]["type"] == "control_requirement_unsatisfied", (
            f"Expected failure type 'control_requirement_unsatisfied', "
            f"got '{data['failure']['type']}'"
        )
        # Detail should mention cost_ceiling
        assert "cost_ceiling" in data["failure"].get("detail", ""), (
            f"Expected 'cost_ceiling' in failure detail: {data['failure']}"
        )


class TestControlRequirementsInPermissions:
    def test_unmet_token_requirements_in_permissions(
        self, client, bootstrap_bearer, cost_ceiling_capability, all_scopes,
    ):
        """Query permissions with token that lacks budget, capability requires cost_ceiling
        -> restricted capability has unmet_token_requirements."""
        if cost_ceiling_capability is None:
            pytest.skip("No capability with cost_ceiling control requirement found")
        cap_name, cap_scope = cost_ceiling_capability

        # Issue token WITHOUT budget
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, (
            f"Permissions query failed: {resp.status_code} {resp.text}"
        )
        data = resp.json()

        # The capability with cost_ceiling should appear in restricted
        restricted_names = [r["capability"] for r in data.get("restricted", [])]
        assert cap_name in restricted_names, (
            f"Expected '{cap_name}' in restricted capabilities when token lacks budget, "
            f"got restricted: {restricted_names}, available: "
            f"{[a['capability'] for a in data.get('available', [])]}"
        )

        # Find the restricted entry and check unmet_token_requirements
        restricted_entry = next(
            r for r in data["restricted"] if r["capability"] == cap_name
        )
        unmet = restricted_entry.get("unmet_token_requirements", [])
        assert "cost_ceiling" in unmet, (
            f"Expected 'cost_ceiling' in unmet_token_requirements, got: {unmet}"
        )

"""Conformance tests for ANIP budget enforcement (v0.13).

Spec references: budget constraints in delegation tokens, budget enforcement
during invocation, budget narrowing in delegation chains.

These tests require the service to register capabilities with financial cost
declarations. Tests are skipped if no suitable capabilities are found.
"""
import pytest
from conftest import issue_token, issue_token_full


class TestBudgetTokenIssuance:
    def test_budget_echoed_in_token_issuance(
        self, client, bootstrap_bearer, fixed_cost_capability, all_scopes,
    ):
        """Issue token with budget, verify response echoes budget."""
        if fixed_cost_capability is None:
            pytest.skip("No capability with fixed financial cost found")
        cap_name, cap_scope, financial = fixed_cost_capability

        status, data = issue_token_full(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": financial["currency"], "max_amount": 1000},
        )
        assert status == 200, f"Token issuance failed: {status} {data}"
        assert data["issued"] is True
        assert "budget" in data, "Budget should be echoed in token issuance response"
        assert data["budget"]["currency"] == financial["currency"]
        assert data["budget"]["max_amount"] == 1000


class TestBudgetEnforcement:
    def test_budget_enforcement_fixed_cost_within(
        self, client, bootstrap_bearer, fixed_cost_capability, all_scopes,
    ):
        """Issue token with budget above fixed cost, invoke -> success."""
        if fixed_cost_capability is None:
            pytest.skip("No capability with fixed financial cost found")
        cap_name, cap_scope, financial = fixed_cost_capability

        cost_amount = financial.get("amount", 0)
        if cost_amount is None or cost_amount == 0:
            pytest.skip("Fixed cost capability has no financial amount")

        budget_amount = cost_amount * 2  # budget is well above cost
        token = issue_token(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": financial["currency"], "max_amount": budget_amount},
        )
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        assert data["success"] is True, (
            f"Expected success with budget ${budget_amount} >= cost ${cost_amount}, "
            f"got: {data}"
        )

    def test_budget_exceeded_fixed_cost(
        self, client, bootstrap_bearer, fixed_cost_capability, all_scopes,
    ):
        """Issue token with budget below fixed cost, invoke -> budget_exceeded."""
        if fixed_cost_capability is None:
            pytest.skip("No capability with fixed financial cost found")
        cap_name, cap_scope, financial = fixed_cost_capability

        cost_amount = financial.get("amount", 0)
        if cost_amount is None or cost_amount == 0:
            pytest.skip("Fixed cost capability has no financial amount")

        # Budget intentionally below the fixed cost
        budget_amount = cost_amount * 0.5
        token = issue_token(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": financial["currency"], "max_amount": budget_amount},
        )
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        assert data["success"] is False, (
            f"Expected failure with budget ${budget_amount} < cost ${cost_amount}"
        )
        assert data["failure"]["type"] == "budget_exceeded", (
            f"Expected failure type 'budget_exceeded', got '{data['failure']['type']}'"
        )

    def test_budget_currency_mismatch(
        self, client, bootstrap_bearer, fixed_cost_capability, all_scopes,
    ):
        """Token budget in different currency than capability cost -> budget_currency_mismatch."""
        if fixed_cost_capability is None:
            pytest.skip("No capability with fixed financial cost found")
        cap_name, cap_scope, financial = fixed_cost_capability

        cost_amount = financial.get("amount", 0)
        if cost_amount is None or cost_amount == 0:
            pytest.skip("Fixed cost capability has no financial amount")

        # Use a different currency than the capability's cost
        cost_currency = financial["currency"]
        mismatch_currency = "EUR" if cost_currency != "EUR" else "GBP"

        token = issue_token(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": mismatch_currency, "max_amount": 1000},
        )
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        assert data["success"] is False, (
            f"Expected failure with currency mismatch ({mismatch_currency} vs {cost_currency})"
        )
        assert data["failure"]["type"] == "budget_currency_mismatch", (
            f"Expected failure type 'budget_currency_mismatch', "
            f"got '{data['failure']['type']}'"
        )


class TestBudgetNarrowing:
    def test_budget_narrowing_success(
        self, client, bootstrap_bearer, fixed_cost_capability, all_scopes,
    ):
        """Issue parent token with budget $500, delegate child with budget $300 -> success."""
        if fixed_cost_capability is None:
            pytest.skip("No capability with fixed financial cost found")
        cap_name, cap_scope, financial = fixed_cost_capability
        currency = financial["currency"]

        # Issue parent token with budget $500
        status, parent_data = issue_token_full(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": currency, "max_amount": 500},
        )
        assert status == 200, f"Parent token issuance failed: {status} {parent_data}"
        assert parent_data["issued"] is True
        parent_token_id = parent_data["token_id"]

        # Delegate child token with narrower budget $300
        status, child_data = issue_token_full(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": currency, "max_amount": 300},
            parent_token=parent_token_id,
        )
        assert status == 200, (
            f"Child token delegation with narrower budget should succeed: "
            f"{status} {child_data}"
        )
        assert child_data.get("issued") is True, (
            f"Child token should be issued: {child_data}"
        )

    def test_budget_narrowing_exceeds_parent(
        self, client, bootstrap_bearer, fixed_cost_capability, all_scopes,
    ):
        """Issue parent token with budget $500, delegate child with budget $600 -> failure."""
        if fixed_cost_capability is None:
            pytest.skip("No capability with fixed financial cost found")
        cap_name, cap_scope, financial = fixed_cost_capability
        currency = financial["currency"]

        # Issue parent token with budget $500
        status, parent_data = issue_token_full(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": currency, "max_amount": 500},
        )
        assert status == 200, f"Parent token issuance failed: {status} {parent_data}"
        parent_token_id = parent_data["token_id"]

        # Try to delegate child with wider budget $600 -> should fail
        status, child_data = issue_token_full(
            client, all_scopes, cap_name, bootstrap_bearer,
            budget={"currency": currency, "max_amount": 600},
            parent_token=parent_token_id,
        )
        # The service should reject this as budget escalation
        issued = child_data.get("issued", False)
        assert issued is not True, (
            f"Child token with budget exceeding parent should not be issued: {child_data}"
        )
        # Check for appropriate failure
        failure = child_data.get("failure", {})
        assert failure.get("type") in ("budget_exceeded", "scope_escalation"), (
            f"Expected budget escalation failure, got: {child_data}"
        )

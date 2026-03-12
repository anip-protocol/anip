"""ANIP v0.2 Conformance Test Suite.

Validates that an ANIP service behaves according to its manifest declarations.
Portable: run against any ANIP service URL with --anip-url, or against the
bundled app in-process (default).

Usage:
    # Against bundled app (default)
    pytest tests/test_conformance.py -v

    # Against a live server
    pytest tests/test_conformance.py -v --anip-url http://localhost:8000 --anip-api-key my-key
"""

import pytest


def _issue(service, scope, capability, auth_headers):
    resp = service.post("/anip/tokens", json={
        "subject": "agent:conformance-tester",
        "scope": scope,
        "capability": capability,
    }, headers=auth_headers)
    return resp.json()["token"]


class TestSideEffectAccuracy:
    """Verify side_effect declarations match actual behavior."""

    def test_read_capability_does_not_mutate_state(self, service, auth_headers):
        """search_flights is declared as 'read' — calling it should not change state."""
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        params = {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}
        r1 = service.post("/anip/invoke/search_flights", json={"token": token, "parameters": params})
        r2 = service.post("/anip/invoke/search_flights", json={"token": token, "parameters": params})
        assert r1.json()["result"] == r2.json()["result"]


class TestScopeEnforcement:
    """Verify scope constraints are enforced."""

    def test_wrong_capability_scope_is_rejected(self, service, auth_headers):
        """Token scoped for search should not allow booking."""
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": token,
            "parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1},
        })
        body = resp.json()
        assert body["success"] is False
        assert body["failure"]["type"] in ("purpose_mismatch", "insufficient_authority")


class TestBudgetEnforcement:
    """Verify budget constraints from scope are enforced."""

    def test_over_budget_invocation_is_rejected(self, service, auth_headers):
        """Booking a flight that costs more than the budget should fail with budget_exceeded."""
        search_token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        search_resp = service.post("/anip/invoke/search_flights", json={
            "token": search_token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        })
        flights = search_resp.json()["result"]["flights"]
        expensive = max(flights, key=lambda f: f["price"])

        book_token = _issue(service, ["travel.book:max_$100"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": book_token,
            "parameters": {
                "flight_number": expensive["flight_number"],
                "date": "2026-03-10",
                "passengers": 1,
            },
        })
        body = resp.json()
        assert body["success"] is False
        assert body["failure"]["type"] == "budget_exceeded"


class TestFailureSemantics:
    """Verify failures include structured resolution guidance."""

    def test_failure_has_type_detail_resolution(self, service, auth_headers):
        """Every ANIP failure must have type, detail, and resolution."""
        token = _issue(service, ["travel.book:max_$1"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": token,
            "parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1},
        })
        body = resp.json()
        assert body["success"] is False
        failure = body["failure"]
        assert "type" in failure
        assert "detail" in failure
        assert "resolution" in failure
        assert "action" in failure["resolution"]

    def test_budget_exceeded_resolution_is_actionable(self, service, auth_headers):
        """Budget exceeded should tell the agent who can grant more budget."""
        token = _issue(service, ["travel.book:max_$1"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": token,
            "parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1},
        })
        failure = resp.json()["failure"]
        assert failure["type"] == "budget_exceeded"
        assert failure["resolution"]["action"] == "request_budget_increase"
        assert "grantable_by" in failure["resolution"]


class TestCostAccuracy:
    """Verify actual costs fall within declared ranges."""

    def test_booking_cost_within_declared_range(self, service, auth_headers):
        """Actual booking cost should fall within manifest-declared cost range."""
        manifest = service.get("/anip/manifest").json()
        book_cost = manifest["capabilities"]["book_flight"]["cost"]["financial"]
        range_min = book_cost["range_min"]
        range_max = book_cost["range_max"]

        search_token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        flights = service.post("/anip/invoke/search_flights", json={
            "token": search_token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        }).json()["result"]["flights"]
        cheapest = min(flights, key=lambda f: f["price"])

        book_token = _issue(service, [f"travel.book:max_${int(cheapest['price']) + 100}"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": book_token,
            "parameters": {
                "flight_number": cheapest["flight_number"],
                "date": "2026-03-10",
                "passengers": 1,
            },
        })
        body = resp.json()
        assert body["success"] is True
        actual_cost = body["cost_actual"]["financial"]["amount"]
        assert range_min <= actual_cost <= range_max, (
            f"Actual cost ${actual_cost} outside declared range ${range_min}-${range_max}"
        )

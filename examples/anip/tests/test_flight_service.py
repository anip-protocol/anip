"""Integration tests for the ANIP flight service.

Tests the application through HTTP using the new anip-service + anip-fastapi
runtime. SDK-internal tests (Merkle trees, checkpoints, audit schemas, etc.)
live in the SDK packages themselves.
"""
import pytest
from fastapi.testclient import TestClient
from app import app, service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get a valid ANIP token via API key bootstrap."""
    resp = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer demo-human-key"},
        json={
            "subject": "human:samir@example.com",
            "scope": ["travel.search", "travel.book"],
            "capability": "search_flights",
            "purpose_parameters": {"task_id": "test"},
        },
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


class TestDiscovery:
    def test_well_known_anip(self, client):
        resp = client.get("/.well-known/anip")
        assert resp.status_code == 200
        data = resp.json()
        assert "search_flights" in data["anip_discovery"]["capabilities"]
        assert "book_flight" in data["anip_discovery"]["capabilities"]

    def test_manifest_signed(self, client):
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200
        assert "X-ANIP-Signature" in resp.headers

    def test_jwks(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200
        assert len(resp.json()["keys"]) > 0


class TestTokens:
    def test_issue_token_with_api_key(self, client):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={
                "scope": ["travel.search"],
                "capability": "search_flights",
                "purpose_parameters": {"task_id": "test"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["issued"] is True

    def test_unauthenticated_rejected(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["travel.search"]},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "provide_credentials"


class TestInvoke:
    def test_search_flights(self, client, auth_headers):
        resp = client.post(
            "/anip/invoke/search_flights",
            headers=auth_headers,
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["count"] == 3

    def test_search_flights_no_results(self, client, auth_headers):
        resp = client.post(
            "/anip/invoke/search_flights",
            headers=auth_headers,
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2099-01-01"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["count"] == 0

    def test_book_flight(self, client):
        # Need a token with travel.book scope
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={
                "subject": "human:samir@example.com",
                "scope": ["travel.search", "travel.book"],
                "capability": "book_flight",
                "purpose_parameters": {"task_id": "test-booking"},
            },
        )
        assert resp.status_code == 200
        token = resp.json()["token"]

        resp = client.post(
            "/anip/invoke/book_flight",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {
                "flight_number": "AA100",
                "date": "2026-03-10",
                "passengers": 1,
                "quote_id": {"id": "qt-test-1234", "price": 420, "issued_at": int(__import__('time').time())},
            }},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["booking_id"].startswith("BK-")
        assert data["result"]["total_cost"] == 420.0

    def test_invoke_without_auth(self, client):
        resp = client.post(
            "/anip/invoke/search_flights",
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "request_new_delegation"

    def test_invoke_unknown_capability(self, client, auth_headers):
        resp = client.post(
            "/anip/invoke/nonexistent",
            headers=auth_headers,
            json={"parameters": {}},
        )
        # Unknown capability returns 404 via failure mapping
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False


class TestCheckpoints:
    def test_list_checkpoints(self, client):
        resp = client.get("/anip/checkpoints")
        assert resp.status_code == 200
        assert "checkpoints" in resp.json()


class TestPermissions:
    def test_permissions_show_search_and_book(self, client, auth_headers):
        resp = client.post("/anip/permissions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        cap_names = [c["capability"] for c in data["available"]]
        assert "search_flights" in cap_names
        assert "book_flight" in cap_names

    def test_permissions_restricted_without_book_scope(self, client):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={
                "scope": ["travel.search"],
                "capability": "search_flights",
                "purpose_parameters": {"task_id": "test"},
            },
        )
        token = resp.json()["token"]
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        restricted_names = [c["capability"] for c in data["restricted"]]
        assert "book_flight" in restricted_names


class TestAudit:
    def test_audit_returns_entries(self, client, auth_headers):
        client.post(
            "/anip/invoke/search_flights",
            headers=auth_headers,
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )
        resp = client.post("/anip/audit", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert "entries" in data

    def test_audit_filter_by_capability(self, client, auth_headers):
        client.post(
            "/anip/invoke/search_flights",
            headers=auth_headers,
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )
        resp = client.post(
            "/anip/audit?capability=search_flights",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["capability_filter"] == "search_flights"


class TestFailureScenarios:
    def test_scope_mismatch(self, client):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={
                "subject": "human:samir@example.com",
                "scope": ["travel.search"],
                "capability": "search_flights",
                "purpose_parameters": {"task_id": "test-scope"},
            },
        )
        token = resp.json()["token"]
        resp = client.post(
            "/anip/invoke/book_flight",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1}},
        )
        data = resp.json()
        assert data["success"] is False

    def test_unknown_capability(self, client, auth_headers):
        resp = client.post(
            "/anip/invoke/cancel_flight",
            headers=auth_headers,
            json={"parameters": {}},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "unknown_capability"

    def test_invoke_with_invalid_token(self, client):
        resp = client.post(
            "/anip/invoke/search_flights",
            headers={"Authorization": "Bearer garbage-jwt-string"},
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"

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


class TestParameterValidation:
    """SPEC.md §6.3: the runtime refuses parameters that do not match the
    declared inputs; the handlers validate what the runtime does not."""

    RESOLUTION = {
        "action": "retry_now",
        "recovery_class": "retry_now",
        "requires": "parameters that match the capability's declared inputs",
    }

    def _token(self, client, capability):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={"scope": ["travel.search", "travel.book"], "capability": capability},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def _invoke(self, client, capability, parameters):
        return client.post(
            f"/anip/invoke/{capability}",
            headers={"Authorization": f"Bearer {self._token(client, capability)}"},
            json={"parameters": parameters},
        )

    def _booking(self, **overrides):
        import time
        parameters = {
            "flight_number": "AA100",
            "date": "2026-03-10",
            "passengers": 1,
            "quote_id": {"id": "qt-test-1234", "price": 420, "issued_at": int(time.time())},
        }
        parameters.update(overrides)
        return parameters

    def test_quote_id_is_optional_and_demanded_by_the_binding(self, client):
        manifest = client.get("/anip/manifest").json()
        inputs = {i["name"]: i for i in manifest["capabilities"]["book_flight"]["inputs"]}
        assert inputs["quote_id"]["required"] is False
        assert inputs["flight_number"]["required"] is True
        assert inputs["date"]["required"] is True
        assert inputs["passengers"]["required"] is False

        parameters = self._booking()
        del parameters["quote_id"]
        resp = self._invoke(client, "book_flight", parameters)
        assert resp.json()["failure"]["type"] == "binding_missing"
        assert resp.status_code == 403

    def test_search_without_required_inputs_is_refused_by_the_runtime(self, client):
        resp = self._invoke(client, "search_flights", {"origin": "SEA"})

        assert resp.status_code == 400
        assert resp.json()["failure"] == {
            "type": "invalid_parameters",
            "detail": "search_flights is missing required input(s): destination, date",
            "resolution": self.RESOLUTION,
            "retry": False,
        }

    def test_booking_without_required_inputs_is_refused_by_the_runtime(self, client):
        parameters = self._booking()
        del parameters["flight_number"]
        resp = self._invoke(client, "book_flight", parameters)

        assert resp.status_code == 400
        assert resp.json()["failure"] == {
            "type": "invalid_parameters",
            "detail": "book_flight is missing required input(s): flight_number",
            "resolution": self.RESOLUTION,
            "retry": False,
        }

    @pytest.mark.parametrize("passengers,received", [
        ("two", "string"), (1.5, "number"), (True, "boolean"), ([1], "array"),
    ])
    def test_passengers_of_the_wrong_type_is_refused_by_the_runtime(
        self, client, passengers, received
    ):
        resp = self._invoke(client, "book_flight", self._booking(passengers=passengers))

        assert resp.status_code == 400
        failure = resp.json()["failure"]
        assert failure["type"] == "invalid_parameters"
        assert failure["detail"] == (
            f"book_flight has invalid input(s): 'passengers' must be integer, got {received}")

    def test_integral_float_books_for_that_many_passengers(self, client):
        resp = client.post(
            "/anip/invoke/book_flight",
            headers={"Authorization": f"Bearer {self._token(client, 'book_flight')}",
                     "Content-Type": "application/json"},
            content=__import__("json").dumps(
                {"parameters": self._booking(passengers=2.0)}).encode(),
        )

        assert b'"passengers": 2.0' in resp.request.content
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["total_cost"] == 840.0
        from anip_flight_demo.domain.flights import get_booking
        booked = get_booking(data["result"]["booking_id"]).passengers
        assert booked == 2 and isinstance(booked, int)

    @pytest.mark.parametrize("overrides,word", [
        ({"flight_number": ""}, "flight_number"),
        ({"date": ""}, "date"),
        ({"flight_number": "   "}, "flight_number"),
        ({"date": True}, "date"),
        ({"passengers": 0}, "passengers"),
        ({"passengers": -1}, "passengers"),
    ])
    def test_handler_refusals_carry_the_same_resolution(self, client, overrides, word):
        resp = self._invoke(client, "book_flight", self._booking(**overrides))

        assert resp.status_code == 400
        failure = resp.json()["failure"]
        assert failure["type"] == "invalid_parameters"
        assert word in failure["detail"]
        # A domain type is validated by the handler, not type-checked by the runtime.
        assert "boolean" not in failure["detail"]
        assert failure["resolution"] == self.RESOLUTION
        assert failure["retry"] is False

    @pytest.mark.parametrize("overrides", [{"origin": ""}, {"destination": True}, {"date": 20260310}])
    def test_search_handler_refusals_carry_the_same_resolution(self, client, overrides):
        parameters = {"origin": "SEA", "destination": "SFO", "date": "2026-03-10", **overrides}
        resp = self._invoke(client, "search_flights", parameters)

        assert resp.status_code == 400
        failure = resp.json()["failure"]
        assert failure["type"] == "invalid_parameters"
        assert "boolean" not in failure["detail"] and "number" not in failure["detail"]
        assert failure["resolution"] == self.RESOLUTION
        assert failure["retry"] is False


class TestApprovedContinuation:
    """SPEC.md §4.7: digests are over RFC 8785 canonical JSON, so an approved
    5 continued as 5.0 is the same request."""

    def _token(self, client, scope):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={"scope": scope, "capability": "book_flight"},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_integral_float_continues_an_approved_group_booking(self, client):
        import json
        import time

        requester = {"Authorization": f"Bearer {self._token(client, ['travel.book'])}"}
        approver = {"Authorization": f"Bearer {self._token(client, ['approver:book_flight'])}"}
        parameters = {
            "flight_number": "AA100", "date": "2026-03-10", "passengers": 5,
            "quote_id": {"id": "qt-test-1234", "price": 420, "issued_at": int(time.time())},
        }
        first = client.post(
            "/anip/invoke/book_flight", headers=requester, json={"parameters": parameters})
        assert first.status_code == 400
        assert first.json()["failure"]["type"] == "approval_required"
        request_id = first.json()["failure"]["approval_required"]["approval_request_id"]
        grant = client.post(
            "/anip/approval_grants", headers=approver,
            json={"approval_request_id": request_id, "grant_type": "one_time"})
        assert grant.status_code == 200, grant.text
        grant_id = grant.json()["grant_id"]

        drifted = client.post(
            "/anip/invoke/book_flight", headers=requester,
            json={"parameters": {**parameters, "passengers": 6}, "approval_grant": grant_id})
        assert drifted.status_code == 400
        assert drifted.json()["failure"]["type"] == "grant_param_drift"

        body = json.dumps(
            {"parameters": {**parameters, "passengers": 5.0}, "approval_grant": grant_id})
        assert '"passengers": 5.0' in body
        continued = client.post(
            "/anip/invoke/book_flight", content=body.encode(),
            headers={**requester, "Content-Type": "application/json"})

        assert continued.status_code == 200, continued.text
        assert continued.json()["result"]["total_cost"] == 2100.0

        spent = client.post(
            "/anip/invoke/book_flight", headers=requester,
            json={"parameters": parameters, "approval_grant": grant_id})
        assert spent.json()["failure"]["type"] == "grant_consumed"
        assert spent.status_code == 409

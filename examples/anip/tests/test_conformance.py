"""ANIP v0.3 Conformance Test Suite.

Validates that an ANIP service behaves according to its manifest declarations.
Portable: run against any ANIP service URL with --anip-url, or against the
bundled app in-process (default).

Usage:
    # Against bundled app (default)
    pytest tests/test_conformance.py -v

    # Against a live server
    pytest tests/test_conformance.py -v --anip-url http://localhost:8000 --anip-api-key my-key
"""

from anip_server import MerkleTree


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


# ---------------------------------------------------------------------------
# v0.3 Conformance Tests — Trust Level and Checkpoints
# ---------------------------------------------------------------------------


class TestDiscoveryV03:
    """Verify v0.3 discovery response fields."""

    def test_discovery_includes_trust_level(self, service):
        """Discovery response must include trust_level field."""
        resp = service.get("/.well-known/anip")
        discovery = resp.json()["anip_discovery"]
        assert "trust_level" in discovery
        assert discovery["trust_level"] in ("signed", "anchored", "attested")

    def test_discovery_protocol_is_v03(self, service):
        """Discovery response must advertise anip/0.3 protocol."""
        resp = service.get("/.well-known/anip")
        discovery = resp.json()["anip_discovery"]
        assert discovery["protocol"] == "anip/0.3"

    def test_discovery_includes_checkpoints_endpoint(self, service):
        """Discovery response must advertise the checkpoints endpoint."""
        resp = service.get("/.well-known/anip")
        endpoints = resp.json()["anip_discovery"]["endpoints"]
        assert "checkpoints" in endpoints
        assert endpoints["checkpoints"] == "/anip/checkpoints"


class TestCheckpointEndpoints:
    """Verify checkpoint list and detail endpoints."""

    def test_checkpoints_list_returns_list(self, service):
        """GET /anip/checkpoints must return a JSON object with a checkpoints list."""
        resp = service.get("/anip/checkpoints")
        body = resp.json()
        assert "checkpoints" in body
        assert isinstance(body["checkpoints"], list)

    def test_checkpoint_lifecycle(self, service, auth_headers):
        """After invoking a capability and creating a checkpoint,
        the checkpoints list should contain at least one entry with
        the expected fields."""
        # 1. Invoke a capability to generate audit log entries
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        service.post("/anip/invoke/search_flights", json={
            "token": token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        })

        # 2. Trigger a checkpoint via the database helper
        from anip_flight_demo.data.database import create_checkpoint
        create_checkpoint()

        # 3. List checkpoints — should have at least one
        resp = service.get("/anip/checkpoints")
        body = resp.json()
        assert len(body["checkpoints"]) >= 1

        checkpoint = body["checkpoints"][-1]
        assert "checkpoint_id" in checkpoint
        assert "merkle_root" in checkpoint
        assert "range" in checkpoint
        assert "first_sequence" in checkpoint["range"]
        assert "last_sequence" in checkpoint["range"]
        assert "entry_count" in checkpoint
        assert "signature" in checkpoint
        assert "timestamp" in checkpoint

    def test_checkpoint_detail_by_id(self, service, auth_headers):
        """GET /anip/checkpoints/{id} returns checkpoint detail with merkle_root."""
        # Generate audit entry and checkpoint
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        service.post("/anip/invoke/search_flights", json={
            "token": token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        })
        from anip_flight_demo.data.database import create_checkpoint
        create_checkpoint()

        # Get the latest checkpoint id
        checkpoints = service.get("/anip/checkpoints").json()["checkpoints"]
        checkpoint_id = checkpoints[-1]["checkpoint_id"]

        # Fetch detail
        resp = service.get(f"/anip/checkpoints/{checkpoint_id}")
        body = resp.json()
        assert "checkpoint" in body
        ckpt = body["checkpoint"]
        assert ckpt["checkpoint_id"] == checkpoint_id
        assert "merkle_root" in ckpt
        assert ckpt["merkle_root"].startswith("sha256:")

    def test_checkpoint_inclusion_proof(self, service, auth_headers):
        """GET /anip/checkpoints/{id}?include_proof=true&leaf_index=0
        returns an inclusion proof."""
        # Generate audit entry and checkpoint
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        service.post("/anip/invoke/search_flights", json={
            "token": token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        })
        from anip_flight_demo.data.database import create_checkpoint
        create_checkpoint()

        # Get the latest checkpoint
        checkpoints = service.get("/anip/checkpoints").json()["checkpoints"]
        checkpoint_id = checkpoints[-1]["checkpoint_id"]

        # Request inclusion proof for leaf_index=0
        resp = service.get(
            f"/anip/checkpoints/{checkpoint_id}",
            params={"include_proof": "true", "leaf_index": 0},
        )
        body = resp.json()
        assert "inclusion_proof" in body
        proof = body["inclusion_proof"]
        assert proof["leaf_index"] == 0
        assert "path" in proof
        assert isinstance(proof["path"], list)
        assert "merkle_root" in proof
        assert proof["merkle_root"].startswith("sha256:")
        assert "leaf_count" in proof
        assert proof["leaf_count"] >= 1

    def test_inclusion_proof_verifies_against_merkle_root(self, service, auth_headers):
        """The inclusion proof returned by the checkpoint endpoint must
        verify against the checkpoint's merkle_root using the Merkle tree
        verification algorithm."""
        # Generate audit entry and checkpoint
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        service.post("/anip/invoke/search_flights", json={
            "token": token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        })
        from anip_flight_demo.data.database import create_checkpoint, rebuild_merkle_tree_to
        create_checkpoint()

        # Get checkpoint
        checkpoints = service.get("/anip/checkpoints").json()["checkpoints"]
        checkpoint = checkpoints[-1]
        checkpoint_id = checkpoint["checkpoint_id"]

        # Get inclusion proof
        resp = service.get(
            f"/anip/checkpoints/{checkpoint_id}",
            params={"include_proof": "true", "leaf_index": 0},
        )
        body = resp.json()
        proof_data = body["inclusion_proof"]
        expected_root = proof_data["merkle_root"]
        proof_path = proof_data["path"]

        # Rebuild the tree to get the leaf data for verification
        ckpt_detail = body["checkpoint"]
        last_seq = ckpt_detail["range"]["last_sequence"]
        tree = rebuild_merkle_tree_to(last_seq)

        # The tree's root should match the checkpoint's merkle_root
        assert tree.root == expected_root

        # Verify the inclusion proof using the static verifier
        # We need the original leaf data — rebuild gives us the tree,
        # and we can get the leaf data from the audit log entries
        import json as json_mod
        from anip_flight_demo.data.database import get_connection
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM audit_log WHERE sequence_number = 1"
        ).fetchone()
        assert row is not None
        entry = dict(row)
        for field in ("parameters", "result_summary", "cost_actual", "delegation_chain"):
            if entry[field]:
                entry[field] = json_mod.loads(entry[field])
        entry["success"] = bool(entry["success"])
        canonical = json_mod.dumps(
            {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

        verified = MerkleTree.verify_inclusion_static(canonical, proof_path, expected_root)
        assert verified, "Inclusion proof failed to verify against checkpoint merkle_root"

    def test_checkpoint_not_found_returns_404(self, service):
        """GET /anip/checkpoints/{id} with a nonexistent id returns 404."""
        resp = service.get("/anip/checkpoints/nonexistent-id")
        assert resp.status_code == 404

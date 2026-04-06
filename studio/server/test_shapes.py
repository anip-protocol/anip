"""Tests for shape CRUD, integrity validation, and contract expectation derivation."""

import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")

from studio.server.derivation import build_shape_backed_proposal


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _seed_project(client, pid):
    """Create a project with a requirements set and scenario."""
    client.post("/api/projects", json={"id": pid, "name": f"Project {pid}"})
    client.post(f"/api/projects/{pid}/requirements", json={
        "id": f"req-{pid}",
        "title": "Requirements",
        "data": {"system": {"name": "test"}},
    })
    client.post(f"/api/projects/{pid}/scenarios", json={
        "id": f"scn-{pid}",
        "title": "Scenario",
        "data": {"scenario": {"name": "test"}},
    })


def _valid_single_shape_data():
    """Minimal valid single_service shape data."""
    return {
        "shape": {
            "id": "shp-1",
            "name": "Order Service",
            "type": "single_service",
            "services": [
                {
                    "id": "svc-order",
                    "name": "Order Service",
                    "role": "processes customer orders",
                    "capabilities": ["receive order", "validate order"],
                }
            ],
            "domain_concepts": [
                {
                    "id": "concept-order",
                    "name": "Order",
                    "meaning": "A customer purchase request",
                    "owner": "svc-order",
                    "sensitivity": "none",
                }
            ],
        }
    }


def _valid_multi_shape_data():
    """Valid multi_service shape with coordination and concepts."""
    return {
        "shape": {
            "id": "shp-multi",
            "name": "Checkout Flow",
            "type": "multi_service",
            "services": [
                {
                    "id": "svc-cart",
                    "name": "Cart Service",
                    "role": "manages shopping cart",
                    "capabilities": ["add item", "remove item"],
                    "owns_concepts": ["concept-cart"],
                },
                {
                    "id": "svc-payment",
                    "name": "Payment Service",
                    "role": "handles payment processing",
                    "capabilities": ["purchase item", "refund"],
                    "owns_concepts": ["concept-payment"],
                },
            ],
            "coordination": [
                {
                    "from": "svc-cart",
                    "to": "svc-payment",
                    "relationship": "handoff",
                    "description": "Cart hands off to payment on checkout",
                }
            ],
            "domain_concepts": [
                {
                    "id": "concept-cart",
                    "name": "Cart",
                    "meaning": "Items selected for purchase",
                    "owner": "svc-cart",
                    "sensitivity": "none",
                },
                {
                    "id": "concept-payment",
                    "name": "Payment",
                    "meaning": "Financial transaction record",
                    "owner": "svc-payment",
                    "sensitivity": "medium",
                },
            ],
        }
    }


# ---------------------------------------------------------------------------
# Test 1: Create shape with valid services and concepts → 201
# ---------------------------------------------------------------------------

def test_create_shape_valid_single_service(client):
    """Create a valid single_service shape returns 201 with shape fields."""
    _seed_project(client, "proj-shp-ok")
    resp = client.post("/api/projects/proj-shp-ok/shapes", json={
        "id": "shp-single-ok",
        "title": "Single Service Shape",
        "requirements_id": "req-proj-shp-ok",
        "data": _valid_single_shape_data(),
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "shp-single-ok"
    assert data["requirements_id"] == "req-proj-shp-ok"
    assert data["content_hash"] != ""
    assert data["status"] == "draft"


# ---------------------------------------------------------------------------
# Test 2: Create shape with broken coordination edge → 422
# ---------------------------------------------------------------------------

def test_create_shape_broken_coordination_edge_returns_422(client):
    """Coordination edge referencing a nonexistent service ID → 422."""
    _seed_project(client, "proj-shp-coord")
    bad_data = {
        "shape": {
            "id": "shp-bad-coord",
            "name": "Bad Coordination",
            "type": "multi_service",
            "services": [
                {"id": "svc-a", "name": "Service A", "role": "does A"},
                {"id": "svc-b", "name": "Service B", "role": "does B"},
            ],
            "coordination": [
                {
                    "from": "svc-a",
                    "to": "svc-NONEXISTENT",  # bogus service ID
                    "relationship": "handoff",
                }
            ],
        }
    }
    resp = client.post("/api/projects/proj-shp-coord/shapes", json={
        "id": "shp-bad-coord",
        "title": "Bad Coordination Shape",
        "requirements_id": "req-proj-shp-coord",
        "data": bad_data,
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "svc-NONEXISTENT" in str(detail)


# ---------------------------------------------------------------------------
# Test 3: Create shape with broken owns_concepts → 422
# ---------------------------------------------------------------------------

def test_create_shape_broken_owns_concepts_returns_422(client):
    """owns_concepts referencing a nonexistent concept ID → 422."""
    _seed_project(client, "proj-shp-owns")
    bad_data = {
        "shape": {
            "id": "shp-bad-owns",
            "name": "Bad Owns",
            "type": "single_service",
            "services": [
                {
                    "id": "svc-x",
                    "name": "Service X",
                    "role": "does X",
                    "owns_concepts": ["concept-NONEXISTENT"],  # no such concept
                }
            ],
        }
    }
    resp = client.post("/api/projects/proj-shp-owns/shapes", json={
        "id": "shp-bad-owns",
        "title": "Bad Owns Shape",
        "requirements_id": "req-proj-shp-owns",
        "data": bad_data,
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "concept-NONEXISTENT" in str(detail)


# ---------------------------------------------------------------------------
# Test 4: Create shape with broken domain_concept owner → 422
# ---------------------------------------------------------------------------

def test_create_shape_broken_concept_owner_returns_422(client):
    """domain_concepts owner that is not a service ID or 'shared' → 422."""
    _seed_project(client, "proj-shp-owner")
    bad_data = {
        "shape": {
            "id": "shp-bad-owner",
            "name": "Bad Owner",
            "type": "single_service",
            "services": [
                {"id": "svc-real", "name": "Real Service", "role": "real role"}
            ],
            "domain_concepts": [
                {
                    "id": "concept-owned",
                    "name": "Owned Concept",
                    "meaning": "some concept",
                    "owner": "svc-BOGUS",  # not a real service ID
                }
            ],
        }
    }
    resp = client.post("/api/projects/proj-shp-owner/shapes", json={
        "id": "shp-bad-owner",
        "title": "Bad Owner Shape",
        "requirements_id": "req-proj-shp-owner",
        "data": bad_data,
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "svc-BOGUS" in str(detail)


# ---------------------------------------------------------------------------
# Test 5: Create shape with duplicate service IDs → 422
# ---------------------------------------------------------------------------

def test_create_shape_duplicate_service_ids_returns_422(client):
    """Shape with two services sharing the same ID → 422."""
    _seed_project(client, "proj-shp-dup")
    bad_data = {
        "shape": {
            "id": "shp-dup",
            "name": "Duplicate Services",
            "type": "multi_service",
            "services": [
                {"id": "svc-dup", "name": "Service One", "role": "does one"},
                {"id": "svc-dup", "name": "Service Two", "role": "does two"},  # duplicate
            ],
        }
    }
    resp = client.post("/api/projects/proj-shp-dup/shapes", json={
        "id": "shp-dup",
        "title": "Duplicate Services Shape",
        "requirements_id": "req-proj-shp-dup",
        "data": bad_data,
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "svc-dup" in str(detail)


# ---------------------------------------------------------------------------
# Test 6: single_service shape with 2 services → 422
# ---------------------------------------------------------------------------

def test_create_single_service_shape_with_two_services_returns_422(client):
    """single_service type must have exactly 1 service; 2 services → 422."""
    _seed_project(client, "proj-shp-single2")
    bad_data = {
        "shape": {
            "id": "shp-single2",
            "name": "Wrong Cardinality",
            "type": "single_service",
            "services": [
                {"id": "svc-1", "name": "Service 1", "role": "role 1"},
                {"id": "svc-2", "name": "Service 2", "role": "role 2"},
            ],
        }
    }
    resp = client.post("/api/projects/proj-shp-single2/shapes", json={
        "id": "shp-single2",
        "title": "Single with Two Services",
        "requirements_id": "req-proj-shp-single2",
        "data": bad_data,
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "single_service" in str(detail)


# ---------------------------------------------------------------------------
# Test 7: multi_service shape with 1 service → 422
# ---------------------------------------------------------------------------

def test_create_multi_service_shape_with_one_service_returns_422(client):
    """multi_service type must have at least 2 services; 1 service → 422."""
    _seed_project(client, "proj-shp-multi1")
    bad_data = {
        "shape": {
            "id": "shp-multi1",
            "name": "Wrong Multi Cardinality",
            "type": "multi_service",
            "services": [
                {"id": "svc-only", "name": "Only Service", "role": "lonely"},
            ],
        }
    }
    resp = client.post("/api/projects/proj-shp-multi1/shapes", json={
        "id": "shp-multi1",
        "title": "Multi with One Service",
        "requirements_id": "req-proj-shp-multi1",
        "data": bad_data,
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "multi_service" in str(detail)


# ---------------------------------------------------------------------------
# Test 8: Update shape data → content_hash changes
# ---------------------------------------------------------------------------

def test_update_shape_data_changes_content_hash(client):
    """Updating a shape's data causes the content_hash to change."""
    _seed_project(client, "proj-shp-upd")
    create_resp = client.post("/api/projects/proj-shp-upd/shapes", json={
        "id": "shp-upd",
        "title": "Shape for Update",
        "requirements_id": "req-proj-shp-upd",
        "data": _valid_single_shape_data(),
    })
    assert create_resp.status_code == 201, create_resp.text
    original_hash = create_resp.json()["content_hash"]

    # Update with different data (add a note)
    new_data = _valid_single_shape_data()
    new_data["shape"]["notes"] = ["added a rationale note"]
    update_resp = client.put("/api/projects/proj-shp-upd/shapes/shp-upd", json={
        "data": new_data,
    })
    assert update_resp.status_code == 200, update_resp.text
    new_hash = update_resp.json()["content_hash"]
    assert new_hash != original_hash, "content_hash must change when data changes"


# ---------------------------------------------------------------------------
# Test 9: Delete shape blocked by evaluation → 409
# ---------------------------------------------------------------------------

def test_delete_shape_blocked_by_evaluation_returns_409(client):
    """Cannot delete a shape that is referenced by an evaluation."""
    _seed_project(client, "proj-shp-del-block")
    # Create the shape
    client.post("/api/projects/proj-shp-del-block/shapes", json={
        "id": "shp-del-block",
        "title": "Shape to Block Delete",
        "requirements_id": "req-proj-shp-del-block",
        "data": _valid_single_shape_data(),
    })
    # Create an evaluation referencing the shape (no proposal_id needed)
    resp = client.post("/api/projects/proj-shp-del-block/evaluations", json={
        "id": "eval-shp-del-block",
        "shape_id": "shp-del-block",
        "scenario_id": "scn-proj-shp-del-block",
        "requirements_id": "req-proj-shp-del-block",
        "source": "manual",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {},
    })
    assert resp.status_code == 201, resp.text

    # Now try to delete the shape — should be blocked
    del_resp = client.delete("/api/projects/proj-shp-del-block/shapes/shp-del-block")
    assert del_resp.status_code == 409, del_resp.text
    detail = del_resp.json()["detail"]
    assert "eval-shp-del-block" in detail["refs"]


# ---------------------------------------------------------------------------
# Test 10: List shapes returns all for project
# ---------------------------------------------------------------------------

def test_list_shapes_returns_all_for_project(client):
    """Listing shapes returns all shapes belonging to the given project."""
    _seed_project(client, "proj-shp-list")
    # Create two shapes
    client.post("/api/projects/proj-shp-list/shapes", json={
        "id": "shp-list-1",
        "title": "Shape One",
        "requirements_id": "req-proj-shp-list",
        "data": _valid_single_shape_data(),
    })
    # Second shape needs different data (different shape ID inside data)
    data2 = _valid_single_shape_data()
    data2["shape"]["id"] = "shp-2-inner"
    client.post("/api/projects/proj-shp-list/shapes", json={
        "id": "shp-list-2",
        "title": "Shape Two",
        "requirements_id": "req-proj-shp-list",
        "data": data2,
    })

    resp = client.get("/api/projects/proj-shp-list/shapes")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    ids = [s["id"] for s in items]
    assert "shp-list-1" in ids
    assert "shp-list-2" in ids
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# Test 11: Create evaluation with shape_id (proposal_id optional/null) → 201
# ---------------------------------------------------------------------------

def test_create_evaluation_with_shape_id_no_proposal(client):
    """Evaluations can be created with shape_id and no proposal_id."""
    _seed_project(client, "proj-eval-shp")
    client.post("/api/projects/proj-eval-shp/shapes", json={
        "id": "shp-eval",
        "title": "Shape for Eval",
        "requirements_id": "req-proj-eval-shp",
        "data": _valid_single_shape_data(),
    })
    resp = client.post("/api/projects/proj-eval-shp/evaluations", json={
        "id": "eval-shp-only",
        "shape_id": "shp-eval",
        "scenario_id": "scn-proj-eval-shp",
        "requirements_id": "req-proj-eval-shp",
        "source": "manual",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {},
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["shape_id"] == "shp-eval"
    assert data["proposal_id"] is None


# ---------------------------------------------------------------------------
# Test 12: Derivation endpoint returns expectations for shape + requirements
# ---------------------------------------------------------------------------

def test_derivation_endpoint_returns_expectations(client):
    """The expectations endpoint returns a list of derived expectations."""
    _seed_project(client, "proj-derive-basic")
    # Create shape
    client.post("/api/projects/proj-derive-basic/shapes", json={
        "id": "shp-derive-basic",
        "title": "Basic Shape",
        "requirements_id": "req-proj-derive-basic",
        "data": _valid_single_shape_data(),
    })
    # Update requirements with some constraints to trigger derivation
    client.put("/api/projects/proj-derive-basic/requirements/req-proj-derive-basic", json={
        "data": {
            "business_constraints": {
                "spending_possible": True,
            }
        }
    })

    resp = client.get("/api/projects/proj-derive-basic/shapes/shp-derive-basic/expectations")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "expectations" in body
    assert isinstance(body["expectations"], list)
    surfaces = [e["surface"] for e in body["expectations"]]
    # spending_possible → budget_enforcement
    assert "budget_enforcement" in surfaces


# ---------------------------------------------------------------------------
# Test 13: Derivation: multi-service shape with coordination → cross_service_handoff
# ---------------------------------------------------------------------------

def test_derivation_multi_service_coordination_implies_cross_service_handoff(client):
    """Multi-service shape with coordination edges derives cross_service_handoff."""
    _seed_project(client, "proj-derive-multi")
    client.post("/api/projects/proj-derive-multi/shapes", json={
        "id": "shp-derive-multi",
        "title": "Multi Service Shape",
        "requirements_id": "req-proj-derive-multi",
        "data": _valid_multi_shape_data(),
    })

    resp = client.get("/api/projects/proj-derive-multi/shapes/shp-derive-multi/expectations")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    surfaces = [e["surface"] for e in body["expectations"]]
    assert "cross_service_handoff" in surfaces
    assert "cross_service_continuity" in surfaces


def test_build_shape_backed_proposal_includes_v021_contracts():
    requirements = {
        "audit": {"durable": True, "searchable": True},
        "lineage": {"task_id": True, "parent_invocation_id": True},
        "business_constraints": {"approval_expected_for_high_risk": True},
        "scale": {"shape_preference": "multi_service_estate"},
    }
    shape_data = {
        "shape": {
            "id": "shp-v021",
            "name": "Checkout Flow",
            "type": "multi_service",
            "services": [
                {
                    "id": "svc-cart",
                    "name": "Cart Service",
                    "role": "cart",
                    "capabilities": ["handle_checkout"],
                },
                {
                    "id": "approval-service",
                    "name": "Approval Service",
                    "role": "approval",
                    "capabilities": ["request_approval"],
                },
                {
                    "id": "verification-service",
                    "name": "Verification Service",
                    "role": "verify",
                    "capabilities": ["verify_outcome"],
                },
                {
                    "id": "revalidation-service",
                    "name": "Revalidation Service",
                    "role": "refresh",
                    "capabilities": ["refresh_input"],
                },
            ],
            "coordination": [
                {"from": "svc-cart", "to": "approval-service", "relationship": "handoff"},
                {"from": "svc-cart", "to": "verification-service", "relationship": "verification"},
                {"from": "svc-cart", "to": "revalidation-service", "relationship": "refresh"},
            ],
        }
    }

    proposal = build_shape_backed_proposal(shape_data, requirements)["proposal"]
    assert proposal["cross_service_contract"]["handoff"][0]["target"]["service"] == "approval-service"
    assert proposal["cross_service_contract"]["verification"][0]["completion_mode"] == "verification_result"
    assert proposal["recovery_target"]["kind"] == "refresh"
    assert proposal["recovery_target"]["target"]["service"] == "revalidation-service"


# ---------------------------------------------------------------------------
# Test 14: Derivation: spending_possible + cost-bearing capability → budget_enforcement
# ---------------------------------------------------------------------------

def test_derivation_spending_possible_with_cost_bearing_capability(client):
    """spending_possible requirement + cost-bearing capability → budget_enforcement."""
    _seed_project(client, "proj-derive-budget")
    shape_data = {
        "shape": {
            "id": "shp-budget",
            "name": "Booking Service",
            "type": "single_service",
            "services": [
                {
                    "id": "svc-booking",
                    "name": "Booking Service",
                    "role": "books travel",
                    "capabilities": ["book flight", "book hotel"],  # contains "book"
                }
            ],
        }
    }
    client.post("/api/projects/proj-derive-budget/shapes", json={
        "id": "shp-derive-budget",
        "title": "Booking Shape",
        "requirements_id": "req-proj-derive-budget",
        "data": shape_data,
    })
    # Set spending_possible on requirements
    client.put("/api/projects/proj-derive-budget/requirements/req-proj-derive-budget", json={
        "data": {
            "business_constraints": {
                "spending_possible": True,
            }
        }
    })

    resp = client.get("/api/projects/proj-derive-budget/shapes/shp-derive-budget/expectations")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    surfaces = [e["surface"] for e in body["expectations"]]
    assert "budget_enforcement" in surfaces
    # The reason should mention both spending AND cost-bearing capability
    budget_entry = next(e for e in body["expectations"] if e["surface"] == "budget_enforcement")
    assert "cost-bearing" in budget_entry["reason"]


# ---------------------------------------------------------------------------
# Test 15: Derivation: high-sensitivity concept → authority_posture
# ---------------------------------------------------------------------------

def test_derivation_high_sensitivity_concept_implies_authority_posture(client):
    """A shape with a high-sensitivity domain concept derives authority_posture."""
    _seed_project(client, "proj-derive-auth")
    shape_data = {
        "shape": {
            "id": "shp-auth",
            "name": "Payment Shape",
            "type": "single_service",
            "services": [
                {"id": "svc-pay", "name": "Payment Service", "role": "handles payments"}
            ],
            "domain_concepts": [
                {
                    "id": "concept-pii",
                    "name": "Customer PII",
                    "meaning": "Personally identifiable information",
                    "owner": "svc-pay",
                    "sensitivity": "high",  # triggers authority_posture
                }
            ],
        }
    }
    client.post("/api/projects/proj-derive-auth/shapes", json={
        "id": "shp-derive-auth",
        "title": "Auth Shape",
        "requirements_id": "req-proj-derive-auth",
        "data": shape_data,
    })

    resp = client.get("/api/projects/proj-derive-auth/shapes/shp-derive-auth/expectations")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    surfaces = [e["surface"] for e in body["expectations"]]
    assert "authority_posture" in surfaces
    auth_entry = next(e for e in body["expectations"] if e["surface"] == "authority_posture")
    assert "Customer PII" in auth_entry["reason"]

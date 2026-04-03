"""Tests for artifact CRUD, referential integrity, and project coherence."""

import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_project(client, pid="proj-art"):
    """Create a project with a requirements set and scenario for reuse."""
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


# ---------------------------------------------------------------------------
# Requirements CRUD
# ---------------------------------------------------------------------------

def test_create_and_list_requirements(client):
    _seed_project(client, "proj-req-crud")
    resp = client.get("/api/projects/proj-req-crud/requirements")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == "req-proj-req-crud"


def test_get_requirements(client):
    _seed_project(client, "proj-req-get")
    resp = client.get("/api/projects/proj-req-get/requirements/req-proj-req-get")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Requirements"


def test_update_requirements(client):
    _seed_project(client, "proj-req-upd")
    resp = client.put("/api/projects/proj-req-upd/requirements/req-proj-req-upd", json={
        "title": "Updated Reqs",
        "status": "active",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated Reqs"
    assert data["status"] == "active"


# ---------------------------------------------------------------------------
# Scenarios CRUD
# ---------------------------------------------------------------------------

def test_create_and_list_scenarios(client):
    _seed_project(client, "proj-scn-crud")
    resp = client.get("/api/projects/proj-scn-crud/scenarios")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == "scn-proj-scn-crud"


def test_update_scenario(client):
    _seed_project(client, "proj-scn-upd")
    resp = client.put("/api/projects/proj-scn-upd/scenarios/scn-proj-scn-upd", json={
        "title": "Updated Scenario",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Scenario"


# ---------------------------------------------------------------------------
# Proposals with project coherence
# ---------------------------------------------------------------------------

def test_create_proposal_with_valid_requirements_id(client):
    _seed_project(client, "proj-prop-ok")
    resp = client.post("/api/projects/proj-prop-ok/proposals", json={
        "id": "prop-ok",
        "title": "Valid Proposal",
        "requirements_id": "req-proj-prop-ok",
        "data": {"proposal": {"name": "test"}},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["requirements_id"] == "req-proj-prop-ok"


def test_create_proposal_cross_project_ref_returns_422(client):
    """A proposal's requirements_id must belong to the same project."""
    _seed_project(client, "proj-a")
    _seed_project(client, "proj-b")
    # Try to create a proposal in proj-b referencing requirements from proj-a
    resp = client.post("/api/projects/proj-b/proposals", json={
        "id": "prop-cross",
        "title": "Cross-project proposal",
        "requirements_id": "req-proj-a",  # belongs to proj-a, not proj-b
        "data": {},
    })
    assert resp.status_code == 422


def test_delete_requirements_blocked_by_proposal_returns_409(client):
    """Cannot delete requirements when a proposal references them."""
    _seed_project(client, "proj-del-block")
    client.post("/api/projects/proj-del-block/proposals", json={
        "id": "prop-block",
        "title": "Blocking Proposal",
        "requirements_id": "req-proj-del-block",
        "data": {},
    })
    resp = client.delete("/api/projects/proj-del-block/requirements/req-proj-del-block")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "prop-block" in detail["refs"]


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

def test_create_evaluation_with_all_refs(client):
    """Create an evaluation referencing proposal, scenario, and requirements."""
    _seed_project(client, "proj-eval")
    client.post("/api/projects/proj-eval/proposals", json={
        "id": "prop-eval",
        "title": "Proposal for eval",
        "requirements_id": "req-proj-eval",
        "data": {},
    })
    resp = client.post("/api/projects/proj-eval/evaluations", json={
        "id": "eval-1",
        "proposal_id": "prop-eval",
        "scenario_id": "scn-proj-eval",
        "requirements_id": "req-proj-eval",
        "source": "live_validation",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {"requirements": {}, "proposal": {}, "scenario": {}},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["proposal_id"] == "prop-eval"
    assert data["scenario_id"] == "scn-proj-eval"
    assert data["requirements_id"] == "req-proj-eval"


def test_create_evaluation_cross_project_ref_returns_422(client):
    """Evaluation refs must all belong to the same project."""
    _seed_project(client, "proj-eval-a")
    _seed_project(client, "proj-eval-b")
    client.post("/api/projects/proj-eval-a/proposals", json={
        "id": "prop-eval-a",
        "title": "Proposal A",
        "requirements_id": "req-proj-eval-a",
        "data": {},
    })
    # Try creating an evaluation in proj-eval-b referencing proposal from proj-eval-a
    resp = client.post("/api/projects/proj-eval-b/evaluations", json={
        "id": "eval-cross",
        "proposal_id": "prop-eval-a",
        "scenario_id": "scn-proj-eval-b",
        "requirements_id": "req-proj-eval-b",
        "source": "manual",
        "data": {"evaluation": {"result": "PARTIAL"}},
        "input_snapshot": {},
    })
    assert resp.status_code == 422


def test_delete_evaluation_succeeds_leaf_node(client):
    """Evaluations are leaf nodes and can always be deleted."""
    _seed_project(client, "proj-eval-del")
    client.post("/api/projects/proj-eval-del/proposals", json={
        "id": "prop-eval-del",
        "title": "Proposal",
        "requirements_id": "req-proj-eval-del",
        "data": {},
    })
    client.post("/api/projects/proj-eval-del/evaluations", json={
        "id": "eval-leaf",
        "proposal_id": "prop-eval-del",
        "scenario_id": "scn-proj-eval-del",
        "requirements_id": "req-proj-eval-del",
        "source": "manual",
        "data": {"evaluation": {"result": "REQUIRES_GLUE"}},
        "input_snapshot": {},
    })
    resp = client.delete("/api/projects/proj-eval-del/evaluations/eval-leaf")
    assert resp.status_code == 204

    # Verify gone
    resp = client.get("/api/projects/proj-eval-del/evaluations/eval-leaf")
    assert resp.status_code == 404


def test_delete_scenario_blocked_by_evaluation_returns_409(client):
    """Cannot delete a scenario when an evaluation references it."""
    _seed_project(client, "proj-scn-block")
    client.post("/api/projects/proj-scn-block/proposals", json={
        "id": "prop-scn-block",
        "title": "Proposal",
        "requirements_id": "req-proj-scn-block",
        "data": {},
    })
    client.post("/api/projects/proj-scn-block/evaluations", json={
        "id": "eval-scn-block",
        "proposal_id": "prop-scn-block",
        "scenario_id": "scn-proj-scn-block",
        "requirements_id": "req-proj-scn-block",
        "source": "manual",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {},
    })
    resp = client.delete("/api/projects/proj-scn-block/scenarios/scn-proj-scn-block")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "eval-scn-block" in detail["refs"]


def test_evaluation_has_input_snapshot_and_source(client):
    """Verify evaluation response includes input_snapshot and source fields."""
    _seed_project(client, "proj-eval-fields")
    client.post("/api/projects/proj-eval-fields/proposals", json={
        "id": "prop-eval-fields",
        "title": "Proposal",
        "requirements_id": "req-proj-eval-fields",
        "data": {},
    })
    snapshot = {"requirements": {"x": 1}, "proposal": {"y": 2}, "scenario": {"z": 3}}
    client.post("/api/projects/proj-eval-fields/evaluations", json={
        "id": "eval-fields",
        "proposal_id": "prop-eval-fields",
        "scenario_id": "scn-proj-eval-fields",
        "requirements_id": "req-proj-eval-fields",
        "source": "live_validation",
        "data": {"evaluation": {"result": "PARTIAL"}},
        "input_snapshot": snapshot,
    })
    resp = client.get("/api/projects/proj-eval-fields/evaluations/eval-fields")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "live_validation"
    assert data["input_snapshot"] == snapshot

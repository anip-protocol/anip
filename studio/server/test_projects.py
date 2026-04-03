"""Tests for project CRUD API endpoints."""

import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


def test_list_projects_empty(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_project(client):
    body = {
        "id": "proj-1",
        "name": "Test Project",
        "summary": "A test project",
        "domain": "testing",
        "labels": ["test", "v1"],
    }
    resp = client.post("/api/projects", json=body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "proj-1"
    assert data["name"] == "Test Project"
    assert data["summary"] == "A test project"
    assert data["domain"] == "testing"
    assert data["labels"] == ["test", "v1"]
    assert "created_at" in data
    assert "updated_at" in data


def test_get_project_with_artifact_counts(client):
    # Create a project first
    client.post("/api/projects", json={
        "id": "proj-counts",
        "name": "Counts Project",
    })
    resp = client.get("/api/projects/proj-counts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "proj-counts"
    assert data["requirements_count"] == 0
    assert data["scenarios_count"] == 0
    assert data["proposals_count"] == 0
    assert data["evaluations_count"] == 0


def test_update_project(client):
    client.post("/api/projects", json={
        "id": "proj-upd",
        "name": "Original Name",
    })
    resp = client.put("/api/projects/proj-upd", json={
        "name": "Updated Name",
        "summary": "Updated summary",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["summary"] == "Updated summary"


def test_duplicate_project_id_returns_409(client):
    client.post("/api/projects", json={
        "id": "proj-dup",
        "name": "First",
    })
    resp = client.post("/api/projects", json={
        "id": "proj-dup",
        "name": "Second",
    })
    assert resp.status_code == 409


def test_missing_project_returns_404(client):
    resp = client.get("/api/projects/nonexistent-project")
    assert resp.status_code == 404


def test_delete_project_cascades_all_children(client):
    # Create a project with full artifact graph
    client.post("/api/projects", json={
        "id": "proj-del",
        "name": "Delete Me",
    })
    client.post("/api/projects/proj-del/requirements", json={
        "id": "req-del",
        "title": "Reqs",
        "data": {"system": {"name": "test"}},
    })
    client.post("/api/projects/proj-del/scenarios", json={
        "id": "scn-del",
        "title": "Scenario",
        "data": {"scenario": {"name": "test"}},
    })
    client.post("/api/projects/proj-del/proposals", json={
        "id": "prop-del",
        "title": "Proposal",
        "requirements_id": "req-del",
        "data": {"proposal": {"name": "test"}},
    })
    client.post("/api/projects/proj-del/evaluations", json={
        "id": "eval-del",
        "proposal_id": "prop-del",
        "scenario_id": "scn-del",
        "requirements_id": "req-del",
        "source": "manual",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {},
    })

    # Verify everything exists
    assert client.get("/api/projects/proj-del").status_code == 200
    assert client.get("/api/projects/proj-del/requirements/req-del").status_code == 200
    assert client.get("/api/projects/proj-del/scenarios/scn-del").status_code == 200
    assert client.get("/api/projects/proj-del/proposals/prop-del").status_code == 200
    assert client.get("/api/projects/proj-del/evaluations/eval-del").status_code == 200

    # Delete the project
    resp = client.delete("/api/projects/proj-del")
    assert resp.status_code == 204

    # Verify everything is gone
    assert client.get("/api/projects/proj-del").status_code == 404
    assert client.get("/api/projects/proj-del/requirements/req-del").status_code == 404
    assert client.get("/api/projects/proj-del/scenarios/scn-del").status_code == 404
    assert client.get("/api/projects/proj-del/proposals/prop-del").status_code == 404
    assert client.get("/api/projects/proj-del/evaluations/eval-del").status_code == 404

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


def test_clone_project_copies_artifacts(client):
    client.post(
        "/api/workspaces",
        json={"id": "ws-clone", "name": "Clone Workspace"},
    )
    client.post(
        "/api/projects",
        json={
            "id": "proj-source",
            "workspace_id": "ws-clone",
            "name": "Source Project",
            "summary": "Original summary",
            "domain": "sales",
            "labels": ["alpha"],
        },
    )
    client.post(
        "/api/projects/proj-source/requirements",
        json={
            "id": "req-source",
            "title": "Requirements",
            "data": {"system": {"name": "Source System"}},
        },
    )
    client.post(
        "/api/projects/proj-source/scenarios",
        json={
            "id": "scn-source",
            "title": "Scenario",
            "data": {"scenario": {"name": "Scenario One"}},
        },
    )
    client.post(
        "/api/projects/proj-source/pm-artifacts",
        json={
            "id": "pm-source",
            "title": "PM Artifact",
            "data": {
                "artifact_type": "design_traceability",
                "source_inputs": {
                    "requirements_id": "req-source",
                    "scenario_ids": ["scn-source"],
                },
                "coverage": [
                    {
                        "id": "scenario:scn-source:context-capability",
                        "label": "What capability or action is being attempted?",
                        "status": "addressed",
                        "mapping_mode": "automatic",
                        "mapping_target_key": "developer_definition.scenario_formalization:scn-source:primary_capability",
                    }
                ],
                "embedded_refs": "artifact:pm-source|project:proj-source",
            },
        },
    )

    cloned = client.post(
        "/api/projects/proj-source/clone",
        json={
            "id": "proj-clone",
            "workspace_id": "ws-clone",
            "name": "Cloned Project",
            "summary": "Cloned summary",
        },
    )
    assert cloned.status_code == 201, cloned.text
    clone_row = cloned.json()
    assert clone_row["id"] == "proj-clone"
    assert clone_row["name"] == "Cloned Project"
    assert clone_row["workspace_id"] == "ws-clone"
    assert clone_row["summary"] == "Cloned summary"

    clone_detail = client.get("/api/projects/proj-clone")
    assert clone_detail.status_code == 200
    detail = clone_detail.json()
    assert detail["requirements_count"] == 1
    assert detail["scenarios_count"] == 1
    assert detail["pm_artifacts_count"] == 1

    cloned_requirements = client.get("/api/projects/proj-clone/requirements")
    assert cloned_requirements.status_code == 200
    requirement_rows = cloned_requirements.json()
    assert len(requirement_rows) == 1
    assert requirement_rows[0]["id"] != "req-source"
    assert requirement_rows[0]["data"]["system"]["name"] == "Source System"

    cloned_artifacts = client.get("/api/projects/proj-clone/pm-artifacts")
    assert cloned_artifacts.status_code == 200
    artifact = next(item for item in cloned_artifacts.json() if item["title"] == "PM Artifact")
    cloned_scenarios = client.get("/api/projects/proj-clone/scenarios").json()
    cloned_scenario_id = cloned_scenarios[0]["id"]
    cloned_coverage = artifact["data"]["coverage"][0]
    assert cloned_scenario_id != "scn-source"
    assert cloned_coverage["id"] == f"scenario:{cloned_scenario_id}:context-capability"
    assert cloned_coverage["mapping_target_key"] == (
        f"developer_definition.scenario_formalization:{cloned_scenario_id}:primary_capability"
    )
    assert "pm-source" not in artifact["data"]["embedded_refs"]
    assert "proj-source" not in artifact["data"]["embedded_refs"]
    assert artifact["id"] in artifact["data"]["embedded_refs"]
    assert "proj-clone" in artifact["data"]["embedded_refs"]

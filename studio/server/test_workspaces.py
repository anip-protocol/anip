"""Tests for workspace CRUD and workspace-scoped project listing."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


def test_workspaces_exist_and_can_be_created(client):
    resp = client.get("/api/workspaces")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    body = {
        "id": "ws-1",
        "name": "Platform Workspace",
        "summary": "Shared platform design work",
    }
    resp = client.post("/api/workspaces", json=body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "ws-1"
    assert data["name"] == "Platform Workspace"

    resp = client.get("/api/workspaces/ws-1")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["projects_count"] == 0


def test_projects_can_be_scoped_to_workspace(client):
    client.post("/api/workspaces", json={
        "id": "ws-a",
        "name": "Workspace A",
    })
    client.post("/api/workspaces", json={
        "id": "ws-b",
        "name": "Workspace B",
    })

    client.post("/api/projects", json={
        "id": "proj-a1",
        "workspace_id": "ws-a",
        "name": "Project A1",
    })
    client.post("/api/projects", json={
        "id": "proj-b1",
        "workspace_id": "ws-b",
        "name": "Project B1",
    })

    resp = client.get("/api/projects?workspace_id=ws-a")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "proj-a1"
    assert data[0]["workspace_id"] == "ws-a"

    resp = client.get("/api/workspaces/ws-a")
    assert resp.status_code == 200
    assert resp.json()["projects_count"] == 1

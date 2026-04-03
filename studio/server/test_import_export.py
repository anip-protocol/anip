"""Tests for seed, export, and import operations."""

import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


def test_seed_creates_projects(client):
    """Seeding from example packs creates one project per pack."""
    resp = client.post("/api/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_projects"] > 0


def test_seed_is_idempotent(client):
    """Running seed again does not create duplicates."""
    resp1 = client.post("/api/seed")
    first = resp1.json()

    resp2 = client.post("/api/seed")
    second = resp2.json()
    assert second["created_projects"] == 0
    assert second["skipped"] == first["created_projects"] + first["skipped"]


def test_export_returns_full_project_graph(client):
    """Export returns the project plus all artifact collections."""
    # Seed first to have data
    client.post("/api/seed")

    # List projects and pick the first one
    projects = client.get("/api/projects").json()
    assert len(projects) > 0
    pid = projects[0]["id"]

    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    # Should have the project and all artifact arrays
    assert "project" in data
    assert data["project"]["id"] == pid
    assert "requirements" in data
    assert "scenarios" in data
    assert "proposals" in data
    assert "evaluations" in data
    # Seeded projects should have at least one of each
    assert len(data["requirements"]) >= 1
    assert len(data["scenarios"]) >= 1
    assert len(data["proposals"]) >= 1
    assert len(data["evaluations"]) >= 1


def test_import_artifacts_into_project(client):
    """Import requirements and scenarios into an existing project."""
    client.post("/api/projects", json={
        "id": "proj-import",
        "name": "Import Target",
    })
    resp = client.post("/api/projects/proj-import/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "imp-req-1",
                    "title": "Imported Reqs",
                    "data": {"system": {"name": "imported"}},
                },
            },
            {
                "type": "scenario",
                "data": {
                    "id": "imp-scn-1",
                    "title": "Imported Scenario",
                    "data": {"scenario": {"name": "imported"}},
                },
            },
            {
                "type": "proposal",
                "data": {
                    "id": "imp-prop-1",
                    "title": "Imported Proposal",
                    "requirements_id": "imp-req-1",
                    "data": {"proposal": {"name": "imported"}},
                },
            },
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 3
    assert data["errors"] == []

    # Verify the imported artifacts exist
    reqs = client.get("/api/projects/proj-import/requirements").json()
    assert any(r["id"] == "imp-req-1" for r in reqs)
    scenarios = client.get("/api/projects/proj-import/scenarios").json()
    assert any(s["id"] == "imp-scn-1" for s in scenarios)
    proposals = client.get("/api/projects/proj-import/proposals").json()
    assert any(p["id"] == "imp-prop-1" for p in proposals)

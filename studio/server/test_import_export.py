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


def test_export_includes_content_hash_on_artifacts(client):
    """Export includes content_hash on every artifact record."""
    client.post("/api/seed")
    projects = client.get("/api/projects").json()
    pid = projects[0]["id"]

    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    for req in data["requirements"]:
        assert "content_hash" in req, "requirements should have content_hash"
        assert len(req["content_hash"]) == 64, "content_hash should be SHA-256 hex"

    for scn in data["scenarios"]:
        assert "content_hash" in scn, "scenarios should have content_hash"
        assert len(scn["content_hash"]) == 64

    for prop in data["proposals"]:
        assert "content_hash" in prop, "proposals should have content_hash"
        assert len(prop["content_hash"]) == 64


def test_export_includes_per_artifact_hashes_on_evaluations(client):
    """Export includes per-artifact hashes on evaluations (no is_stale)."""
    client.post("/api/seed")
    projects = client.get("/api/projects").json()
    pid = projects[0]["id"]

    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    for ev in data["evaluations"]:
        assert "requirements_hash" in ev, "evaluation should have requirements_hash"
        assert "proposal_hash" in ev, "evaluation should have proposal_hash"
        assert "scenario_hash" in ev, "evaluation should have scenario_hash"
        # is_stale must NOT be present — it's environment-relative
        assert "is_stale" not in ev, "export must NOT include is_stale"
        assert "stale_artifacts" not in ev, "export must NOT include stale_artifacts"


def test_export_includes_metadata(client):
    """Export includes a metadata section with export timestamp."""
    client.post("/api/seed")
    projects = client.get("/api/projects").json()
    pid = projects[0]["id"]

    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    assert "metadata" in data
    assert "exported_at" in data["metadata"]
    # Should be a valid ISO timestamp string
    from datetime import datetime
    ts = data["metadata"]["exported_at"]
    datetime.fromisoformat(ts)  # raises ValueError if invalid


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
                    "data": {
                        "system": {
                            "name": "imported",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                        "transports": {"http": True},
                        "trust": {"mode": "unsigned", "checkpoints": False},
                        "auth": {},
                        "permissions": {},
                        "audit": {},
                        "lineage": {},
                        "scale": {
                            "shape_preference": "production_single_service",
                            "high_availability": False
                        },
                    },
                },
            },
            {
                "type": "scenario",
                "data": {
                    "id": "imp-scn-1",
                    "title": "Imported Scenario",
                    "data": {
                        "scenario": {
                            "name": "test_scenario",
                            "category": "safety",
                            "narrative": "A test scenario",
                            "context": {"key": "value"},
                            "expected_behavior": ["behave correctly"],
                            "expected_anip_support": ["trust"],
                        }
                    },
                },
            },
            {
                "type": "proposal",
                "data": {
                    "id": "imp-prop-1",
                    "title": "Imported Proposal",
                    "requirements_id": "imp-req-1",
                    "data": {
                        "proposal": {
                            "recommended_shape": "production_single_service",
                            "rationale": ["test rationale"],
                            "required_components": ["component-a"],
                        }
                    },
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


def test_import_duplicate_id_rejected(client):
    """Importing an artifact with a duplicate ID is rejected with a clear error."""
    client.post("/api/projects", json={
        "id": "proj-dup-test",
        "name": "Duplicate Test Project",
    })

    # First import — creates the requirements set
    resp1 = client.post("/api/projects/proj-dup-test/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "dup-req-1",
                    "title": "Original Reqs",
                    "data": {
                        "system": {
                            "name": "original",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                        "transports": {},
                        "trust": {"mode": "unsigned", "checkpoints": False},
                        "auth": {},
                        "permissions": {},
                        "audit": {},
                        "lineage": {},
                        "scale": {
                            "shape_preference": "production_single_service",
                            "high_availability": False
                        },
                    },
                },
            },
        ],
    })
    assert resp1.status_code == 200
    assert resp1.json()["imported"] == 1

    # Second import — tries to use the same ID
    resp2 = client.post("/api/projects/proj-dup-test/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "dup-req-1",
                    "title": "Duplicate Reqs",
                    "data": {
                        "system": {
                            "name": "duplicate",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                        "transports": {},
                        "trust": {"mode": "unsigned", "checkpoints": False},
                        "auth": {},
                        "permissions": {},
                        "audit": {},
                        "lineage": {},
                        "scale": {
                            "shape_preference": "production_single_service",
                            "high_availability": False
                        },
                    },
                },
            },
        ],
    })
    assert resp2.status_code == 200
    result = resp2.json()
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "duplicate" in result["errors"][0].lower() or "dup-req-1" in result["errors"][0]


def test_import_proposal_with_missing_requirements_id_rejected(client):
    """Importing a proposal whose requirements_id does not exist is rejected."""
    client.post("/api/projects", json={
        "id": "proj-missing-req",
        "name": "Missing Req Test",
    })

    resp = client.post("/api/projects/proj-missing-req/import", json={
        "artifacts": [
            {
                "type": "proposal",
                "data": {
                    "id": "prop-orphan",
                    "title": "Orphan Proposal",
                    "requirements_id": "nonexistent-req-id",
                    "data": {
                        "proposal": {
                            "recommended_shape": "production_single_service",
                            "rationale": ["orphan"],
                            "required_components": ["x"],
                        }
                    },
                },
            },
        ],
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "nonexistent-req-id" in result["errors"][0] or "requirements_id" in result["errors"][0]


def test_import_schema_validation_rejects_invalid_artifact(client):
    """Schema validation rejects artifacts that do not conform to their schema."""
    client.post("/api/projects", json={
        "id": "proj-schema-val",
        "name": "Schema Validation Test",
    })

    # Missing required top-level fields in requirements data
    resp = client.post("/api/projects/proj-schema-val/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "bad-req-1",
                    "title": "Bad Requirements",
                    "data": {
                        # Missing required fields: transports, trust, auth, etc.
                        "system": {
                            "name": "minimal",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                    },
                },
            },
        ],
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "schema validation failed" in result["errors"][0]

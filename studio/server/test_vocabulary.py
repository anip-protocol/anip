"""Tests for vocabulary CRUD, merge, and global canonical entries."""

import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


def test_global_canonical_entries_seeded_on_startup(client):
    """The app lifespan loads vocabulary_defaults.json as global canonical entries."""
    resp = client.get("/api/vocabulary")
    assert resp.status_code == 200
    entries = resp.json()
    # vocabulary_defaults.json has 24 canonical entries
    assert len(entries) >= 20
    # All should be global (project_id is None) and canonical
    for entry in entries:
        assert entry["project_id"] is None
        assert entry["origin"] == "canonical"


def test_create_project_local_vocabulary_entry(client):
    """Create a vocabulary entry scoped to a project."""
    # Create a project first
    client.post("/api/projects", json={"id": "proj-vocab", "name": "Vocab Project"})
    resp = client.post("/api/vocabulary", json={
        "project_id": "proj-vocab",
        "category": "context_key",
        "value": "custom_field",
        "origin": "project",
        "description": "A project-local vocabulary entry",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == "proj-vocab"
    assert data["category"] == "context_key"
    assert data["value"] == "custom_field"
    assert data["origin"] == "project"


def test_merged_vocabulary_returns_global_and_project(client):
    """Querying with project_id returns both global and project-scoped entries."""
    client.post("/api/projects", json={"id": "proj-vocab-merge", "name": "Merge Project"})
    client.post("/api/vocabulary", json={
        "project_id": "proj-vocab-merge",
        "category": "behavior",
        "value": "custom_behavior",
        "origin": "project",
    })
    resp = client.get("/api/vocabulary", params={"project_id": "proj-vocab-merge"})
    assert resp.status_code == 200
    entries = resp.json()
    project_ids = {e["project_id"] for e in entries}
    # Should have both None (global) and the project ID
    assert None in project_ids
    assert "proj-vocab-merge" in project_ids


def test_delete_vocabulary_entry(client):
    """Delete a vocabulary entry by ID."""
    client.post("/api/projects", json={"id": "proj-vocab-del", "name": "Del Project"})
    create_resp = client.post("/api/vocabulary", json={
        "project_id": "proj-vocab-del",
        "category": "context_key",
        "value": "deletable_key",
        "origin": "custom",
    })
    vocab_id = create_resp.json()["id"]
    resp = client.delete(f"/api/vocabulary/{vocab_id}")
    assert resp.status_code == 204

    # Verify the entry is gone by checking the full list
    list_resp = client.get("/api/vocabulary", params={"project_id": "proj-vocab-del"})
    ids = [e["id"] for e in list_resp.json()]
    assert vocab_id not in ids


def test_duplicate_global_entry_is_rejected(client):
    """The partial unique index on (category, value) WHERE project_id IS NULL
    prevents duplicate global entries regardless of origin."""
    # Create a global entry (using 'custom' origin so cleanup can remove it)
    resp1 = client.post("/api/vocabulary", json={
        "category": "test_unique_category",
        "value": "test_unique_value",
        "origin": "custom",
    })
    assert resp1.status_code == 201

    # Try to create the same global entry again — should be rejected
    resp2 = client.post("/api/vocabulary", json={
        "category": "test_unique_category",
        "value": "test_unique_value",
        "origin": "custom",
    })
    assert resp2.status_code == 409

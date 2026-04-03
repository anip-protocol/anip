"""Tests for evaluation staleness detection.

Verifies that:
- A freshly created evaluation reports is_stale=false
- Updating a requirement makes the evaluation stale
- Updating the scenario makes the evaluation stale
- list_evaluations also returns staleness for each evaluation
- A new evaluation created after artifact updates is fresh (is_stale=false)
"""

import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")

import uuid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pid():
    """Return a short unique project ID."""
    return f"stale-{uuid.uuid4().hex[:8]}"


def _seed_full_project(client, pid):
    """Create project with requirements, scenario, proposal, and evaluation.

    Returns the evaluation response dict.
    """
    # Project
    r = client.post("/api/projects", json={"id": pid, "name": f"Project {pid}"})
    assert r.status_code == 201, r.text

    # Requirements
    req_id = f"req-{pid}"
    r = client.post(f"/api/projects/{pid}/requirements", json={
        "id": req_id,
        "title": "Requirements",
        "data": {"system": {"name": "original"}},
    })
    assert r.status_code == 201, r.text

    # Scenario
    scn_id = f"scn-{pid}"
    r = client.post(f"/api/projects/{pid}/scenarios", json={
        "id": scn_id,
        "title": "Scenario",
        "data": {"scenario": {"name": "original"}},
    })
    assert r.status_code == 201, r.text

    # Proposal
    prop_id = f"prop-{pid}"
    r = client.post(f"/api/projects/{pid}/proposals", json={
        "id": prop_id,
        "title": "Proposal",
        "requirements_id": req_id,
        "data": {"proposal": {"name": "original"}},
    })
    assert r.status_code == 201, r.text

    # Evaluation
    eval_id = f"eval-{pid}"
    r = client.post(f"/api/projects/{pid}/evaluations", json={
        "id": eval_id,
        "proposal_id": prop_id,
        "scenario_id": scn_id,
        "requirements_id": req_id,
        "source": "manual",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {},
    })
    assert r.status_code == 201, r.text
    return r.json(), pid, req_id, scn_id, prop_id, eval_id


# ---------------------------------------------------------------------------
# Test 1: Fresh evaluation is not stale
# ---------------------------------------------------------------------------

def test_fresh_evaluation_is_not_stale(client):
    """Immediately after creation, is_stale should be false and stale_artifacts empty."""
    pid = _pid()
    eval_data, pid, req_id, scn_id, prop_id, eval_id = _seed_full_project(client, pid)

    # The POST response itself should show is_stale=false
    # (staleness is added on read — check via GET)
    r = client.get(f"/api/projects/{pid}/evaluations/{eval_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_stale"] is False
    assert body["stale_artifacts"] == []


# ---------------------------------------------------------------------------
# Test 2: Updating requirements makes evaluation stale
# ---------------------------------------------------------------------------

def test_update_requirements_makes_evaluation_stale(client):
    """After updating requirements data, evaluation becomes stale with 'requirements' listed."""
    pid = _pid()
    _, pid, req_id, scn_id, prop_id, eval_id = _seed_full_project(client, pid)

    # Update requirements data
    r = client.put(f"/api/projects/{pid}/requirements/{req_id}", json={
        "data": {"system": {"name": "updated"}},
    })
    assert r.status_code == 200, r.text

    # Re-fetch evaluation — should now be stale
    r = client.get(f"/api/projects/{pid}/evaluations/{eval_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_stale"] is True
    assert "requirements" in body["stale_artifacts"]


# ---------------------------------------------------------------------------
# Test 3: Updating scenario makes evaluation stale
# ---------------------------------------------------------------------------

def test_update_scenario_makes_evaluation_stale(client):
    """After updating scenario data, evaluation becomes stale with 'scenario' listed."""
    pid = _pid()
    _, pid, req_id, scn_id, prop_id, eval_id = _seed_full_project(client, pid)

    # Update scenario data
    r = client.put(f"/api/projects/{pid}/scenarios/{scn_id}", json={
        "data": {"scenario": {"name": "updated"}},
    })
    assert r.status_code == 200, r.text

    # Re-fetch evaluation — should now be stale with scenario listed
    r = client.get(f"/api/projects/{pid}/evaluations/{eval_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_stale"] is True
    assert "scenario" in body["stale_artifacts"]


# ---------------------------------------------------------------------------
# Test 4: list_evaluations returns staleness for each evaluation
# ---------------------------------------------------------------------------

def test_list_evaluations_returns_staleness(client):
    """list_evaluations should include is_stale and stale_artifacts on every item."""
    pid = _pid()
    _, pid, req_id, scn_id, prop_id, eval_id = _seed_full_project(client, pid)

    # Fresh — list should show is_stale=false
    r = client.get(f"/api/projects/{pid}/evaluations")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["is_stale"] is False
    assert items[0]["stale_artifacts"] == []

    # Update requirements, then list again
    client.put(f"/api/projects/{pid}/requirements/{req_id}", json={
        "data": {"system": {"name": "changed"}},
    })
    r = client.get(f"/api/projects/{pid}/evaluations")
    assert r.status_code == 200, r.text
    items = r.json()
    assert items[0]["is_stale"] is True
    assert "requirements" in items[0]["stale_artifacts"]


# ---------------------------------------------------------------------------
# Test 5: New evaluation after artifact updates is fresh
# ---------------------------------------------------------------------------

def test_new_evaluation_after_update_is_fresh(client):
    """Creating a new evaluation after artifact updates captures current hashes → is_stale=false."""
    pid = _pid()
    _, pid, req_id, scn_id, prop_id, eval_id = _seed_full_project(client, pid)

    # Update both requirements and scenario
    client.put(f"/api/projects/{pid}/requirements/{req_id}", json={
        "data": {"system": {"name": "v2"}},
    })
    client.put(f"/api/projects/{pid}/scenarios/{scn_id}", json={
        "data": {"scenario": {"name": "v2"}},
    })

    # Old evaluation is now stale
    r = client.get(f"/api/projects/{pid}/evaluations/{eval_id}")
    assert r.json()["is_stale"] is True

    # Create a new evaluation using the updated artifacts
    new_eval_id = f"eval2-{pid}"
    r = client.post(f"/api/projects/{pid}/evaluations", json={
        "id": new_eval_id,
        "proposal_id": prop_id,
        "scenario_id": scn_id,
        "requirements_id": req_id,
        "source": "manual",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {},
    })
    assert r.status_code == 201, r.text

    # The new evaluation should be fresh
    r = client.get(f"/api/projects/{pid}/evaluations/{new_eval_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_stale"] is False
    assert body["stale_artifacts"] == []
